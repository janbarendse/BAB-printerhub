"""
UI modal entrypoint for the embedded runtime.

This runs unprotected UI code and talks to the core over IPC.
"""

from __future__ import annotations

import os
import sys


def _resolve_base_dir() -> str:
    env_base = os.environ.get("BAB_UI_BASE")
    if env_base:
        return env_base
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_sys_path(base_dir: str) -> None:
    if base_dir and base_dir not in sys.path:
        sys.path.insert(0, base_dir)


def main() -> int:
    modal_arg = ""
    if len(sys.argv) > 1 and sys.argv[1].startswith("--modal="):
        modal_arg = sys.argv[1].split("=", 1)[1].strip()

    if not modal_arg:
        logger.error("No modal specified. Use --modal=<name>")
        return 1

    base_dir = _resolve_base_dir().strip()
    _ensure_sys_path(base_dir)

    from src.logger_module import logger

    logger.info("UI runner base dir: %s", base_dir)

    try:
        from src.core.config_manager import load_config
        config_path = os.path.join(base_dir, "config.json")
        config = load_config(config_path)
    except Exception as exc:
        logger.error("Failed to load config: %s", exc)
        config = {}
        config_path = os.path.join(base_dir, "config.json")

    if modal_arg == "fiscal_tools":
        from src.core import fiscal_ui

        fiscal_ui._open_fiscal_tools_modal_original(config)
        return 0

    if modal_arg == "export":
        from src.core import export_ui

        export_ui._open_export_modal_original(config)
        return 0

    if modal_arg == "settings":
        from src.core import config_settings_ui

        config_settings_ui._open_config_settings_window(config_path, config)
        return 0

    logger.error("Unknown modal: %s", modal_arg)
    return 1


if __name__ == "__main__":
    try:
        import multiprocessing

        multiprocessing.freeze_support()
    except Exception:
        pass

    sys.exit(main())
