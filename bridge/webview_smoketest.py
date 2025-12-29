"""
Minimal pywebview smoketest focused on Nuitka modal issues.

Goals:
- Prefer Edge/WebView2 (edgechromium) and fall back to mshtml if missing.
- Check for WebView2 runtime and log/alert when not found.
- Mimic the subprocess modal launch pattern used in the main app.
"""

import glob
import logging
import os
import sys
import subprocess
import ctypes
import multiprocessing


# -----------------------------------------------------------------------------
# Logging setup
# -----------------------------------------------------------------------------
def _is_compiled_exe() -> bool:
    """
    Detect whether we are running from a compiled onefile/onefolder exe.

    Nuitka sometimes doesn't set sys.frozen for onefile, so also check
    __compiled__ and the executable extension.
    """
    if getattr(sys, "frozen", False):
        return True
    if "__compiled__" in globals():
        return True
    if sys.executable.lower().endswith(".exe"):
        return True
    return False


def _resolve_log_dir() -> str:
    """Pick a persistent log directory for compiled builds."""
    if _is_compiled_exe():
        base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base_dir:
            return os.path.join(base_dir, "BAB-PrintHub", "logs")
        return os.getcwd()
    return os.path.dirname(os.path.abspath(__file__))


LOG_DIR = _resolve_log_dir()
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "webview_smoketest.log")

logger = logging.getLogger("webview_smoketest")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(console_handler)

logger.info("Smoketest starting (pid=%s, frozen=%s)", os.getpid(), getattr(sys, "frozen", False))
logger.info("Log file: %s", LOG_FILE)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def show_error(title: str, message: str) -> None:
    """Display a native message box (best effort)."""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x10)
    except Exception:
        pass


def find_webview2_runtime() -> str | None:
    """Return the path to msedgewebview2.exe if the runtime is installed, else None."""
    candidates = [
        r"C:\Program Files\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
        r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def create_window(gui_preference: str = "edgechromium") -> None:
    """Create and start a simple webview window."""
    import webview  # Imported here to keep module surface small during build

    logger.info("Requested GUI backend: %s", gui_preference)
    runtime_path = find_webview2_runtime()
    if runtime_path:
        logger.info("WebView2 runtime detected at: %s", runtime_path)
    else:
        logger.warning("WebView2 runtime NOT found; will fall back to mshtml if Edge fails")

    html = """
    <!doctype html>
    <html>
    <head><meta charset="utf-8"><title>WebView Smoketest</title></head>
    <body style="font-family: Segoe UI, sans-serif; padding:24px;">
      <h2>WebView Smoketest</h2>
      <p>Backend preference: <strong>{backend}</strong></p>
      <p>PID: {pid}</p>
      <p>Runtime: {runtime}</p>
      <button onclick="pywebview.api.close()">Close via API</button>
    </body>
    </html>
    """.format(
        backend=gui_preference,
        pid=os.getpid(),
        runtime=runtime_path or "not found",
    )

    class API:
        def __init__(self):
            self.window = None

        def close(self):
            if self.window:
                self.window.destroy()

    api = API()
    window = webview.create_window(
        title="WebView Smoketest",
        html=html,
        width=600,
        height=400,
        js_api=api,
        resizable=True,
    )
    api.window = window

    logger.info("webview.start -> edgechromium (private_mode=True)")
    try:
        webview.start(gui=gui_preference, debug=False, private_mode=True)
        logger.info("webview.start returned (edgechromium)")
        return
    except SystemExit as se:
        logger.info("webview.start raised SystemExit on edgechromium: %s", se)
        return
    except Exception as edge_err:
        logger.exception("Edge/WebView2 backend failed: %s", edge_err)
        show_error("WebView2 Error", f"Edge backend failed:\n{edge_err}\nFalling back to mshtml...")

    logger.info("webview.start -> mshtml (fallback, debug=True)")
    try:
        webview.start(gui="mshtml", debug=True)
        logger.info("webview.start returned (mshtml)")
    except SystemExit as se:
        logger.info("webview.start raised SystemExit on mshtml: %s", se)
    except Exception as mshtml_err:
        logger.exception("mshtml backend also failed: %s", mshtml_err)
        show_error("WebView Error", f"mshtml backend failed:\n{mshtml_err}")
        raise


def run_modal():
    """Run the modal directly (used by --modal flag)."""
    create_window(gui_preference="edgechromium")


def run_launcher():
    """
    Simple launcher that mimics the main app pattern:
    - main process triggers a subprocess with --modal
    - keeps the console alive to observe crashes/logs
    """
    exe = sys.executable
    args = [exe]

    if _is_compiled_exe():
        # In compiled mode, just ask the exe to open modal once
        args.append("--modal=demo")
    else:
        # When running as a script, pass the script path explicitly
        script_path = os.path.abspath(__file__)
        args.extend([script_path, "--modal=demo"])

    logger.info("Launching modal subprocess using: %s", " ".join(args))
    try:
        proc = subprocess.Popen(args)
        logger.info("Spawned modal subprocess (pid=%s)", proc.pid)
        proc.wait()
        logger.info("Modal subprocess exited with code %s", proc.returncode)
    except Exception as e:
        logger.exception("Failed to launch modal subprocess: %s", e)
        show_error("Launcher Error", str(e))


def main():
    # Basic arg parsing
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    # Compiled exe: avoid launcher recursion, just run modal unless explicitly told otherwise
    if _is_compiled_exe():
        if arg.startswith("--modal"):
            run_modal()
        else:
            # Single-shot modal for smoketest in compiled mode
            run_modal()
        return

    # Script mode (non-compiled)
    if arg.startswith("--modal"):
        run_modal()
    else:
        runtime_path = find_webview2_runtime()
        logger.info("WebView2 runtime present: %s", bool(runtime_path))
        print(f"WebView2 runtime present: {bool(runtime_path)}")
        run_launcher()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
