"""Automotive Essential Tool (AUES) v2.1 - Blender Extension."""

import bpy
from bpy.app.handlers import persistent

from . import operators, preferences, ui
from .preferences import (
    AUES_AddonPreferences,
    AUES_SceneProperties,
    ensure_scene_matcaps,
    populate_default_matcaps,
    populate_default_modifiers,
)
from .utils import get_prefs


_CLASSES = (
    AUES_SceneProperties,
    AUES_AddonPreferences,
    *operators.CLASSES,
    *ui.CLASSES,
)

_ADDON_KEYMAPS = []


def _initialize_defaults():
    """Populate global preference defaults and seed any uninitialized scenes."""
    prefs = get_prefs(bpy.context)
    if prefs is not None:
        populate_default_matcaps(prefs, force=False)
        populate_default_modifiers(prefs, force=False)
    scenes = getattr(bpy.data, "scenes", None)
    if scenes is None:
        return False
    for scene in scenes:
        ensure_scene_matcaps(scene, prefs)
    return prefs is not None


def _ensure_defaults_deferred():
    """Deferred initialization once preferences and studio_lights are ready."""
    try:
        _initialize_defaults()
    except Exception:
        pass
    return None


@persistent
def _on_load_post(_dummy):
    """Preserve saved .blend MatCap settings; seed uninitialized scenes from defaults."""
    try:
        _initialize_defaults()
    except Exception:
        pass


@persistent
def _on_save_pre(_dummy):
    """Ensure every scene persists its MatCap slot configuration inside the .blend file."""
    try:
        _initialize_defaults()
    except Exception:
        pass


def _register_keymaps():
    wm = getattr(bpy.context, "window_manager", None)
    kc = wm.keyconfigs.addon if wm else None
    if kc is None:
        return

    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    kmi = km.keymap_items.new(
        "wm.call_menu_pie",
        type='A',
        value='PRESS',
        alt=True,
        shift=True,
    )
    kmi.properties.name = "AUES_MT_pie_menu"
    _ADDON_KEYMAPS.append((km, kmi))


def _unregister_keymaps():
    for km, kmi in _ADDON_KEYMAPS:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _ADDON_KEYMAPS.clear()


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Scene.aues_props = bpy.props.PointerProperty(type=AUES_SceneProperties)

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    if _on_save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_on_save_pre)

    if not _initialize_defaults():
        bpy.app.timers.register(_ensure_defaults_deferred, first_interval=0.2)

    _register_keymaps()


def unregister():
    _unregister_keymaps()

    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    if _on_save_pre in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(_on_save_pre)

    if hasattr(bpy.types.Scene, "aues_props"):
        del bpy.types.Scene.aues_props

    for cls in reversed(_CLASSES):
        if getattr(cls, "is_registered", False):
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError:
                pass
