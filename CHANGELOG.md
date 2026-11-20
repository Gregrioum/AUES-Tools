# Changelog

All notable changes to **Automotive Essential Tool (AUES)** are documented here.

---

## [2.1.0] - 2026-11-20

### Added
- **Straighten / Snap to Line (`aues.straighten_line`)**: Aligns selected vertices onto a straight line between their endpoints (handles multiple disconnected edge chains independently and loose vertex selections), with F9 Redo controls for `Spacing` (`Preserve Position`, `Arc Length`, `Even Spacing`) and `Influence`.
- **Edge Flow (`aues.edge_flow`)**: Repositions selected interior edge loops along a 4-point chord-length cubic spline (with 3-point boundary fallback) derived from surrounding quad rings for Class-A curvature fairing, with F9 Redo controls for `Tension`, `Influence`, `Iterations`, and `Preserve Spacing`. Also added to the South-West Pie Menu slot.
- **Inline Personalized Quick Modifiers**: Customizable 1–6 modifier button slots (matching the MatCap slot workflow) supporting all 55 mesh-compatible Blender modifiers, official modifier icons, custom short labels, and optional **Automotive Modifier Presets** (`Mirror`, `SubD`, `Solidify`, `Bevel`, `W.Normal`, `Shrinkwrap`).
- **Per-`.blend` MatCap Persistence**: Active MatCap slot configuration is now saved inside each `.blend` file (via `Scene.aues_props` + persistent `load_post`/`save_pre` handlers), with one-click **Save Global** / **Load Global** (`aues.sync_matcap_prefs`) sync to Add-on Preferences.
- **Unavailable MatCap Marking**: Saved MatCaps not installed on the current workstation are automatically disabled and marked with an error icon and `(Unavailable)` label in the button grid, preserved as `[Unavailable]` in the Edit Slots dropdown without overwriting the saved filename.

### Changed
- Renamed **Quick MatCaps** section to **Quick Surface** and moved the Surface Inspection Strip (`Overlays`, `Wireframe`, `Face Orientation`, `Cavity`, `Backface`) directly above the MatCap selector.
- Hardened startup registration against Blender's `_RestrictData` / `_RestrictContext` during automatic extension loading.
- Added permanent string interning (`_ENUM_STR_POOL`) and key-memoized EnumProperty caches so drawing multiple dynamic MatCap/Modifier dropdowns in the same frame never triggers Blender's C-string garbage-collection corruption.

### Removed
- Removed `X = 0` (`to_zero`) centerline snap from `aues.flatten_axis`, the N-Panel, and the Pie Menu.
- Removed the contextual Subdivision level switcher (`aues.set_subsurf_level`) from the Quick Surface section.

---

## [2.0.0] - 2026-11-20

### Added
- Migrated from a legacy single-file script to a validated modular **Blender 4.2+ / 5.x Extension** (`blender_manifest.toml`, `__init__.py`, `utils.py`, `preferences.py`, `operators.py`, `ui.py`) namespaced under `aues.*` / `AUES_*`.
- Restored native **F9 Redo Panel** parameters for LoopTools (`Relax`, `Space`, `GStretch`) and added `Curve` & `Circle`.
- Exposed Flatten Orientation selector (`Active / Global / Local / Normal / View`) and added self-contained **Flatten to Plane** (`aues.flatten_best_fit`).
- Expanded Crease presets to `0 | .25 | .5 | .75 | 1` with Crease Overlay toggle, plus **Sharp / Clear** and **BW 0 / BW 1** Bevel Weight controls.
- Added **Flip MatCap** (`Shift+Click` swaps Zebra H/V), Surface Inspection Strip, **Clean OpenGL Viewport Render** snapshot mode, **1-Click Quick Save**, and **AUES Quick Pie** (`Alt + Shift + A`).

### Fixed
- Accurate `dir()` LoopTools detection and Blender 4.2+ Extension (`bl_ext.*.looptools`) auto-discovery.
- Cached dynamic `EnumProperty` items (`_MATCAP_ITEMS_CACHE`) to prevent Blender string GC corruption.
- Blender 5.2 clean `PropertyGroup` unregistration via `getattr(cls, "is_registered", False)`.
- Explicit `'WINDOW'` region override for Area Capture screenshots.
- BMesh attribute allocation safety (no empty `0.0` float layers, safe iteration after layer creation, non-destructive mesh updates).

---

## [1.99] - 2026-09-16
- Added **Flatten Axis (`X/Y/Z`)** with `GLOBAL`, `LOCAL`, and `VIEW` orientation options.
- Added multi-object Edit Mode crease support and Blender 4.0+ `crease_edge` float attribute handling.
- Added LoopTools enable helper UI, safer screenshot timer checks, and safer unregistration guards.

---

## [1.98] - 2026-08-27
- Initial consolidated N-Panel release with LoopTools shortcuts (`Relax`, `Space`, `GStretch`), Edge Crease (`0 / 0.5 / 1`), customizable 3–6 MatCap slots, and delayed N-panel-hidden Viewport Screenshot.
