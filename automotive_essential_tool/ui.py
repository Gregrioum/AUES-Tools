"""N-Panel UI and Pie Menu for Automotive Essential Tool (AUES) v2.1."""

import bpy

from .utils import (
    find_looptools_module,
    format_matcap_label,
    format_modifier_label,
    get_installed_matcaps,
    get_modifier_info,
    get_prefs,
    has_operator,
    is_looptools_available,
)


class AUES_PT_main_panel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AUES'
    bl_label = 'AUES Tools v2.1'

    def draw(self, context):
        layout = self.layout
        props = context.scene.aues_props
        prefs = get_prefs(context)
        space = context.space_data

        # ------------------------------------------------------------------
        # Section 1: LoopTools Quick Access
        # ------------------------------------------------------------------
        layout.label(text="LoopTools Quick Access:")

        if not is_looptools_available():
            box_warn = layout.box()
            box_warn.label(text="LoopTools is not enabled!", icon='ERROR')
            has_mod = find_looptools_module() is not None
            btn_text = "Enable LoopTools" if has_mod else "Install LoopTools..."
            box_warn.operator("aues.enable_looptools", text=btn_text, icon='CHECKMARK')
        else:
            col_lt = layout.column(align=True)
            row_lt1 = col_lt.row(align=True)
            row_lt1.operator("mesh.looptools_relax", text="Relax")
            row_lt1.operator("mesh.looptools_space", text="Space")

            row_lt2 = col_lt.row(align=True)
            if has_operator("mesh", "looptools_curve"):
                row_lt2.operator("mesh.looptools_curve", text="Curve")
            if has_operator("mesh", "looptools_circle"):
                row_lt2.operator("mesh.looptools_circle", text="Circle")

            box_gs = layout.box()
            row_gs = box_gs.row(align=True)
            row_gs.operator("aues.gstretch", text="GStretch")
            row_gs.prop(props, "gstretch_method", text="")

        layout.separator()

        # ------------------------------------------------------------------
        # Section 2: Flatten, Straighten & Edge Flow
        # ------------------------------------------------------------------
        row_flat_hdr = layout.row(align=True)
        row_flat_hdr.label(text="Flatten:")
        row_flat_hdr.prop(props, "flatten_orient", text="")

        col_flat = layout.column(align=True)
        row_axes = col_flat.row(align=True)
        row_axes.scale_y = 1.2
        for axis in ('X', 'Y', 'Z'):
            op = row_axes.operator("aues.flatten_axis", text=axis)
            op.axis = axis
            op.orient_type = props.flatten_orient

        row_extra = col_flat.row(align=True)
        row_extra.operator("aues.flatten_best_fit", text="Plane", icon='MESH_PLANE')
        row_extra.operator("aues.straighten_line", text="Straighten", icon='IPO_LINEAR')
        row_extra.operator("aues.edge_flow", text="Edge Flow", icon='SMOOTHCURVE')

        layout.separator()

        # ------------------------------------------------------------------
        # Section 3: Quick Sharpness (Crease, Sharp, Bevel Weight)
        # ------------------------------------------------------------------
        row_sharp_hdr = layout.row(align=True)
        row_sharp_hdr.label(text="Quick Sharpness:")
        if space and space.type == 'VIEW_3D' and hasattr(space.overlay, "show_edge_crease"):
            row_sharp_hdr.prop(space.overlay, "show_edge_crease", text="", icon='EDGESEL')

        col_sharp = layout.column(align=True)
        row_crease = col_sharp.row(align=True)
        for val, lbl in ((0.0, "0"), (0.25, ".25"), (0.5, ".5"), (0.75, ".75"), (1.0, "1")):
            op_c = row_crease.operator("aues.set_crease", text=lbl)
            op_c.crease_value = val

        row_edges = col_sharp.row(align=True)
        op_s_on = row_edges.operator("aues.set_sharp", text="Sharp")
        op_s_on.sharp = True
        op_s_off = row_edges.operator("aues.set_sharp", text="Clear")
        op_s_off.sharp = False
        op_bw0 = row_edges.operator("aues.set_bevel_weight", text="BW 0")
        op_bw0.weight_value = 0.0
        op_bw1 = row_edges.operator("aues.set_bevel_weight", text="BW 1")
        op_bw1.weight_value = 1.0

        layout.separator()

        # ------------------------------------------------------------------
        # Section 4: Quick Modifiers (Personalized Slots)
        # ------------------------------------------------------------------
        row_mod_hdr = layout.row(align=True)
        row_mod_hdr.label(text="Quick Modifiers:")
        row_mod_hdr.prop(props, "edit_modifiers", text="", icon='PREFERENCES')

        if prefs is None:
            layout.label(text="Preferences unavailable", icon='ERROR')
        elif props.edit_modifiers:
            box_mod = layout.box()
            box_mod.prop(prefs, "mod_slot_count")
            box_mod.prop(prefs, "mod_smart_defaults")
            box_mod.separator()
            for i in range(1, prefs.mod_slot_count + 1):
                mtype = getattr(prefs, f"mod_type_{i}", "")
                mname, _ = get_modifier_info(mtype)
                split = box_mod.split(factor=0.62, align=True)
                if mtype and mname is None:
                    split.alert = True
                split.prop(prefs, f"mod_pick_{i}", text="")
                split.prop(prefs, f"mod_label_{i}", text="", placeholder="Label...")
            box_mod.operator("aues.reset_modifier_defaults", text="Reset Defaults", icon='LOOP_BACK')
        else:
            mod_slots = list(range(1, prefs.mod_slot_count + 1))
            for i in range(0, len(mod_slots), 3):
                chunk = mod_slots[i:i + 3]
                row_mbtns = layout.row(align=True)
                row_mbtns.scale_y = 1.25
                for slot_num in chunk:
                    mtype = getattr(prefs, f"mod_type_{slot_num}", "")
                    custom_lbl = getattr(prefs, f"mod_label_{slot_num}", "")
                    label = format_modifier_label(mtype, custom_lbl)
                    mname, micon = get_modifier_info(mtype)
                    if mtype and mname is not None:
                        op_m = row_mbtns.operator("aues.add_modifier", text=label, icon=micon)
                        op_m.mod_type = mtype
                    else:
                        sub = row_mbtns.row(align=True)
                        sub.alert = True
                        sub.enabled = False
                        na_lbl = f"{label} (Unavailable)" if mtype else "Empty"
                        op_m = sub.operator("aues.add_modifier", text=na_lbl, icon='ERROR')
                        op_m.mod_type = mtype

        layout.separator()

        # ------------------------------------------------------------------
        # Section 5: Quick Surface (Saved per .blend) & Surface Inspection
        # ------------------------------------------------------------------
        row_mat_hdr = layout.row(align=True)
        row_mat_hdr.label(text="Quick Surface:")
        row_mat_hdr.operator("aues.flip_matcap", text="", icon='ARROW_LEFTRIGHT')
        row_mat_hdr.prop(props, "edit_matcaps", text="", icon='PREFERENCES')

        # Compact Inspection Strip (Overlays, Wireframe, Face Orientation, Cavity, Backface)
        if space and space.type == 'VIEW_3D':
            row_insp = layout.row(align=True)
            row_insp.prop(space.overlay, "show_overlays", text="", icon='OVERLAY')
            row_insp.prop(space.overlay, "show_wireframes", text="", icon='SHADING_WIRE')
            row_insp.prop(space.overlay, "show_face_orientation", text="", icon='NORMALS_FACE')
            if hasattr(space.shading, "show_cavity"):
                row_insp.prop(space.shading, "show_cavity", text="Cavity", toggle=True)
            if hasattr(space.shading, "show_backface_culling"):
                row_insp.prop(space.shading, "show_backface_culling", text="Backface", toggle=True)

        installed_set = set(get_installed_matcaps(context))
        scene_has_matcaps = props.matcap_initialized or any(
            getattr(props, f"matcap_file_{i}", "") for i in range(1, 7)
        )
        matcap_source = props if scene_has_matcaps else prefs

        if matcap_source is None:
            layout.label(text="MatCap settings unavailable", icon='ERROR')
        elif props.edit_matcaps:
            box_mat = layout.box()
            box_mat.label(text="Saved with .blend file", icon='FILE_BLEND')
            box_mat.prop(props, "slot_count")
            box_mat.prop(props, "matcap_apply_all_viewports")
            box_mat.separator()
            for i in range(1, props.slot_count + 1):
                fname = getattr(props, f"matcap_file_{i}", "")
                split = box_mat.split(factor=0.62, align=True)
                if fname and fname not in installed_set:
                    split.alert = True
                split.prop(props, f"matcap_pick_{i}", text="")
                split.prop(props, f"matcap_label_{i}", text="", placeholder="Label...")

            row_sync = box_mat.row(align=True)
            op_save_g = row_sync.operator("aues.sync_matcap_prefs", text="Save Global", icon='EXPORT')
            op_save_g.direction = 'SCENE_TO_PREFS'
            op_load_g = row_sync.operator("aues.sync_matcap_prefs", text="Load Global", icon='IMPORT')
            op_load_g.direction = 'PREFS_TO_SCENE'

            op_rst = box_mat.operator("aues.reset_matcap_defaults", text="Reset Defaults", icon='LOOP_BACK')
            op_rst.target = 'SCENE'
        else:
            is_matcap_active = (
                space is not None
                and space.type == 'VIEW_3D'
                and space.shading.type == 'SOLID'
                and space.shading.light == 'MATCAP'
            )
            current_light = space.shading.studio_light if is_matcap_active else ""
            has_unavailable = False

            slots = list(range(1, matcap_source.slot_count + 1))
            for i in range(0, len(slots), 3):
                chunk = slots[i:i + 3]
                row_btns = layout.row(align=True)
                row_btns.scale_y = 1.35
                for slot_num in chunk:
                    matcap_file = getattr(matcap_source, f"matcap_file_{slot_num}", "")
                    custom_lbl = getattr(matcap_source, f"matcap_label_{slot_num}", "")
                    label = format_matcap_label(matcap_file, custom_lbl)
                    is_available = bool(matcap_file) and (matcap_file in installed_set)

                    if is_available:
                        is_current = bool(is_matcap_active and current_light == matcap_file)
                        op = row_btns.operator(
                            "aues.set_matcap",
                            text=label,
                            depress=is_current,
                        )
                        op.matcap_name = matcap_file
                    else:
                        if matcap_file:
                            has_unavailable = True
                        sub = row_btns.row(align=True)
                        sub.alert = True
                        sub.enabled = False
                        na_lbl = f"{label} (Unavailable)" if matcap_file else "Empty"
                        op = sub.operator(
                            "aues.set_matcap",
                            text=na_lbl,
                            icon='ERROR',
                        )
                        op.matcap_name = matcap_file

            if has_unavailable:
                row_na = layout.row()
                row_na.alert = True
                row_na.label(text="Some saved MatCaps are unavailable", icon='ERROR')

        layout.separator()

        # ------------------------------------------------------------------
        # Section 6: Quick Snapshot
        # ------------------------------------------------------------------
        row_snap_hdr = layout.row(align=True)
        row_snap_hdr.label(text="Quick Snapshot:")
        row_snap_hdr.prop(props, "edit_snapshot", text="", icon='PREFERENCES')

        if props.edit_snapshot and prefs is not None:
            box_snap = layout.box()
            box_snap.prop(prefs, "screenshot_mode", text="")
            row_f1 = box_snap.row(align=True)
            row_f1.prop(prefs, "screenshot_hide_overlays", text="No Overlays", toggle=True)
            row_f1.prop(prefs, "screenshot_hide_gizmos", text="No Gizmos", toggle=True)
            if prefs.screenshot_mode == 'AREA':
                box_snap.prop(prefs, "screenshot_hide_ui", text="Hide UI Regions")
            else:
                box_snap.prop(prefs, "screenshot_transparent_bg", text="Transparent BG")
            box_snap.prop(prefs, "screenshot_dir", text="")

        row_snap_btns = layout.row(align=True)
        row_snap_btns.scale_y = 1.2
        row_snap_btns.operator("aues.quick_screenshot", text="Quick Save", icon='IMAGE_DATA')
        row_snap_btns.operator("aues.take_screenshot", text="Save As...", icon='CAMERA_DATA')


class AUES_MT_pie_menu(bpy.types.Menu):
    bl_idname = "AUES_MT_pie_menu"
    bl_label = "AUES Quick Pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        lt_ready = is_looptools_available()

        # 1. West
        if lt_ready:
            pie.operator("mesh.looptools_relax", text="Relax Spacing", icon='MOD_SMOOTH')
        else:
            pie.operator("aues.enable_looptools", text="Enable LoopTools", icon='ERROR')

        # 2. East
        if lt_ready:
            pie.operator("mesh.looptools_space", text="Even Space", icon='EDGESEL')
        else:
            pie.separator()

        # 3. South
        pie.operator("aues.flatten_best_fit", text="Flatten to Plane", icon='MESH_PLANE')

        # 4. North
        pie.operator("aues.flip_matcap", text="Flip MatCap", icon='ARROW_LEFTRIGHT')

        # 5. North-West
        op_c0 = pie.operator("aues.set_crease", text="Crease 0")
        op_c0.crease_value = 0.0

        # 6. North-East
        op_c1 = pie.operator("aues.set_crease", text="Crease 1")
        op_c1.crease_value = 1.0

        # 7. South-West
        pie.operator("aues.edge_flow", text="Edge Flow", icon='SMOOTHCURVE')

        # 8. South-East
        pie.operator("aues.quick_screenshot", text="Quick Snapshot", icon='CAMERA_DATA')


CLASSES = (
    AUES_PT_main_panel,
    AUES_MT_pie_menu,
)
