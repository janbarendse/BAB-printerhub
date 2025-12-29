# Plan: PyQt Modals + Staged Build/Compile

Goal: replace the current modal UIs with PyQt equivalents, validate them in
source mode first, then build an exe, and finally compile only the protected
core with Nuitka while keeping UI code uncompiled.

Phase 1: Baseline + UI framework decision
- Confirm PyQt variant (PyQt6 vs PySide6) and licensing constraints.
- Identify which modals to port first (fiscal tools, export, log viewer, settings).
- Define UI runtime layout (where PyQt assets and UI entrypoints live).

Phase 2: PyQt modal implementation (no exe build)
- Build PyQt modal shells with layout/visual parity to existing webview UI.
- Wire UI actions to IPC client calls (same interface as current webview UI).
- Add a simple dev launcher to open each modal from source.
- Manual run: verify open/close, data bindings, and IPC calls.

Phase 3: Package core + PyQt UI (exe build)
- Update build deps to include PyQt runtime.
- Build exe with PyInstaller using workspace subfolders.
- Validate tray app + PyQt modals from exe.

Phase 4: Compile protected core with Nuitka
- Separate protected core modules (printer drivers, software mappings).
- Keep PyQt UI code in source form.
- Configure Nuitka to compile only the protected core.
- Validate IPC and modal flows against the compiled core.

Deliverables
- PyQt modal implementation in `src/` with launcher.
- Updated build scripts and requirements.
- Nuitka compilation config limited to protected core.
