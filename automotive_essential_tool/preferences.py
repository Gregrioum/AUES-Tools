"""AddonPreferences and per-.blend Scene properties for Automotive Essential Tool (AUES) v2.1."""

import bpy
import rna_keymap_ui

from .utils import (
    get_addon_id,
    get_installed_matcaps,
    get_matcap_enum_items,
    get_modifier_enum_items,
    get_modifier_info,
    get_prefs,
    resolve_default_matcap_slots,
    resolve_default_modifier_slots,
)


def _mark_scene_matcap_initialized(self, context):
    if hasattr(self, "matcap_initialized") and not self.matcap_initialized:
        self.matcap_initialized = True


def _on_edit_matcaps_toggle(self, context):
    if self.edit_matcaps and context and getattr(context, "scene", None):
        ensure_scene_matcaps(context.scene, get_prefs(context))


def _make_matcap_getter(slot_idx: int):
    file_attr = f"matcap_file_{slot_idx}"

    def _getter(self):
        items = get_matcap_enum_items(self, bpy.context)
        target = getattr(self, file_attr, "")
        for idx, item in enumerate(items):
            if item[0] == target:
                return idx
        return 0

    return _getter


def _make_matcap_setter(slot_idx: int, mark_scene: bool = False):
    file_attr = f"matcap_file_{slot_idx}"
    label_attr = f"matcap_label_{slot_idx}"

    def _setter(self, value):
        items = get_matcap_enum_items(self, bpy.context)
        if 0 <= value < len(items):
            new_file = items[value][0]
            old_file = getattr(self, file_attr, "")
            setattr(self, file_attr, new_file)
            if new_file != old_file:
                setattr(self, label_attr, "")
            if mark_scene and hasattr(self, "matcap_initialized"):
                self.matcap_initialized = True

    return _setter


def _make_modifier_getter(slot_idx: int):
    type_attr = f"mod_type_{slot_idx}"

    def _getter(self):
        items = get_modifier_enum_items(self, bpy.context)
        target = getattr(self, type_attr, "")
        for idx, item in enumerate(items):
            if item[0] == target:
                return idx
        return 0

    return _getter


def _make_modifier_setter(slot_idx: int):
    type_attr = f"mod_type_{slot_idx}"
    label_attr = f"mod_label_{slot_idx}"

    def _setter(self, value):
        items = get_modifier_enum_items(self, bpy.context)
        if 0 <= value < len(items):
            new_type = items[value][0]
            old_type = getattr(self, type_attr, "")
            setattr(self, type_attr, new_type)
            if new_type != old_type:
                setattr(self, label_attr, "")

    return _setter


def populate_default_matcaps(target, force: bool = False):
    """Populate empty (or all, when force=True) MatCap slots on Prefs or Scene props."""
    if target is None:
        return
    has_any = any(getattr(target, f"matcap_file_{i}", "") for i in range(1, 7))
    if has_any and not force:
        return

    defaults = resolve_default_matcap_slots(bpy.context)
    for idx, (filename, label) in enumerate(defaults, start=1):
        setattr(target, f"matcap_file_{idx}", filename)
        setattr(target, f"matcap_label_{idx}", label)

    if hasattr(target, "matcap_initialized"):
        target.matcap_initialized = True


def copy_matcap_settings(src, dst):
    """Copy MatCap slot settings between AddonPreferences and Scene properties."""
    if src is None or dst is None:
        return
    dst.slot_count = src.slot_count
    dst.matcap_apply_all_viewports = src.matcap_apply_all_viewports
    for i in range(1, 7):
        setattr(dst, f"matcap_file_{i}", getattr(src, f"matcap_file_{i}", ""))
        setattr(dst, f"matcap_label_{i}", getattr(src, f"matcap_label_{i}", ""))
    if hasattr(dst, "matcap_initialized"):
        dst.matcap_initialized = True


def ensure_scene_matcaps(scene, prefs=None):
    """Ensure a Scene has MatCap settings saved in its .blend data without overwriting existing ones."""
    if scene is None or not hasattr(scene, "aues_props"):
        return
    props = scene.aues_props
    has_saved_files = any(getattr(props, f"matcap_file_{i}", "") for i in range(1, 7))
    if props.matcap_initialized or has_saved_files:
        if not props.matcap_initialized:
            props.matcap_initialized = True
        return

    if prefs is not None and any(getattr(prefs, f"matcap_file_{i}", "") for i in range(1, 7)):
        copy_matcap_settings(prefs, props)
    else:
        populate_default_matcaps(props, force=True)


def populate_default_modifiers(prefs, force: bool = False):
    """Populate empty (or all, when force=True) Quick Modifier slots with automotive defaults."""
    if prefs is None:
        return
    has_any = any(getattr(prefs, f"mod_type_{i}", "") for i in range(1, 7))
    if has_any and not force:
        return

    defaults = resolve_default_modifier_slots()
    for idx, (mod_type, label) in enumerate(defaults, start=1):
        setattr(prefs, f"mod_type_{idx}", mod_type)
        setattr(prefs, f"mod_label_{idx}", label)


class AUES_SceneProperties(bpy.types.PropertyGroup):
    """Per-scene modeling UI state and .blend-persisted MatCap slot configuration."""

    edit_matcaps: bpy.props.BoolProperty(
        name="Edit MatCap Slots",
        description="Toggle to assign different MatCaps and labels to this .blend file's quick slots",
        default=False,
        update=_on_edit_matcaps_toggle,
    )
    edit_modifiers: bpy.props.BoolProperty(
        name="Edit Modifier Slots",
        description="Toggle to personalize the quick modifier buttons",
        default=False,
    )
    edit_snapshot: bpy.props.BoolProperty(
        name="Snapshot Settings",
        description="Show or hide viewport snapshot options",
        default=False,
    )
    gstretch_method: bpy.props.EnumProperty(
        name="Method",
        description="GStretch calculation method",
        items=[
            ('project', "Project", "Project vertices onto the grease pencil stroke"),
            ('irregular', "Irregular", "Preserve relative vertex spacing along the stroke"),
            ('regular', "Regular", "Distribute vertices evenly along the stroke"),
        ],
        default='regular',
    )
    flatten_orient: bpy.props.EnumProperty(
        name="Orientation",
        description="Coordinate space used by Flatten X / Y / Z buttons",
        items=[
            ('ACTIVE', "Active", "Use the current 3D Viewport Transform Orientation"),
            ('GLOBAL', "Global", "Global world axes"),
            ('LOCAL', "Local", "Local object axes"),
            ('NORMAL', "Normal", "Selection normal orientation"),
            ('VIEW', "View", "Current 3D Viewport view orientation"),
        ],
        default='GLOBAL',
    )

    # --- Per-.blend MatCap Slots (saved inside the .blend file!) ---
    matcap_initialized: bpy.props.BoolProperty(
        name="MatCaps Initialized",
        default=False,
        options={'HIDDEN'},
    )
    slot_count: bpy.props.IntProperty(
        name="Active Slots",
        description="Number of quick MatCap buttons saved with this .blend file",
        default=3,
        min=1,
        max=6,
        update=_mark_scene_matcap_initialized,
    )
    matcap_apply_all_viewports: bpy.props.BoolProperty(
        name="Apply to All 3D Viewports",
        description="Apply MatCap changes to every 3D Viewport instead of only the active one (Shift+Click always applies to all)",
        default=False,
        update=_mark_scene_matcap_initialized,
    )

    matcap_file_1: bpy.props.StringProperty(name="Slot 1 File", default="")
    matcap_file_2: bpy.props.StringProperty(name="Slot 2 File", default="")
    matcap_file_3: bpy.props.StringProperty(name="Slot 3 File", default="")
    matcap_file_4: bpy.props.StringProperty(name="Slot 4 File", default="")
    matcap_file_5: bpy.props.StringProperty(name="Slot 5 File", default="")
    matcap_file_6: bpy.props.StringProperty(name="Slot 6 File", default="")

    matcap_label_1: bpy.props.StringProperty(name="Label 1", default="", description="Optional short button label", update=_mark_scene_matcap_initialized)
    matcap_label_2: bpy.props.StringProperty(name="Label 2", default="", description="Optional short button label", update=_mark_scene_matcap_initialized)
    matcap_label_3: bpy.props.StringProperty(name="Label 3", default="", description="Optional short button label", update=_mark_scene_matcap_initialized)
    matcap_label_4: bpy.props.StringProperty(name="Label 4", default="", description="Optional short button label", update=_mark_scene_matcap_initialized)
    matcap_label_5: bpy.props.StringProperty(name="Label 5", default="", description="Optional short button label", update=_mark_scene_matcap_initialized)
    matcap_label_6: bpy.props.StringProperty(name="Label 6", default="", description="Optional short button label", update=_mark_scene_matcap_initialized)

    matcap_pick_1: bpy.props.EnumProperty(
        name="Slot 1", items=get_matcap_enum_items,
        get=_make_matcap_getter(1), set=_make_matcap_setter(1, mark_scene=True),
        options={'SKIP_SAVE'},
    )
    matcap_pick_2: bpy.props.EnumProperty(
        name="Slot 2", items=get_matcap_enum_items,
        get=_make_matcap_getter(2), set=_make_matcap_setter(2, mark_scene=True),
        options={'SKIP_SAVE'},
    )
    matcap_pick_3: bpy.props.EnumProperty(
        name="Slot 3", items=get_matcap_enum_items,
        get=_make_matcap_getter(3), set=_make_matcap_setter(3, mark_scene=True),
        options={'SKIP_SAVE'},
    )
    matcap_pick_4: bpy.props.EnumProperty(
        name="Slot 4", items=get_matcap_enum_items,
        get=_make_matcap_getter(4), set=_make_matcap_setter(4, mark_scene=True),
        options={'SKIP_SAVE'},
    )
    matcap_pick_5: bpy.props.EnumProperty(
        name="Slot 5", items=get_matcap_enum_items,
        get=_make_matcap_getter(5), set=_make_matcap_setter(5, mark_scene=True),
        options={'SKIP_SAVE'},
    )
    matcap_pick_6: bpy.props.EnumProperty(
        name="Slot 6", items=get_matcap_enum_items,
        get=_make_matcap_getter(6), set=_make_matcap_setter(6, mark_scene=True),
        options={'SKIP_SAVE'},
    )


class AUES_AddonPreferences(bpy.types.AddonPreferences):
    """Persistent user preferences shared across Blender sessions."""

    bl_idname = get_addon_id()

    # --- Global Default MatCap Slots (seeded into new .blend files) ---
    slot_count: bpy.props.IntProperty(
        name="Active Slots",
        description="Default number of quick MatCap buttons for new .blend files",
        default=3,
        min=1,
        max=6,
    )
    matcap_apply_all_viewports: bpy.props.BoolProperty(
        name="Apply to All 3D Viewports",
        description="Apply MatCap changes to every 3D Viewport in the workspace instead of only the active one (Shift+Click always applies to all)",
        default=False,
    )

    matcap_file_1: bpy.props.StringProperty(name="Slot 1 File", default="")
    matcap_file_2: bpy.props.StringProperty(name="Slot 2 File", default="")
    matcap_file_3: bpy.props.StringProperty(name="Slot 3 File", default="")
    matcap_file_4: bpy.props.StringProperty(name="Slot 4 File", default="")
    matcap_file_5: bpy.props.StringProperty(name="Slot 5 File", default="")
    matcap_file_6: bpy.props.StringProperty(name="Slot 6 File", default="")

    matcap_label_1: bpy.props.StringProperty(name="Label 1", default="", description="Optional short button label")
    matcap_label_2: bpy.props.StringProperty(name="Label 2", default="", description="Optional short button label")
    matcap_label_3: bpy.props.StringProperty(name="Label 3", default="", description="Optional short button label")
    matcap_label_4: bpy.props.StringProperty(name="Label 4", default="", description="Optional short button label")
    matcap_label_5: bpy.props.StringProperty(name="Label 5", default="", description="Optional short button label")
    matcap_label_6: bpy.props.StringProperty(name="Label 6", default="", description="Optional short button label")

    matcap_pick_1: bpy.props.EnumProperty(
        name="Slot 1", items=get_matcap_enum_items,
        get=_make_matcap_getter(1), set=_make_matcap_setter(1),
        options={'SKIP_SAVE'},
    )
    matcap_pick_2: bpy.props.EnumProperty(
        name="Slot 2", items=get_matcap_enum_items,
        get=_make_matcap_getter(2), set=_make_matcap_setter(2),
        options={'SKIP_SAVE'},
    )
    matcap_pick_3: bpy.props.EnumProperty(
        name="Slot 3", items=get_matcap_enum_items,
        get=_make_matcap_getter(3), set=_make_matcap_setter(3),
        options={'SKIP_SAVE'},
    )
    matcap_pick_4: bpy.props.EnumProperty(
        name="Slot 4", items=get_matcap_enum_items,
        get=_make_matcap_getter(4), set=_make_matcap_setter(4),
        options={'SKIP_SAVE'},
    )
    matcap_pick_5: bpy.props.EnumProperty(
        name="Slot 5", items=get_matcap_enum_items,
        get=_make_matcap_getter(5), set=_make_matcap_setter(5),
        options={'SKIP_SAVE'},
    )
    matcap_pick_6: bpy.props.EnumProperty(
        name="Slot 6", items=get_matcap_enum_items,
        get=_make_matcap_getter(6), set=_make_matcap_setter(6),
        options={'SKIP_SAVE'},
    )

    # --- Quick Modifier Slots (persisted globally) ---
    mod_slot_count: bpy.props.IntProperty(
        name="Active Slots",
        description="Number of quick modifier buttons displayed in the panel",
        default=6,
        min=1,
        max=6,
    )
    mod_smart_defaults: bpy.props.BoolProperty(
        name="Automotive Modifier Presets",
        description="Apply automotive-friendly initial settings when adding modifiers (Mirror Clipping, SubD L2 + Optimal Display, Bevel Weight, Weighted Normal Keep Sharp)",
        default=True,
    )

    mod_type_1: bpy.props.StringProperty(name="Modifier Slot 1", default="")
    mod_type_2: bpy.props.StringProperty(name="Modifier Slot 2", default="")
    mod_type_3: bpy.props.StringProperty(name="Modifier Slot 3", default="")
    mod_type_4: bpy.props.StringProperty(name="Modifier Slot 4", default="")
    mod_type_5: bpy.props.StringProperty(name="Modifier Slot 5", default="")
    mod_type_6: bpy.props.StringProperty(name="Modifier Slot 6", default="")

    mod_label_1: bpy.props.StringProperty(name="Modifier Label 1", default="", description="Optional short button label")
    mod_label_2: bpy.props.StringProperty(name="Modifier Label 2", default="", description="Optional short button label")
    mod_label_3: bpy.props.StringProperty(name="Modifier Label 3", default="", description="Optional short button label")
    mod_label_4: bpy.props.StringProperty(name="Modifier Label 4", default="", description="Optional short button label")
    mod_label_5: bpy.props.StringProperty(name="Modifier Label 5", default="", description="Optional short button label")
    mod_label_6: bpy.props.StringProperty(name="Modifier Label 6", default="", description="Optional short button label")

    mod_pick_1: bpy.props.EnumProperty(
        name="Slot 1", items=get_modifier_enum_items,
        get=_make_modifier_getter(1), set=_make_modifier_setter(1),
        options={'SKIP_SAVE'},
    )
    mod_pick_2: bpy.props.EnumProperty(
        name="Slot 2", items=get_modifier_enum_items,
        get=_make_modifier_getter(2), set=_make_modifier_setter(2),
        options={'SKIP_SAVE'},
    )
    mod_pick_3: bpy.props.EnumProperty(
        name="Slot 3", items=get_modifier_enum_items,
        get=_make_modifier_getter(3), set=_make_modifier_setter(3),
        options={'SKIP_SAVE'},
    )
    mod_pick_4: bpy.props.EnumProperty(
        name="Slot 4", items=get_modifier_enum_items,
        get=_make_modifier_getter(4), set=_make_modifier_setter(4),
        options={'SKIP_SAVE'},
    )
    mod_pick_5: bpy.props.EnumProperty(
        name="Slot 5", items=get_modifier_enum_items,
        get=_make_modifier_getter(5), set=_make_modifier_setter(5),
        options={'SKIP_SAVE'},
    )
    mod_pick_6: bpy.props.EnumProperty(
        name="Slot 6", items=get_modifier_enum_items,
        get=_make_modifier_getter(6), set=_make_modifier_setter(6),
        options={'SKIP_SAVE'},
    )

    # --- Screenshot Settings ---
    screenshot_mode: bpy.props.EnumProperty(
        name="Capture Mode",
        description="Method used to capture viewport snapshots",
        items=[
            (
                'OPENGL',
                "Viewport Render (Clean)",
                "Uses Blender OpenGL viewport render at scene resolution with zero UI chrome",
            ),
            (
                'AREA',
                "Area Capture (Fast)",
                "Captures raw 3D Viewport area pixels at current viewport dimensions",
            ),
        ],
        default='OPENGL',
    )
    screenshot_dir: bpy.props.StringProperty(
        name="Quick Save Folder",
        description="Output directory for 1-Click Quick Save snapshots (supports // relative to .blend)",
        subtype='DIR_PATH',
        default="//aues_screenshots/",
    )
    screenshot_prefix: bpy.props.StringProperty(
        name="Filename Prefix",
        description="Prefix for auto-numbered Quick Save snapshots",
        default="AUES_shot",
    )
    screenshot_hide_overlays: bpy.props.BoolProperty(
        name="Hide Overlays",
        description="Temporarily hide viewport overlays (grid, outlines, 3D cursor) during capture",
        default=True,
    )
    screenshot_hide_gizmos: bpy.props.BoolProperty(
        name="Hide Gizmos",
        description="Temporarily hide viewport gizmos during capture",
        default=True,
    )
    screenshot_hide_ui: bpy.props.BoolProperty(
        name="Hide UI Regions (Area Mode)",
        description="Temporarily hide N-Panel, Toolbar, and Header during Area Capture",
        default=True,
    )
    screenshot_transparent_bg: bpy.props.BoolProperty(
        name="Transparent Background (Render Mode)",
        description="Render viewport background as transparent PNG alpha in Viewport Render mode",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        installed_set = set(get_installed_matcaps(context))

        # Quick Modifier Slots
        box_mod = layout.box()
        row_mh = box_mod.row()
        row_mh.label(text="Quick Modifier Slots (Saved Globally)", icon='MODIFIER')
        row_mh.operator("aues.reset_modifier_defaults", text="Reset Defaults", icon='LOOP_BACK')

        row_mt = box_mod.row(align=True)
        row_mt.prop(self, "mod_slot_count")
        row_mt.prop(self, "mod_smart_defaults")

        for i in range(1, self.mod_slot_count + 1):
            mtype = getattr(self, f"mod_type_{i}", "")
            mname, _ = get_modifier_info(mtype)
            split = box_mod.split(factor=0.62, align=True)
            if mtype and mname is None:
                split.alert = True
            split.prop(self, f"mod_pick_{i}", text=f"Slot {i}")
            split.prop(self, f"mod_label_{i}", text="", placeholder="Custom label...")

        # MatCap Default Slots
        box = layout.box()
        row = box.row()
        row.label(text="Default MatCap Slots (New .blend Files)", icon='SHADING_SOLID')
        op_apply = row.operator("aues.sync_matcap_prefs", text="Apply to Scene", icon='IMPORT')
        op_apply.direction = 'PREFS_TO_SCENE'
        op_rst = row.operator("aues.reset_matcap_defaults", text="Reset Defaults", icon='LOOP_BACK')
        op_rst.target = 'PREFS'

        row_top = box.row(align=True)
        row_top.prop(self, "slot_count")
        row_top.prop(self, "matcap_apply_all_viewports")

        for i in range(1, self.slot_count + 1):
            fname = getattr(self, f"matcap_file_{i}", "")
            split = box.split(factor=0.62, align=True)
            if fname and fname not in installed_set:
                split.alert = True
            split.prop(self, f"matcap_pick_{i}", text=f"Slot {i}")
            split.prop(self, f"matcap_label_{i}", text="", placeholder="Custom label...")

        # Snapshot Defaults
        box_snap = layout.box()
        box_snap.label(text="Viewport Snapshot Defaults", icon='CAMERA_DATA')
        box_snap.prop(self, "screenshot_mode")
        box_snap.prop(self, "screenshot_dir")
        box_snap.prop(self, "screenshot_prefix")
        row_flags = box_snap.row(align=True)
        row_flags.prop(self, "screenshot_hide_overlays")
        row_flags.prop(self, "screenshot_hide_gizmos")
        row_flags2 = box_snap.row(align=True)
        row_flags2.prop(self, "screenshot_hide_ui")
        row_flags2.prop(self, "screenshot_transparent_bg")

        # Keymap
        box_km = layout.box()
        box_km.label(text="Pie Menu Shortcut", icon='KEYINGSET')
        wm = context.window_manager
        kc = wm.keyconfigs.user if wm else None
        if kc:
            km = kc.keymaps.get('3D View')
            if km:
                found = False
                for kmi in km.keymap_items:
                    if kmi.idname == "wm.call_menu_pie" and getattr(kmi.properties, "name", "") == "AUES_MT_pie_menu":
                        box_km.context_pointer_set("keymap", km)
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, box_km, 0)
                        found = True
                if not found:
                    box_km.label(text="Pie menu shortcut not registered.", icon='INFO')
