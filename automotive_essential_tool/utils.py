"""Shared helper utilities for Automotive Essential Tool (AUES)."""

import os
import addon_utils
import bpy


# Module-level caches & permanent string pool required by Blender to prevent
# dynamic EnumProperty C-strings from being garbage-collected when multiple
# dropdowns draw in the same UI frame.
_ENUM_STR_POOL = {}
_MATCAP_ITEMS_CACHE_KEY = None
_MATCAP_ITEMS_CACHE = []
_MODIFIER_ITEMS_CACHE_KEY = None
_MODIFIER_ITEMS_CACHE = []


def _intern(text: str) -> str:
    """Keep a permanent Python reference to strings returned to Blender's C EnumProperty."""
    existing = _ENUM_STR_POOL.get(text)
    if existing is None:
        _ENUM_STR_POOL[text] = text
        return text
    return existing

# Candidate built-in matcaps across Blender 3.x / 4.x / 5.x for smart defaults
_DEFAULT_SLOT_CANDIDATES = (
    (("basic_side.exr", "basic_grey.exr", "basic_1.exr", "clay_studio.exr"), "Clay"),
    (("metal_carpaint.exr", "hard_surface_red.exr", "ceramic_dark.exr"), "Carpaint"),
    (("check_reflection_horizontal.exr", "reflection_check_horizontal.exr"), "Zebra H"),
    (("check_reflection_vertical.exr", "reflection_check_vertical.exr"), "Zebra V"),
    (("hard_surface_grey.exr", "clay_studio.exr", "basic_dark.exr"), "Hard Surf"),
    (("check_rim_light.exr", "check_rim_dark.exr", "basic_bright.exr"), "Rim"),
)

_SHORT_LABEL_REPLACEMENTS = (
    ("Check Reflection Horizontal", "Zebra H"),
    ("Check Reflection Vertical", "Zebra V"),
    ("Reflection Check Horizontal", "Zebra H"),
    ("Reflection Check Vertical", "Zebra V"),
    ("Hard Surface ", "HS "),
    ("Metal Carpaint", "Carpaint"),
)

# Modifiers that cannot be added to Mesh objects (Grease Pencil & Volume-only)
_NON_MESH_MODIFIERS = frozenset({
    "LINEART",
    "MESH_TO_VOLUME",
    "VOLUME_DISPLACE",
})

# Default 6 automotive modeling modifiers
_DEFAULT_MODIFIER_SLOTS = (
    ("MIRROR", "Mirror"),
    ("SUBSURF", "SubD"),
    ("SOLIDIFY", "Solidify"),
    ("BEVEL", "Bevel"),
    ("WEIGHTED_NORMAL", "W.Normal"),
    ("SHRINKWRAP", "Shrink"),
)

_MODIFIER_SHORT_LABELS = {
    "SUBSURF": "SubD",
    "WEIGHTED_NORMAL": "W.Normal",
    "SHRINKWRAP": "Shrink",
    "SIMPLE_DEFORM": "Deform",
    "SURFACE_DEFORM": "SurfDef",
    "DATA_TRANSFER": "DataXfer",
    "EDGE_SPLIT": "EdgeSplit",
    "MULTIRES": "MultiRes",
    "NODES": "GeoNodes",
    "CORRECTIVE_SMOOTH": "CorrSmth",
    "LAPLACIANSMOOTH": "LapSmth",
    "LAPLACIANDEFORM": "LapDef",
    "PARTICLE_SYSTEM": "Particles",
    "PARTICLE_INSTANCE": "PartInst",
    "MESH_SEQUENCE_CACHE": "SeqCache",
    "VERTEX_WEIGHT_EDIT": "VW Edit",
    "VERTEX_WEIGHT_MIX": "VW Mix",
    "VERTEX_WEIGHT_PROXIMITY": "VW Prox",
}


def get_addon_id():
    """Return the package/module identifier used for AddonPreferences lookup."""
    return __package__ or __name__


def get_prefs(context=None):
    """Safely fetch AUES AddonPreferences regardless of Extension vs legacy install."""
    ctx = context or bpy.context
    if ctx is None or not hasattr(ctx, "preferences"):
        return None
    addon = ctx.preferences.addons.get(get_addon_id())
    return addon.preferences if addon else None


def has_operator(module_name: str, op_name: str) -> bool:
    """Accurately check whether a Blender operator is currently registered.

    NOTE: hasattr(bpy.ops.<mod>, <op>) always returns True due to bpy.ops proxy
    behavior; checking dir() avoids false positives across all Blender versions.
    """
    submod = getattr(bpy.ops, module_name, None)
    if submod is None:
        return False
    return op_name in dir(submod)


def is_looptools_available() -> bool:
    """Return True if LoopTools operators are registered and callable."""
    return has_operator("mesh", "looptools_relax")


def find_looptools_module():
    """Locate the installed LoopTools module name (Extension or legacy add-on)."""
    candidates = []
    try:
        for mod in addon_utils.modules():
            mod_name = getattr(mod, "__name__", "")
            if mod_name == "mesh_looptools" or mod_name.endswith(".looptools"):
                candidates.append(mod_name)
    except Exception:
        pass

    # Prefer Extensions (bl_ext.*) over legacy module names on Blender 4.2+
    for name in candidates:
        if name.startswith("bl_ext."):
            return name
    return candidates[0] if candidates else None


# -----------------------------------------------------------------------------
# MatCap Helpers
# -----------------------------------------------------------------------------

def get_installed_matcaps(context=None):
    """Return a list of installed MatCap studio light filenames."""
    ctx = context or bpy.context
    names = []
    try:
        prefs = getattr(ctx, "preferences", None)
        studio_lights = getattr(prefs, "studio_lights", None)
        if studio_lights:
            for sl in studio_lights:
                if getattr(sl, "type", "") == 'MATCAP':
                    names.append(sl.name)
    except Exception:
        pass
    return names


def is_matcap_installed(matcap_name: str, context=None, installed_set=None) -> bool:
    """Return True if the given MatCap filename is installed in Blender."""
    if not matcap_name:
        return False
    if installed_set is None:
        installed_set = set(get_installed_matcaps(context))
    return matcap_name in installed_set


def format_matcap_label(name: str, custom_label: str = "") -> str:
    """Format a matcap filename (or custom alias) into a clean button label."""
    if custom_label and custom_label.strip():
        return custom_label.strip()
    if not name:
        return "None"
    clean = os.path.splitext(name)[0].replace("_", " ").strip().title()
    for src, dst in _SHORT_LABEL_REPLACEMENTS:
        if clean.startswith(src) or clean == src:
            clean = clean.replace(src, dst)
    return clean


def get_matcap_enum_items(self, context):
    """Cached dynamic EnumProperty item generator for MatCap dropdown selectors.

    Includes any saved-but-uninstalled MatCap filenames referenced by `self`
    marked clearly as '[Unavailable]' so opening a .blend file on another PC
    never silently overwrites missing MatCap references.
    """
    global _MATCAP_ITEMS_CACHE, _MATCAP_ITEMS_CACHE_KEY

    installed = tuple(get_installed_matcaps(context))
    installed_set = set(installed)

    missing = []
    if self is not None:
        seen_m = set()
        for slot_i in range(1, 7):
            fname = getattr(self, f"matcap_file_{slot_i}", "")
            if fname and fname not in installed_set and fname not in seen_m:
                missing.append(fname)
                seen_m.add(fname)

    cache_key = (installed, tuple(missing))
    if cache_key == _MATCAP_ITEMS_CACHE_KEY and _MATCAP_ITEMS_CACHE:
        return _MATCAP_ITEMS_CACHE

    items = []
    seen = set()

    for idx, name in enumerate(installed):
        label = format_matcap_label(name)
        items.append((_intern(name), _intern(label), _intern(name), 'SHADING_RENDERED', idx))
        seen.add(name)

    if not items:
        fallback = (
            ("basic_side.exr", "Basic Side"),
            ("metal_carpaint.exr", "Carpaint"),
            ("check_reflection_horizontal.exr", "Zebra H"),
        )
        for idx, (name, label) in enumerate(fallback):
            items.append((_intern(name), _intern(label), _intern("Fallback MatCap"), 'SHADING_RENDERED', idx))
            seen.add(name)

    next_idx = len(items)
    for fname in missing:
        if fname not in seen:
            label = format_matcap_label(fname)
            items.append((
                _intern(fname),
                _intern(f"[Unavailable] {label}"),
                _intern(f"MatCap '{fname}' is not installed in this Blender"),
                'ERROR',
                next_idx,
            ))
            seen.add(fname)
            next_idx += 1

    _MATCAP_ITEMS_CACHE_KEY = cache_key
    _MATCAP_ITEMS_CACHE = items
    return _MATCAP_ITEMS_CACHE


def resolve_default_matcap_slots(context=None):
    """Return 6 (filename, label) defaults matching currently available MatCaps."""
    installed = get_installed_matcaps(context)
    installed_set = set(installed)
    fallback_first = installed[0] if installed else "basic_side.exr"

    resolved = []
    for candidates, default_label in _DEFAULT_SLOT_CANDIDATES:
        chosen = None
        for cand in candidates:
            if cand in installed_set:
                chosen = cand
                break
        if chosen is None:
            chosen = fallback_first
            resolved.append((chosen, ""))
        else:
            resolved.append((chosen, default_label))
    return resolved


# -----------------------------------------------------------------------------
# Quick Modifier Helpers
# -----------------------------------------------------------------------------

def get_mesh_modifier_defs():
    """Return sorted list of (identifier, name, description, icon) for mesh-valid modifiers."""
    defs = []
    try:
        enum_items = bpy.types.Modifier.bl_rna.properties['type'].enum_items
        for item in enum_items:
            ident = item.identifier
            if ident.startswith("GREASE_PENCIL_") or ident in _NON_MESH_MODIFIERS:
                continue
            icon = item.icon if item.icon and item.icon != 'NONE' else 'MODIFIER'
            defs.append((ident, item.name, item.description or item.name, icon))
    except Exception:
        pass
    defs.sort(key=lambda entry: entry[1].lower())
    return defs


def get_modifier_info(mod_type: str):
    """Return (display_name, icon) for a modifier type identifier, or (None, 'ERROR') if unavailable."""
    if not mod_type:
        return (None, 'NONE')
    try:
        enum_items = bpy.types.Modifier.bl_rna.properties['type'].enum_items
        item = enum_items.get(mod_type)
        if item is not None:
            icon = item.icon if item.icon and item.icon != 'NONE' else 'MODIFIER'
            return (item.name, icon)
    except Exception:
        pass
    return (None, 'ERROR')


def format_modifier_label(mod_type: str, custom_label: str = "") -> str:
    """Format a modifier type (or custom alias) into a clean button label."""
    if custom_label and custom_label.strip():
        return custom_label.strip()
    if not mod_type:
        return "None"
    if mod_type in _MODIFIER_SHORT_LABELS:
        return _MODIFIER_SHORT_LABELS[mod_type]
    name, _ = get_modifier_info(mod_type)
    if name:
        return name
    return mod_type.replace("_", " ").title()


def get_modifier_enum_items(self, context):
    """Cached dynamic EnumProperty item generator for Quick Modifier slot pickers."""
    global _MODIFIER_ITEMS_CACHE, _MODIFIER_ITEMS_CACHE_KEY

    defs = tuple(get_mesh_modifier_defs())
    def_ids = {d[0] for d in defs}

    missing = []
    if self is not None:
        seen_m = set()
        for slot_i in range(1, 7):
            mtype = getattr(self, f"mod_type_{slot_i}", "")
            if mtype and mtype not in def_ids and mtype not in seen_m:
                missing.append(mtype)
                seen_m.add(mtype)

    cache_key = (tuple(d[0] for d in defs), tuple(missing))
    if cache_key == _MODIFIER_ITEMS_CACHE_KEY and _MODIFIER_ITEMS_CACHE:
        return _MODIFIER_ITEMS_CACHE

    items = []
    seen = set()

    for idx, (ident, name, desc, icon) in enumerate(defs):
        items.append((_intern(ident), _intern(name), _intern(desc), icon, idx))
        seen.add(ident)

    if not items:
        fallback = (
            ("MIRROR", "Mirror", "Mirror modifier", 'MOD_MIRROR'),
            ("SUBSURF", "Subdivision Surface", "Subdivision Surface modifier", 'MOD_SUBSURF'),
            ("SOLIDIFY", "Solidify", "Solidify modifier", 'MOD_SOLIDIFY'),
            ("BEVEL", "Bevel", "Bevel modifier", 'MOD_BEVEL'),
        )
        for idx, (ident, name, desc, icon) in enumerate(fallback):
            items.append((_intern(ident), _intern(name), _intern(desc), icon, idx))
            seen.add(ident)

    next_idx = len(items)
    for mtype in missing:
        if mtype not in seen:
            items.append((
                _intern(mtype),
                _intern(f"[Unavailable] {format_modifier_label(mtype)}"),
                _intern(f"Modifier '{mtype}' is not available in this Blender version"),
                'ERROR',
                next_idx,
            ))
            seen.add(mtype)
            next_idx += 1

    _MODIFIER_ITEMS_CACHE_KEY = cache_key
    _MODIFIER_ITEMS_CACHE = items
    return _MODIFIER_ITEMS_CACHE


def resolve_default_modifier_slots():
    """Return 6 (mod_type, label) automotive defaults verified against installed modifiers."""
    available = {ident for ident, _, _, _ in get_mesh_modifier_defs()}
    fallback = "MIRROR" if (not available or "MIRROR" in available) else next(iter(available))

    resolved = []
    for mod_type, short_lbl in _DEFAULT_MODIFIER_SLOTS:
        if not available or mod_type in available:
            resolved.append((mod_type, short_lbl))
        else:
            resolved.append((fallback, ""))
    return resolved


# -----------------------------------------------------------------------------
# Viewport Helpers
# -----------------------------------------------------------------------------

def find_window_region(area):
    """Return the primary 'WINDOW' region for a given Blender area."""
    if area is None:
        return None
    for region in area.regions:
        if region.type == 'WINDOW':
            return region
    return None
