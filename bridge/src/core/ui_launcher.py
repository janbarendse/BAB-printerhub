"""
Launches unprotected UI modals using an embedded Python runtime.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def _is_compiled() -> bool:
    """Check if running as compiled executable (Nuitka or PyInstaller)."""
    # PyInstaller sets sys.frozen
    if getattr(sys, "frozen", False):
        return True
    # Nuitka sets __compiled__ at module level
    if "__compiled__" in globals():
        return True
    # Check if executable ends with .exe and is not python.exe/pythonw.exe
    if sys.executable.lower().endswith('.exe'):
        exe_name = os.path.basename(sys.executable).lower()
        if exe_name not in ('python.exe', 'pythonw.exe', 'python3.exe', 'python313.exe'):
            return True
    return False


def _resolve_base_dir() -> str:
    if _is_compiled():
        return os.path.dirname(sys.executable)
    # core -> src -> bridge
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _find_ui_python(base_dir: str) -> Optional[str]:
    override = os.environ.get("BAB_UI_PYTHON")
    if override and os.path.exists(override):
        return override

    candidates = [
        os.path.join(base_dir, "ui_runtime", "pythonw.exe"),
        os.path.join(base_dir, "ui_runtime", "python.exe"),
        os.path.join(base_dir, "runtime", "pythonw.exe"),
        os.path.join(base_dir, "runtime", "python.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    if not _is_compiled():
        return sys.executable

    return None


class UIModalLauncher:
    """Launches UI modals with pipe credentials."""

    def __init__(self, pipe_name: str, auth_key: bytes, base_dir: Optional[str] = None) -> None:
        self.pipe_name = pipe_name
        self.auth_key = auth_key
        self.base_dir = base_dir or _resolve_base_dir()
        self.python_exe = _find_ui_python(self.base_dir)
        self.ui_entry = os.path.join(self.base_dir, "src", "core", "ui_modal_runner.py")

    def launch(self, modal_name: str) -> bool:
        env = os.environ.copy()
        env["BAB_PIPE_NAME"] = self.pipe_name
        env["BAB_PIPE_KEY"] = self.auth_key.hex()
        env["BAB_UI_BASE"] = self.base_dir
        env["PYTHONPATH"] = f"{self.base_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

        if _is_compiled():
            # Use absolute path to ensure we launch the correct executable
            # even when the app is moved to a different location
            exe_path = os.path.abspath(sys.executable)
            args = [exe_path, f"--modal={modal_name}"]
        else:
            if not self.python_exe:
                logger.error("UI runtime not found. Set BAB_UI_PYTHON or bundle ui_runtime.")
                return False
            if not os.path.exists(self.ui_entry):
                logger.error("UI entrypoint not found: %s", self.ui_entry)
                return False
            args = [self.python_exe, self.ui_entry, f"--modal={modal_name}"]

        logger.info("Launching modal subprocess with args: %s", args)
        logger.info("Executable: %s", sys.executable)
        logger.info("Absolute exe path: %s", os.path.abspath(sys.executable))
        logger.info("Is compiled: %s", _is_compiled())
        logger.info("Base directory: %s", self.base_dir)
        logger.info("Current working directory: %s", os.getcwd())
        logger.info("Exe exists: %s", os.path.exists(sys.executable))

        # Ensure base_dir is absolute and exists
        abs_base_dir = os.path.abspath(self.base_dir)
        if not os.path.isdir(abs_base_dir):
            logger.error("Base directory does not exist: %s", abs_base_dir)
            return False

        try:
            subprocess.Popen(
                args,
                cwd=abs_base_dir,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            logger.info("UI modal launched: %s", modal_name)
            return True
        except Exception as exc:
            logger.error("Failed to launch UI modal %s: %s", modal_name, exc)
            return False
