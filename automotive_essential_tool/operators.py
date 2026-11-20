"""Operators for Automotive Essential Tool (AUES) v2.1."""

from datetime import datetime
import os
import tempfile

import bmesh
import bpy
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector

from .preferences import (
    copy_matcap_settings,
    ensure_scene_matcaps,
    populate_default_matcaps,
    populate_default_modifiers,
)
from .utils import (
    find_looptools_module,
    find_window_region,
    get_installed_matcaps,
    get_modifier_info,
    get_prefs,
    has_operator,
    is_matcap_installed,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _get_edit_mesh_objects(context):
    if hasattr(context, "objects_in_mode_unique_data"):
        return [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']
    if context.edit_object and context.edit_object.type == 'MESH':
        return [context.edit_object]
    return []


def _has_selected_verts(objects) -> bool:
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        if any(v.select for v in bm.verts):
            return True
    return False


def _apply_automotive_modifier_preset(mod):
    """Apply clean automotive-modeling defaults to newly added modifiers."""
    mtype = mod.type
    try:
        if mtype == 'MIRROR':
            mod.use_axis = (True, False, False)
            mod.use_clip = True
        elif mtype == 'SUBSURF':
            mod.levels = 2
            mod.render_levels = 2
            mod.show_only_control_edges = True
        elif mtype == 'SOLIDIFY':
            mod.thickness = 0.005
            mod.offset = -1.0
        elif mtype == 'BEVEL':
            mod.limit_method = 'WEIGHT'
            mod.segments = 2
            mod.width = 0.01
        elif mtype == 'WEIGHTED_NORMAL':
            mod.keep_sharp = True
        elif mtype == 'SHRINKWRAP':
            mod.wrap_method = 'NEAREST_SURFACEPOINT'
        elif mtype == 'WELD':
            mod.merge_threshold = 0.0001
    except Exception:
        pass


def _resolve_quick_save_dir(raw_dir: str) -> str:
    """Resolve screenshot output directory, handling unsaved .blend relative paths."""
    if raw_dir.startswith("//") and not bpy.data.filepath:
        home = os.path.expanduser("~")
        pictures = os.path.join(home, "Pictures")
        base = pictures if os.path.isdir(pictures) else tempfile.gettempdir()
        return os.path.join(base, "AUES_Screenshots")
    resolved = bpy.path.abspath(raw_dir)
    return resolved or tempfile.gettempdir()


def _next_numbered_filepath(directory: str, prefix: str, ext: str = ".png") -> str:
    os.makedirs(directory, exist_ok=True)
    clean_prefix = (prefix or "AUES_shot").strip()
    idx = 1
    while True:
        candidate = os.path.join(directory, f"{clean_prefix}_{idx:03d}{ext}")
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def _run_opengl_capture(
    context,
    area,
    space,
    filepath: str,
    hide_overlays: bool,
    hide_gizmos: bool,
    transparent_bg: bool,
):
    """Capture a clean, anti-aliased OpenGL viewport render without UI chrome."""
    scene = context.scene
    render = scene.render
    img_settings = render.image_settings

    orig_filepath = render.filepath
    orig_format = img_settings.file_format
    orig_color_mode = img_settings.color_mode
    orig_transparent = render.film_transparent
    orig_overlays = space.overlay.show_overlays
    orig_gizmo = space.show_gizmo

    win_region = find_window_region(area)
    if win_region is None:
        raise RuntimeError("Could not find 3D Viewport WINDOW region")

    try:
        render.filepath = filepath
        img_settings.file_format = 'PNG'
        if transparent_bg:
            img_settings.color_mode = 'RGBA'
            render.film_transparent = True

        if hide_overlays:
            space.overlay.show_overlays = False
        if hide_gizmos:
            space.show_gizmo = False

        override = {
            'window': context.window,
            'screen': context.screen,
            'area': area,
            'region': win_region,
        }
        with bpy.context.temp_override(**override):
            bpy.ops.render.opengl(write_still=True)
    finally:
        render.filepath = orig_filepath
        img_settings.file_format = orig_format
        img_settings.color_mode = orig_color_mode
        render.film_transparent = orig_transparent
        try:
            space.overlay.show_overlays = orig_overlays
            space.show_gizmo = orig_gizmo
        except (ReferenceError, AttributeError):
            pass


def _run_area_capture(
    context,
    area,
    space,
    filepath: str,
    hide_overlays: bool,
    hide_gizmos: bool,
    hide_ui: bool,
    delay: float = 0.15,
):
    """Capture 3D Viewport pixels cleanly using the WINDOW region override."""
    window = context.window
    screen = context.screen

    orig_ui = getattr(space, "show_region_ui", True)
    orig_toolbar = getattr(space, "show_region_toolbar", True)
    orig_header = getattr(space, "show_region_header", True)
    orig_overlays = space.overlay.show_overlays
    orig_gizmo = space.show_gizmo

    if hide_ui:
        if hasattr(space, "show_region_ui"):
            space.show_region_ui = False
        if hasattr(space, "show_region_toolbar"):
            space.show_region_toolbar = False
        if hasattr(space, "show_region_header"):
            space.show_region_header = False
    if hide_overlays:
        space.overlay.show_overlays = False
    if hide_gizmos:
        space.show_gizmo = False

    def _restore():
        try:
            if hasattr(space, "show_region_ui"):
                space.show_region_ui = orig_ui
            if hasattr(space, "show_region_toolbar"):
                space.show_region_toolbar = orig_toolbar
            if hasattr(space, "show_region_header"):
                space.show_region_header = orig_header
            space.overlay.show_overlays = orig_overlays
            space.show_gizmo = orig_gizmo
        except (ReferenceError, AttributeError):
            pass

    def _take_shot():
        try:
            wm = bpy.context.window_manager
            if window not in wm.windows or area not in window.screen.areas:
                return None

            win_region = find_window_region(area)
            if win_region is None:
                print("AUES Screenshot failed: WINDOW region unavailable")
                return None

            override = {
                'window': window,
                'screen': screen,
                'area': area,
                'region': win_region,
            }
            with bpy.context.temp_override(**override):
                if has_operator("screen", "screenshot_area"):
                    bpy.ops.screen.screenshot_area(filepath=filepath)
                else:
                    bpy.ops.screen.screenshot(filepath=filepath)
        except Exception as exc:
            print(f"AUES Screenshot failed: {exc}")
        finally:
            _restore()
        return None

    if delay > 0.0:
        bpy.app.timers.register(_take_shot, first_interval=delay)
    else:
        _take_shot()


# -----------------------------------------------------------------------------
# LoopTools Operators
# -----------------------------------------------------------------------------

class AUES_OT_enable_looptools(bpy.types.Operator):
    bl_idname = "aues.enable_looptools"
    bl_label = "Enable LoopTools"
    bl_description = "Enable LoopTools (supports both Blender 4.2+ Extensions and legacy add-on)"

    def execute(self, context):
        mod_name = find_looptools_module()
        if mod_name:
            try:
                bpy.ops.preferences.addon_enable(module=mod_name)
                self.report({'INFO'}, f"Enabled LoopTools ({mod_name})")
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, f"Failed to enable LoopTools: {exc}")
                return {'CANCELLED'}

        try:
            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
            if hasattr(context.preferences, "active_section"):
                context.preferences.active_section = 'EXTENSIONS'
        except Exception:
            pass
        self.report(
            {'WARNING'},
            "LoopTools is not installed. Install 'LoopTools' from Preferences > Get Extensions.",
        )
        return {'CANCELLED'}


class AUES_OT_gstretch(bpy.types.Operator):
    bl_idname = "aues.gstretch"
    bl_label = "GStretch"
    bl_description = "Distribute selected vertices along an active Grease Pencil / Annotation stroke"
    bl_options = {'REGISTER', 'UNDO'}

    method: bpy.props.EnumProperty(
        name="Method",
        items=[
            ('project', "Project", "Project vertices onto the stroke"),
            ('irregular', "Irregular", "Preserve relative spacing along the stroke"),
            ('regular', "Regular", "Distribute vertices evenly along the stroke"),
        ],
        default='regular',
    )
    influence: bpy.props.FloatProperty(
        name="Influence",
        description="Strength of the GStretch projection",
        min=0.0,
        max=100.0,
        default=100.0,
        subtype='PERCENTAGE',
    )
    delete_strokes: bpy.props.BoolProperty(
        name="Delete Strokes",
        description="Remove annotation strokes after applying GStretch",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        props = getattr(context.scene, "aues_props", None)
        if props is not None:
            self.method = props.gstretch_method
        return self.execute(context)

    def execute(self, context):
        if not has_operator("mesh", "looptools_gstretch"):
            self.report({'WARNING'}, "LoopTools is not enabled")
            return {'CANCELLED'}
        try:
            bpy.ops.mesh.looptools_gstretch(
                method=self.method,
                influence=self.influence,
                delete_strokes=self.delete_strokes,
            )
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Flatten & Plane Snap Operators
# -----------------------------------------------------------------------------

class AUES_OT_flatten_axis(bpy.types.Operator):
    bl_idname = "aues.flatten_axis"
    bl_label = "Flatten Axis"
    bl_description = "Flatten selected vertices along an axis"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('X', "X", "Flatten along X axis"),
            ('Y', "Y", "Flatten along Y axis"),
            ('Z', "Z", "Flatten along Z axis"),
        ],
        default='X',
    )
    orient_type: bpy.props.EnumProperty(
        name="Orientation",
        items=[
            ('ACTIVE', "Active", "Use the current 3D Viewport Transform Orientation"),
            ('GLOBAL', "Global", "Global world coordinates"),
            ('LOCAL', "Local", "Local object coordinates"),
            ('NORMAL', "Normal", "Selection normal coordinates"),
            ('VIEW', "View", "Current view coordinates"),
        ],
        default='GLOBAL',
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        if not _has_selected_verts(objects):
            self.report({'INFO'}, "No vertices selected")
            return {'CANCELLED'}

        axis_map = {
            'X': ((0.0, 1.0, 1.0), (True, False, False)),
            'Y': ((1.0, 0.0, 1.0), (False, True, False)),
            'Z': ((1.0, 1.0, 0.0), (False, False, True)),
        }
        val, constraint = axis_map[self.axis]

        try:
            kwargs = {
                'value': val,
                'constraint_axis': constraint,
                'use_proportional_edit': False,
            }
            if self.orient_type != 'ACTIVE':
                kwargs['orient_type'] = self.orient_type
            bpy.ops.transform.resize(**kwargs)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        return {'FINISHED'}


def _eval_cubic_chord_lagrange(p0: Vector, p1: Vector, p2: Vector, p3: Vector, frac: float) -> Vector:
    """Evaluate a 4-point chord-length cubic Lagrange spline between p1 and p2 at frac in [0, 1].

    Accurately reproduces circular/curved automotive surface arcs without overshooting
    next to uneven quad widths (such as support loops / bevels adjacent to wide panels).
    """
    t0 = 0.0
    t1 = t0 + max((p1 - p0).length, 1e-5)
    t2 = t1 + max((p2 - p1).length, 1e-5)
    t3 = t2 + max((p3 - p2).length, 1e-5)
    t = t1 + (t2 - t1) * frac

    l0 = ((t - t1) * (t - t2) * (t - t3)) / ((t0 - t1) * (t0 - t2) * (t0 - t3))
    l1 = ((t - t0) * (t - t2) * (t - t3)) / ((t1 - t0) * (t1 - t2) * (t1 - t3))
    l2 = ((t - t0) * (t - t1) * (t - t3)) / ((t2 - t0) * (t2 - t1) * (t2 - t3))
    l3 = ((t - t0) * (t - t1) * (t - t2)) / ((t3 - t0) * (t3 - t1) * (t3 - t2))
    return l0 * p0 + l1 * p1 + l2 * p2 + l3 * p3


def _eval_quadratic_chord_lagrange(p0: Vector, p1: Vector, p2: Vector, t_frac: float, target_segment: int) -> Vector:
    """Evaluate a 3-point chord-length Lagrange quadratic curve.

    target_segment == 1 evaluates between p1 and p2 at t_frac.
    target_segment == 0 evaluates between p0 and p1 at t_frac.
    """
    t0 = 0.0
    t1 = t0 + max((p1 - p0).length, 1e-5)
    t2 = t1 + max((p2 - p1).length, 1e-5)
    t = (t1 + (t2 - t1) * t_frac) if target_segment == 1 else (t0 + (t1 - t0) * t_frac)

    l0 = ((t - t1) * (t - t2)) / ((t0 - t1) * (t0 - t2))
    l1 = ((t - t0) * (t - t2)) / ((t1 - t0) * (t1 - t2))
    l2 = ((t - t0) * (t - t1)) / ((t2 - t0) * (t2 - t1))
    return l0 * p0 + l1 * p1 + l2 * p2


def _find_opposite_edge_at_vert(vert, incoming_edge):
    """Walk one quad-ring outward from `vert` opposite `incoming_edge`."""
    in_faces = set(incoming_edge.link_faces)
    candidates = [
        e for e in vert.link_edges
        if e != incoming_edge and not (set(e.link_faces) & in_faces)
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


class AUES_OT_straighten_line(bpy.types.Operator):
    bl_idname = "aues.straighten_line"
    bl_label = "Straighten (Snap to Line)"
    bl_description = "Align selected vertices onto a straight line between their endpoints (great for character lines & shutlines)"
    bl_options = {'REGISTER', 'UNDO'}

    spacing: bpy.props.EnumProperty(
        name="Spacing",
        description="How interior vertices are positioned along the straight line",
        items=[
            ('PROJECT', "Preserve Position", "Project vertices perpendicularly onto the straight line"),
            ('PROPORTIONAL', "Arc Length", "Preserve relative edge-length ratios along the line"),
            ('EVEN', "Even Spacing", "Distribute vertices evenly along the straight line"),
        ],
        default='PROJECT',
    )
    influence: bpy.props.FloatProperty(
        name="Influence",
        description="Blend factor between original positions and the straightened line",
        min=0.0,
        max=1.0,
        default=1.0,
        subtype='FACTOR',
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        if not objects:
            self.report({'WARNING'}, "No edit mesh objects found")
            return {'CANCELLED'}

        inf = self.influence
        total_moved = 0

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            sel_verts = [v for v in bm.verts if v.select]
            if len(sel_verts) < 3:
                continue

            sel_set = set(sel_verts)

            # Build adjacency from selected edges among selected vertices
            adj = {v: [] for v in sel_verts}
            for e in bm.edges:
                if e.select and e.verts[0] in sel_set and e.verts[1] in sel_set:
                    v0, v1 = e.verts[0], e.verts[1]
                    adj[v0].append(v1)
                    adj[v1].append(v0)

            # Split into connected components so multiple chains straighten independently
            visited = set()
            components = []
            for v in sel_verts:
                if v in visited:
                    continue
                comp = []
                stack = [v]
                visited.add(v)
                while stack:
                    cur = stack.pop()
                    comp.append(cur)
                    for nb in adj[cur]:
                        if nb not in visited:
                            visited.add(nb)
                            stack.append(nb)
                components.append(comp)

            # If vertices are all loose (no selected edges), treat all selected verts as one group
            if all(len(c) == 1 for c in components):
                components = [sel_verts]

            obj_moved = 0
            for comp in components:
                if len(comp) < 3:
                    continue

                # Check if component is a clean open chain (2 endpoints, all interior degree == 2)
                endpoints = [v for v in comp if len(adj[v]) == 1]
                is_open_chain = (
                    len(endpoints) == 2
                    and all(len(adj[v]) in (1, 2) for v in comp)
                )

                if is_open_chain:
                    chain = [endpoints[0]]
                    prev = None
                    cur = endpoints[0]
                    while True:
                        nxts = [nb for nb in adj[cur] if nb != prev]
                        if not nxts:
                            break
                        prev, cur = cur, nxts[0]
                        chain.append(cur)

                    p_start = chain[0].co.copy()
                    p_end = chain[-1].co.copy()
                    line_vec = p_end - p_start
                    line_len = line_vec.length
                    if line_len <= 1e-6:
                        continue
                    line_dir = line_vec / line_len

                    if self.spacing == 'EVEN':
                        denom = len(chain) - 1
                        for idx in range(1, len(chain) - 1):
                            target = p_start.lerp(p_end, idx / denom)
                            chain[idx].co = chain[idx].co.lerp(target, inf)
                            obj_moved += 1
                    elif self.spacing == 'PROPORTIONAL':
                        orig_pts = [v.co.copy() for v in chain]
                        cum = [0.0]
                        for idx in range(1, len(orig_pts)):
                            cum.append(cum[-1] + (orig_pts[idx] - orig_pts[idx - 1]).length)
                        total_arc = cum[-1]
                        if total_arc <= 1e-6:
                            continue
                        for idx in range(1, len(chain) - 1):
                            target = p_start.lerp(p_end, cum[idx] / total_arc)
                            chain[idx].co = orig_pts[idx].lerp(target, inf)
                            obj_moved += 1
                    else:  # 'PROJECT'
                        for idx in range(1, len(chain) - 1):
                            pt = chain[idx].co
                            t = (pt - p_start).dot(line_dir)
                            target = p_start + line_dir * t
                            chain[idx].co = pt.lerp(target, inf)
                            obj_moved += 1
                else:
                    # Fallback for loose vertices or branching selections: farthest pair defines the line
                    p_a = max(comp, key=lambda v: (v.co - comp[0].co).length_squared)
                    p_b = max(comp, key=lambda v: (v.co - p_a.co).length_squared)
                    line_vec = p_b.co - p_a.co
                    line_len = line_vec.length
                    if line_len <= 1e-6:
                        continue
                    p_start = p_a.co.copy()
                    line_dir = line_vec / line_len

                    for v in comp:
                        if v in (p_a, p_b):
                            continue
                        t = (v.co - p_start).dot(line_dir)
                        target = p_start + line_dir * t
                        v.co = v.co.lerp(target, inf)
                        obj_moved += 1

            if obj_moved > 0:
                bm.normal_update()
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
                total_moved += obj_moved

        if total_moved == 0:
            self.report({'WARNING'}, "Select at least 3 vertices (or an open edge chain) to straighten")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Straightened {total_moved} vertex(es)")
        return {'FINISHED'}


class AUES_OT_edge_flow(bpy.types.Operator):
    bl_idname = "aues.edge_flow"
    bl_label = "Edge Flow"
    bl_description = "Reposition selected edge loops to follow surrounding surface curvature (Class-A reflection fairing)"
    bl_options = {'REGISTER', 'UNDO'}

    tension: bpy.props.FloatProperty(
        name="Tension",
        description="Curvature strength (0 = flat midpoint, 1 = natural surrounding curvature)",
        min=-1.0,
        max=2.0,
        default=1.0,
    )
    influence: bpy.props.FloatProperty(
        name="Influence",
        description="Blend factor between original positions and smoothed flow positions",
        min=0.0,
        max=1.0,
        default=1.0,
        subtype='FACTOR',
    )
    iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Number of relaxation passes (useful when fairing multiple parallel loops together)",
        min=1,
        max=10,
        default=1,
    )
    preserve_spacing: bpy.props.BoolProperty(
        name="Preserve Spacing",
        description="Maintain each vertex's original left/right ratio instead of centering between neighbors",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        if not objects:
            self.report({'WARNING'}, "No edit mesh objects found")
            return {'CANCELLED'}

        tension = self.tension
        inf = self.influence
        total_moved = 0

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            sel_edges = [e for e in bm.edges if e.select]
            if not sel_edges:
                continue

            sel_edge_set = set(sel_edges)
            candidate_verts = []
            seen_v = set()
            for e in sel_edges:
                for v in e.verts:
                    if v not in seen_v:
                        seen_v.add(v)
                        candidate_verts.append(v)

            # Precompute perpendicular cross-ribs (v_l1, v_l2, v_r1, v_r2) for each vertex
            rib_entries = []
            for v in candidate_verts:
                # Unselected edges incident to v that belong to faces touching a selected edge at v
                touching_faces = set()
                for e in v.link_edges:
                    if e in sel_edge_set:
                        touching_faces.update(e.link_faces)

                perp_edges = [
                    e for e in v.link_edges
                    if e not in sel_edge_set and (set(e.link_faces) & touching_faces)
                ]
                if len(perp_edges) != 2:
                    continue

                e_l, e_r = perp_edges[0], perp_edges[1]
                v_l1 = e_l.other_vert(v)
                v_r1 = e_r.other_vert(v)
                if v_l1 == v_r1:
                    continue

                e_l2 = _find_opposite_edge_at_vert(v_l1, e_l)
                e_r2 = _find_opposite_edge_at_vert(v_r1, e_r)
                v_l2 = e_l2.other_vert(v_l1) if e_l2 is not None else None
                v_r2 = e_r2.other_vert(v_r1) if e_r2 is not None else None

                # Guard against degenerate self-loops
                if v_l2 in (v, v_r1):
                    v_l2 = None
                if v_r2 in (v, v_l1):
                    v_r2 = None

                rib_entries.append((v, v_l1, v_l2, v_r1, v_r2))

            if not rib_entries:
                continue

            orig_positions = {v: v.co.copy() for v, _, _, _, _ in rib_entries}

            # Compute initial spacing ratio if preserve_spacing is requested
            ratios = {}
            for v, v_l1, _, v_r1, _ in rib_entries:
                if self.preserve_spacing:
                    dl = (v.co - v_l1.co).length
                    dr = (v_r1.co - v.co).length
                    denom = dl + dr
                    r = (dl / denom) if denom > 1e-6 else 0.5
                    ratios[v] = max(0.05, min(0.95, r))
                else:
                    ratios[v] = 0.5

            for _ in range(self.iterations):
                # Snapshot all referenced vertex positions for order-independent update
                snap = {}
                for v, v_l1, v_l2, v_r1, v_r2 in rib_entries:
                    for ref in (v, v_l1, v_l2, v_r1, v_r2):
                        if ref is not None and ref not in snap:
                            snap[ref] = ref.co.copy()

                for v, v_l1, v_l2, v_r1, v_r2 in rib_entries:
                    p1 = snap[v_l1]
                    p2 = snap[v_r1]
                    r = ratios[v]
                    p_linear = p1.lerp(p2, r)

                    if v_l2 is not None and v_r2 is not None:
                        p_curve = _eval_cubic_chord_lagrange(snap[v_l2], p1, p2, snap[v_r2], r)
                    elif v_l2 is not None:
                        p_curve = _eval_quadratic_chord_lagrange(snap[v_l2], p1, p2, r, target_segment=1)
                    elif v_r2 is not None:
                        p_curve = _eval_quadratic_chord_lagrange(p1, p2, snap[v_r2], r, target_segment=0)
                    else:
                        p_curve = p_linear

                    v.co = p_linear + (p_curve - p_linear) * tension

            # Blend final result with original positions by `influence`
            if inf < 1.0:
                for v, orig_co in orig_positions.items():
                    v.co = orig_co.lerp(v.co, inf)

            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            total_moved += len(rib_entries)

        if total_moved == 0:
            self.report({'WARNING'}, "Select an interior edge loop (with adjacent quad faces) to apply Edge Flow")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Edge Flow applied to {total_moved} vertex(es)")
        return {'FINISHED'}


class AUES_OT_flatten_best_fit(bpy.types.Operator):
    bl_idname = "aues.flatten_best_fit"
    bl_label = "Flatten to Plane"
    bl_description = "Project selected vertices onto their average best-fit plane (no external add-on required)"
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.FloatProperty(
        name="Influence",
        description="Blend factor between original positions and flattened plane",
        min=0.0,
        max=1.0,
        default=1.0,
        subtype='FACTOR',
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        world_points = []
        normal_sum = Vector((0.0, 0.0, 0.0))
        face_normal_sum = Vector((0.0, 0.0, 0.0))
        per_obj_data = []

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            sel_verts = [v for v in bm.verts if v.select]
            if not sel_verts:
                continue

            mat = obj.matrix_world
            nmat = mat.to_3x3().inverted_safe().transposed()
            pts = [mat @ v.co for v in sel_verts]
            world_points.extend(pts)

            for f in bm.faces:
                if f.select:
                    face_normal_sum += (nmat @ f.normal).normalized()
            for v in sel_verts:
                normal_sum += (nmat @ v.normal).normalized()

            per_obj_data.append((obj, bm, sel_verts, pts, mat.inverted_safe()))

        if len(world_points) < 3:
            self.report({'WARNING'}, "Select at least 3 vertices to flatten to a plane")
            return {'CANCELLED'}

        centroid = sum(world_points, Vector((0.0, 0.0, 0.0))) / len(world_points)

        if face_normal_sum.length > 1e-5:
            plane_normal = face_normal_sum.normalized()
        elif normal_sum.length > 1e-5:
            plane_normal = normal_sum.normalized()
        else:
            p0 = max(world_points, key=lambda p: (p - centroid).length_squared)
            v0 = p0 - centroid
            p1 = max(world_points, key=lambda p: v0.cross(p - centroid).length_squared)
            cross = v0.cross(p1 - centroid)
            if cross.length <= 1e-6:
                self.report({'WARNING'}, "Selected vertices are collinear; cannot compute plane")
                return {'CANCELLED'}
            plane_normal = cross.normalized()

        inf = self.influence
        for obj, bm, sel_verts, pts, mat_inv in per_obj_data:
            for v, wp in zip(sel_verts, pts):
                dist = (wp - centroid).dot(plane_normal)
                projected = wp - plane_normal * (dist * inf)
                v.co = mat_inv @ projected
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        self.report({'INFO'}, f"Flattened {len(world_points)} vertex(es) to best-fit plane")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Edge Sharpness Operators (Crease, Bevel Weight, Mark Sharp)
# -----------------------------------------------------------------------------

class AUES_OT_set_crease(bpy.types.Operator):
    bl_idname = "aues.set_crease"
    bl_label = "Set Crease"
    bl_description = "Assign Subdivision crease weight to selected edges across active edit meshes"
    bl_options = {'REGISTER', 'UNDO'}

    crease_value: bpy.props.FloatProperty(
        name="Crease Value",
        min=0.0,
        max=1.0,
        default=0.0,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        is_blender_4_plus = bpy.app.version >= (4, 0, 0)
        edges_updated = 0

        for obj in objects:
            me = obj.data
            bm = bmesh.from_edit_mesh(me)

            has_selected = any(e.select for e in bm.edges)
            if not has_selected:
                continue

            if not is_blender_4_plus and hasattr(bm.edges.layers, "crease"):
                crease_layer = bm.edges.layers.crease.verify()
            else:
                crease_layer = bm.edges.layers.float.get('crease_edge')
                if crease_layer is None:
                    if self.crease_value == 0.0:
                        edges_updated += sum(1 for e in bm.edges if e.select)
                        continue
                    crease_layer = bm.edges.layers.float.new('crease_edge')

            # Iterate bm.edges AFTER layer creation (creating a layer reallocates BMEdge data)
            count = 0
            for edge in bm.edges:
                if edge.select:
                    edge[crease_layer] = self.crease_value
                    count += 1

            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
            edges_updated += count

        if edges_updated == 0:
            self.report({'INFO'}, "No edges selected")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Crease {self.crease_value:g} applied to {edges_updated} edge(s)")
        return {'FINISHED'}


class AUES_OT_set_bevel_weight(bpy.types.Operator):
    bl_idname = "aues.set_bevel_weight"
    bl_label = "Set Bevel Weight"
    bl_description = "Assign Bevel modifier edge weight to selected edges across active edit meshes"
    bl_options = {'REGISTER', 'UNDO'}

    weight_value: bpy.props.FloatProperty(
        name="Bevel Weight",
        min=0.0,
        max=1.0,
        default=1.0,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        is_blender_4_plus = bpy.app.version >= (4, 0, 0)
        edges_updated = 0

        for obj in objects:
            me = obj.data
            bm = bmesh.from_edit_mesh(me)

            has_selected = any(e.select for e in bm.edges)
            if not has_selected:
                continue

            if not is_blender_4_plus and hasattr(bm.edges.layers, "bevel_weight"):
                bw_layer = bm.edges.layers.bevel_weight.verify()
            else:
                bw_layer = bm.edges.layers.float.get('bevel_weight_edge')
                if bw_layer is None:
                    if self.weight_value == 0.0:
                        edges_updated += sum(1 for e in bm.edges if e.select)
                        continue
                    bw_layer = bm.edges.layers.float.new('bevel_weight_edge')

            count = 0
            for edge in bm.edges:
                if edge.select:
                    edge[bw_layer] = self.weight_value
                    count += 1

            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
            edges_updated += count

        if edges_updated == 0:
            self.report({'INFO'}, "No edges selected")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Bevel weight {self.weight_value:g} applied to {edges_updated} edge(s)")
        return {'FINISHED'}


class AUES_OT_set_sharp(bpy.types.Operator):
    bl_idname = "aues.set_sharp"
    bl_label = "Set Edge Sharp"
    bl_description = "Mark or clear sharp shading flag on selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    sharp: bpy.props.BoolProperty(
        name="Sharp",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        objects = _get_edit_mesh_objects(context)
        edges_updated = 0

        for obj in objects:
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            selected_edges = [e for e in bm.edges if e.select]
            if not selected_edges:
                continue
            for edge in selected_edges:
                edge.smooth = not self.sharp
            bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
            edges_updated += len(selected_edges)

        if edges_updated == 0:
            self.report({'INFO'}, "No edges selected")
            return {'CANCELLED'}

        action = "Marked sharp" if self.sharp else "Cleared sharp"
        self.report({'INFO'}, f"{action} on {edges_updated} edge(s)")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Quick Modifier Operators
# -----------------------------------------------------------------------------

class AUES_OT_add_modifier(bpy.types.Operator):
    bl_idname = "aues.add_modifier"
    bl_label = "Add Modifier"
    bl_description = "Add the assigned modifier to selected object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    mod_type: bpy.props.StringProperty(
        name="Modifier Type",
        default="",
    )

    @classmethod
    def description(cls, context, properties):
        mtype = getattr(properties, "mod_type", "")
        if not mtype:
            return "No modifier assigned to this slot"
        mname, _ = get_modifier_info(mtype)
        if mname is None:
            return f"Unavailable: Modifier '{mtype}' is not supported in this Blender version"
        return f"Add {mname} modifier to selected object(s)"

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects or context.active_object)

    def execute(self, context):
        if not self.mod_type:
            self.report({'WARNING'}, "No modifier assigned to this slot")
            return {'CANCELLED'}

        mname, _ = get_modifier_info(self.mod_type)
        if mname is None:
            self.report({'WARNING'}, f"Modifier '{self.mod_type}' is unavailable in this Blender version")
            return {'CANCELLED'}

        prefs = get_prefs(context)
        use_presets = prefs.mod_smart_defaults if prefs else True

        targets = list(context.selected_objects)
        if context.active_object and context.active_object not in targets:
            targets.append(context.active_object)

        added = 0
        for obj in targets:
            if not hasattr(obj, "modifiers"):
                continue
            try:
                mod = obj.modifiers.new(name=mname, type=self.mod_type)
                if mod is not None:
                    if use_presets:
                        _apply_automotive_modifier_preset(mod)
                    added += 1
            except (RuntimeError, TypeError):
                continue

        if added == 0:
            self.report({'WARNING'}, f"Could not add '{mname}' to the selected object type(s)")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Added {mname} to {added} object(s)")
        return {'FINISHED'}


class AUES_OT_reset_modifier_defaults(bpy.types.Operator):
    bl_idname = "aues.reset_modifier_defaults"
    bl_label = "Reset Modifier Defaults"
    bl_description = "Reset all 6 Quick Modifier slots to automotive defaults"

    def execute(self, context):
        prefs = get_prefs(context)
        if prefs is None:
            return {'CANCELLED'}
        populate_default_modifiers(prefs, force=True)
        self.report({'INFO'}, "Quick Modifier slots reset to automotive defaults")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Viewport Shading, MatCap & Inspection Operators
# -----------------------------------------------------------------------------

class AUES_OT_set_matcap(bpy.types.Operator):
    bl_idname = "aues.set_matcap"
    bl_label = "Set MatCap"
    bl_description = "Switch 3D Viewport to Solid MatCap shading (Shift+Click to apply to all 3D Viewports)"

    matcap_name: bpy.props.StringProperty()
    apply_all: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        fname = getattr(properties, "matcap_name", "")
        if not fname:
            return "No MatCap assigned to this slot"
        if not is_matcap_installed(fname, context):
            return f"Unavailable: MatCap '{fname}' is saved in this .blend file but not installed in Blender"
        return f"Apply MatCap '{fname}' (Shift+Click to apply to all 3D Viewports)"

    def invoke(self, context, event):
        props = getattr(context.scene, "aues_props", None)
        prefs = get_prefs(context)
        if props is not None and props.matcap_initialized:
            default_all = props.matcap_apply_all_viewports
        else:
            default_all = prefs.matcap_apply_all_viewports if prefs else False
        self.apply_all = bool(event.shift) or default_all
        return self.execute(context)

    def execute(self, context):
        if not self.matcap_name:
            self.report({'WARNING'}, "No MatCap assigned to this slot")
            return {'CANCELLED'}

        if not is_matcap_installed(self.matcap_name, context):
            self.report({'WARNING'}, f"MatCap '{self.matcap_name}' is not installed (Unavailable)")
            return {'CANCELLED'}

        target_spaces = []
        if not self.apply_all and context.space_data and context.space_data.type == 'VIEW_3D':
            target_spaces.append(context.space_data)
        else:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            target_spaces.append(space)

        if not target_spaces:
            self.report({'WARNING'}, "No 3D Viewport found")
            return {'CANCELLED'}

        for space in target_spaces:
            space.shading.type = 'SOLID'
            space.shading.light = 'MATCAP'
            try:
                space.shading.studio_light = self.matcap_name
            except TypeError:
                self.report({'WARNING'}, f"MatCap '{self.matcap_name}' is not installed (Unavailable)")
                return {'CANCELLED'}

        return {'FINISHED'}


class AUES_OT_flip_matcap(bpy.types.Operator):
    bl_idname = "aues.flip_matcap"
    bl_label = "Flip MatCap"
    bl_description = "Flip MatCap reflection horizontally (Shift+Click to swap Horizontal/Vertical Zebra)"

    swap_zebra: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.space_data is not None and context.space_data.type == 'VIEW_3D'

    def invoke(self, context, event):
        self.swap_zebra = bool(event.shift)
        return self.execute(context)

    def execute(self, context):
        shading = context.space_data.shading
        if self.swap_zebra:
            installed = set(get_installed_matcaps(context))
            h_names = ("check_reflection_horizontal.exr", "reflection_check_horizontal.exr")
            v_names = ("check_reflection_vertical.exr", "reflection_check_vertical.exr")
            h_matcap = next((n for n in h_names if n in installed), None)
            v_matcap = next((n for n in v_names if n in installed), None)

            if h_matcap and v_matcap:
                shading.type = 'SOLID'
                shading.light = 'MATCAP'
                target = v_matcap if shading.studio_light == h_matcap else h_matcap
                shading.studio_light = target
                return {'FINISHED'}

        if shading.type != 'SOLID' or shading.light != 'MATCAP':
            shading.type = 'SOLID'
            shading.light = 'MATCAP'

        if has_operator("view3d", "toggle_matcap_flip"):
            bpy.ops.view3d.toggle_matcap_flip()
        else:
            shading.studiolight_rotate_z = (shading.studiolight_rotate_z + 3.14159265) % 6.2831853
        return {'FINISHED'}


class AUES_OT_reset_matcap_defaults(bpy.types.Operator):
    bl_idname = "aues.reset_matcap_defaults"
    bl_label = "Reset MatCap Defaults"
    bl_description = "Reset MatCap slots to automotive defaults"

    target: bpy.props.EnumProperty(
        name="Target",
        items=[
            ('SCENE', "Current .blend Scene", "Reset this .blend file's MatCap slots"),
            ('PREFS', "Global Preferences", "Reset global default MatCap slots"),
        ],
        default='SCENE',
    )

    def execute(self, context):
        if self.target == 'PREFS':
            prefs = get_prefs(context)
            if prefs is None:
                return {'CANCELLED'}
            populate_default_matcaps(prefs, force=True)
            self.report({'INFO'}, "Global default MatCap slots reset")
            return {'FINISHED'}

        props = getattr(context.scene, "aues_props", None)
        if props is None:
            return {'CANCELLED'}
        populate_default_matcaps(props, force=True)
        self.report({'INFO'}, "Scene MatCap slots reset to automotive defaults")
        return {'FINISHED'}


class AUES_OT_sync_matcap_prefs(bpy.types.Operator):
    bl_idname = "aues.sync_matcap_prefs"
    bl_label = "Sync MatCap Slots"
    bl_description = "Copy MatCap slots between the current .blend file and global preferences"

    direction: bpy.props.EnumProperty(
        name="Direction",
        items=[
            ('SCENE_TO_PREFS', "Save as Global Default", "Save this .blend file's MatCap slots as the global default for new files"),
            ('PREFS_TO_SCENE', "Load Global Defaults", "Load global default MatCap slots into this .blend file"),
        ],
        default='SCENE_TO_PREFS',
    )

    def execute(self, context):
        prefs = get_prefs(context)
        scene = context.scene
        if prefs is None or scene is None or not hasattr(scene, "aues_props"):
            return {'CANCELLED'}

        props = scene.aues_props
        if self.direction == 'SCENE_TO_PREFS':
            ensure_scene_matcaps(scene, prefs)
            copy_matcap_settings(props, prefs)
            self.report({'INFO'}, "Saved current .blend MatCap slots as global default")
        else:
            populate_default_matcaps(prefs, force=False)
            copy_matcap_settings(prefs, props)
            self.report({'INFO'}, "Loaded global default MatCap slots into current .blend file")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Viewport Screenshot Operators
# -----------------------------------------------------------------------------

class AUES_OT_take_screenshot(bpy.types.Operator, ExportHelper):
    bl_idname = "aues.take_screenshot"
    bl_label = "Save Screenshot"
    bl_description = "Save a clean 3D Viewport snapshot to a chosen PNG file"

    filename_ext = ".png"
    filter_glob: bpy.props.StringProperty(
        default="*.png",
        options={'HIDDEN'},
        maxlen=255,
    )
    capture_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('OPENGL', "Viewport Render (Clean)", "Anti-aliased OpenGL viewport render without UI"),
            ('AREA', "Area Capture (Fast)", "Direct 3D Viewport area pixel capture"),
        ],
        default='OPENGL',
    )
    hide_overlays: bpy.props.BoolProperty(name="Hide Overlays", default=True)
    hide_gizmos: bpy.props.BoolProperty(name="Hide Gizmos", default=True)
    hide_ui: bpy.props.BoolProperty(name="Hide UI (Area Mode)", default=True)
    transparent_bg: bpy.props.BoolProperty(name="Transparent BG (Render Mode)", default=False)

    def invoke(self, context, event):
        prefs = get_prefs(context)
        if prefs:
            self.capture_mode = prefs.screenshot_mode
            self.hide_overlays = prefs.screenshot_hide_overlays
            self.hide_gizmos = prefs.screenshot_hide_gizmos
            self.hide_ui = prefs.screenshot_hide_ui
            self.transparent_bg = prefs.screenshot_transparent_bg

        base_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0] if bpy.data.filepath else "viewport"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = _resolve_quick_save_dir(prefs.screenshot_dir) if prefs else tempfile.gettempdir()
        self.filepath = os.path.join(default_dir, f"{base_name}_{stamp}.png")
        return super().invoke(context, event)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "capture_mode")
        layout.prop(self, "hide_overlays")
        layout.prop(self, "hide_gizmos")
        if self.capture_mode == 'AREA':
            layout.prop(self, "hide_ui")
        else:
            layout.prop(self, "transparent_bg")

    def execute(self, context):
        space = context.space_data
        area = context.area
        if not space or space.type != 'VIEW_3D':
            view3d_areas = [a for a in context.screen.areas if a.type == 'VIEW_3D']
            if not view3d_areas:
                self.report({'ERROR'}, "No 3D Viewport found")
                return {'CANCELLED'}
            area = max(view3d_areas, key=lambda a: a.width * a.height)
            space = area.spaces.active

        filepath = self.filepath
        out_dir = os.path.dirname(filepath)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if self.capture_mode == 'OPENGL':
            try:
                _run_opengl_capture(
                    context, area, space, filepath,
                    self.hide_overlays, self.hide_gizmos, self.transparent_bg,
                )
            except Exception as exc:
                self.report({'ERROR'}, f"Viewport render failed: {exc}")
                return {'CANCELLED'}
            self.report({'INFO'}, f"Snapshot saved: {filepath}")
        else:
            _run_area_capture(
                context, area, space, filepath,
                self.hide_overlays, self.hide_gizmos, self.hide_ui,
                delay=0.15,
            )
            self.report({'INFO'}, f"Area capture queued: {filepath}")

        return {'FINISHED'}


class AUES_OT_quick_screenshot(bpy.types.Operator):
    bl_idname = "aues.quick_screenshot"
    bl_label = "Quick Save"
    bl_description = "1-click auto-numbered viewport snapshot saved directly to your configured folder"

    @classmethod
    def poll(cls, context):
        return context.space_data is not None and context.space_data.type == 'VIEW_3D'

    def execute(self, context):
        prefs = get_prefs(context)
        mode = prefs.screenshot_mode if prefs else 'OPENGL'
        raw_dir = prefs.screenshot_dir if prefs else "//aues_screenshots/"
        prefix = prefs.screenshot_prefix if prefs else "AUES_shot"
        hide_overlays = prefs.screenshot_hide_overlays if prefs else True
        hide_gizmos = prefs.screenshot_hide_gizmos if prefs else True
        hide_ui = prefs.screenshot_hide_ui if prefs else True
        transparent_bg = prefs.screenshot_transparent_bg if prefs else False

        out_dir = _resolve_quick_save_dir(raw_dir)
        filepath = _next_numbered_filepath(out_dir, prefix)

        if mode == 'OPENGL':
            try:
                _run_opengl_capture(
                    context, context.area, context.space_data, filepath,
                    hide_overlays, hide_gizmos, transparent_bg,
                )
            except Exception as exc:
                self.report({'ERROR'}, f"Quick snapshot failed: {exc}")
                return {'CANCELLED'}
            self.report({'INFO'}, f"Saved: {filepath}")
        else:
            _run_area_capture(
                context, context.area, context.space_data, filepath,
                hide_overlays, hide_gizmos, hide_ui,
                delay=0.05,
            )
            self.report({'INFO'}, f"Saved: {filepath}")

        return {'FINISHED'}


CLASSES = (
    AUES_OT_enable_looptools,
    AUES_OT_gstretch,
    AUES_OT_flatten_axis,
    AUES_OT_straighten_line,
    AUES_OT_edge_flow,
    AUES_OT_flatten_best_fit,
    AUES_OT_set_crease,
    AUES_OT_set_bevel_weight,
    AUES_OT_set_sharp,
    AUES_OT_add_modifier,
    AUES_OT_reset_modifier_defaults,
    AUES_OT_set_matcap,
    AUES_OT_flip_matcap,
    AUES_OT_reset_matcap_defaults,
    AUES_OT_sync_matcap_prefs,
    AUES_OT_take_screenshot,
    AUES_OT_quick_screenshot,
)
