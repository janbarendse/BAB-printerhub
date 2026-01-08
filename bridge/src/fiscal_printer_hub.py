"""
BAB-Cloud PrintHub - Main Application Entry Point

This is the unified fiscal printer bridge application that supports multiple
POS systems (Odoo, TCPOS, Simphony, QuickBooks) and multiple printer brands
(CTS310ii, Star, Citizen, Epson) through a modular, config-driven architecture.

The application runs as a Windows system tray application with:
- Background POS integration (polling or file monitoring)
- System tray icon with quick actions
- Fiscal tools modal UI (pywebview)
- Single instance enforcement
"""

import sys
import os
import time
import queue
import threading
import logging

# IMPORTANT: Check for modal mode FIRST, before any other initialization
# This ensures modals don't trigger single instance checks or other startup logic
# Check all arguments, not just argv[1], since Nuitka may add extra arguments
_IS_MODAL_MODE = False
_MODAL_NAME = None
for arg in sys.argv[1:]:
    if arg.startswith('--modal='):
        _IS_MODAL_MODE = True
        _MODAL_NAME = arg.split('=')[1]
        break

# Enforce Python 3.13 requirement (pythonnet compatibility)
# Skip this check in modal mode since the main instance already passed it
if not _IS_MODAL_MODE and (sys.version_info < (3, 13) or sys.version_info >= (3, 14)):
    print("=" * 60)
    print("ERROR: Python 3.13 is required")
    print(f"Current version: {sys.version}")
    print("pythonnet requires Python 3.13 (not 3.14+)")
    print("Please install Python 3.13 and try again")
    print("=" * 60)
    try:
        input("Press Enter to exit...")
    except (EOFError, OSError):
        pass  # No stdin in GUI mode
    sys.exit(1)

# Setup logging
from src.logger_module import logger

# Import version info
from src.version import VERSION

# Queue for main thread communication (for modal UI)
modal_queue = queue.Queue()

def main():
    """
    Main application entry point.

    Workflow:
    1. Enforce single instance
    2. Load configuration
    3. Initialize printer (factory pattern)
    4. Initialize POS software (factory pattern)
    5. Start WordPress poller (if enabled)
    6. Start system tray icon
    7. Main loop: Listen for modal UI requests
    """

    logger.info("=" * 60)
    logger.info(f"BAB-Cloud PrintHub v{VERSION} Starting...")
    logger.info("=" * 60)

    # =========================================================================
    # Step 1: Single Instance Enforcement
    # =========================================================================
    logger.info("[1/7] Enforcing single instance...")
    from src.single_instance import check_single_instance

    instance_lock = check_single_instance("BAB_Cloud_PrintHub")
    logger.info("✓ Single instance lock acquired")

    # =========================================================================
    # Step 2: Load Configuration
    # =========================================================================
    logger.info("[2/7] Loading configuration...")
    from src.core.config_manager import load_config, validate_config

    try:
        config = load_config()
        validate_config(config)
        logger.info(f"✓ Configuration loaded and validated")
        logger.info(f"  Active software: {config['software']['active']}")
        logger.info(f"  Active printer: {config['printer']['active']}")
    except Exception as e:
        logger.error(f"✗ Configuration error: {e}")
        try:
            input("Press Enter to exit...")
        except (EOFError, OSError):
            pass  # No stdin in GUI mode
        sys.exit(1)

    # =========================================================================
    # Step 3: Initialize Printer (Factory Pattern)
    # =========================================================================
    logger.info("[3/7] Initializing printer...")
    from src.printers import create_printer

    try:
        printer = create_printer(config)
        logger.info(f"✓ Printer driver loaded: {printer.get_name()}")

        # Connect to printer
        logger.info("  Connecting to printer...")
        if printer.connect():
            logger.info(f"  ✓ Connected to {printer.get_name()} on {printer.com_port}")
        else:
            logger.warning("  ✗ Could not connect to printer - will retry in background")
            # Don't exit - printer may be offline temporarily
    except Exception as e:
        logger.error(f"✗ Printer initialization failed: {e}")
        try:
            input("Press Enter to exit...")
        except (EOFError, OSError):
            pass  # No stdin in GUI mode
        sys.exit(1)

    # =========================================================================
    # Step 4: Initialize POS Software (Factory Pattern)
    # =========================================================================
    logger.info("[4/7] Initializing POS software integration...")
    from src.software import create_software

    try:
        software = create_software(config, printer)
        logger.info(f"✓ Software integration loaded: {software.get_name()}")

        # Start the integration
        logger.info("  Starting integration...")
        try:
            start_result = software.start()
            if start_result:
                logger.info(f"  ✓ {software.get_name()} integration started")
            else:
                logger.warning(f"  ✗ {software.get_name()} integration failed to start")
                # Log error details if available
                if hasattr(software, 'errors') and software.errors:
                    logger.error(f"  Error details: {software.errors[-1]}")
                if hasattr(software, 'get_status'):
                    status = software.get_status()
                    if 'error' in status:
                        logger.error(f"  Status error: {status['error']}")
                # Continue anyway - integration may start later
        except Exception as start_ex:
            logger.error(f"  ✗ Exception during {software.get_name()} start(): {start_ex}")
            logger.error(f"  Exception type: {type(start_ex).__name__}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            # Continue anyway
    except Exception as e:
        logger.error(f"✗ Software integration failed: {e}")
        try:
            input("Press Enter to exit...")
        except (EOFError, OSError):
            pass  # No stdin in GUI mode
        sys.exit(1)

    # =========================================================================
    # Step 4.5: Start IPC Server for UI Modals
    # =========================================================================
    logger.info("[4.5/7] Starting IPC server...")
    from src.core.ipc import PipeServer, make_pipe_name, make_auth_key
    from src.core.ipc_handlers import CoreCommandHandler
    from src.core.ui_launcher import UIModalLauncher

    ipc_handler = CoreCommandHandler(config, printer, software)
    pipe_name = make_pipe_name()
    auth_key = make_auth_key()
    ipc_server = PipeServer(pipe_name, auth_key, ipc_handler.handle, log=logger)
    ipc_server.start()

    ui_launcher = UIModalLauncher(pipe_name, auth_key)

    # =========================================================================
    # Step 5: Start BABPortal Poller
    # =========================================================================
    logger.info("[5/7] Checking BABPortal configuration...")
    babportal_enabled = config.get('babportal', {}).get('enabled', False)

    babportal_thread = None
    if babportal_enabled:
        logger.info("  BABPortal polling enabled")
        try:
            from src.wordpress.wordpress_poller import start_babportal_poller
            babportal_thread = start_babportal_poller(config, printer)
            logger.info("  OK BABPortal poller started")
        except Exception as e:
            logger.warning(f"  ? BABPortal poller failed: {e}")
            # Continue - BABPortal is optional
    else:
        logger.info("  BABPortal polling: disabled")

# =========================================================================
    # Step 6: Start System Tray Icon
    # =========================================================================
    logger.info("[6/7] Starting system tray...")
    from src.core.system_tray import start_system_tray

    try:
        tray_thread = start_system_tray(config, printer, software, modal_queue)
        logger.info("✓ System tray started")
    except Exception as e:
        logger.error(f"✗ System tray failed: {e}")
        try:
            input("Press Enter to exit...")
        except (EOFError, OSError):
            pass  # No stdin in GUI mode
        sys.exit(1)

    # =========================================================================
    # Step 7: Main Loop - Listen for Modal UI Requests
    # =========================================================================
    logger.info("[7/7] Main loop ready")
    logger.info("=" * 60)
    logger.info(f"BAB-Cloud PrintHub v{VERSION} is running")
    logger.info("Check system tray for application icon")
    logger.info("=" * 60)

    # Main thread loop: Process modal UI requests
    while True:
        try:
            if not modal_queue.empty():
                command = modal_queue.get()

                if command == 'open_fiscal_tools':
                    logger.info("Opening fiscal tools modal...")
                    try:
                        ui_launcher.launch("fiscal_tools")
                    except Exception as e:
                        logger.error(f"Error opening fiscal tools: {e}")

                elif command == 'open_export_modal':
                    logger.info("Opening export modal...")
                    try:
                        ui_launcher.launch("export")
                    except Exception as e:
                        logger.error(f"Error opening export modal: {e}")

                elif command == 'open_settings':
                    logger.info("Opening settings window...")
                    try:
                        ui_launcher.launch("settings")
                    except Exception as e:
                        logger.error(f"Error opening settings: {e}")

                elif command == 'quit':
                    logger.info("Quit command received")
                    break

            # Sleep briefly to avoid busy-wait
            time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(1)  # Prevent tight error loop

    # =========================================================================
    # Cleanup
    # =========================================================================
    logger.info("=" * 60)
    logger.info("Shutting down BAB-Cloud PrintHub...")
    logger.info("=" * 60)

    # Stop software integration
    if software and software.running:
        logger.info(f"Stopping {software.get_name()} integration...")
        software.stop()

    # Disconnect printer
    if printer and printer.connected:
        logger.info(f"Disconnecting {printer.get_name()}...")
        printer.disconnect()

    # Release instance lock
    instance_lock.release()

    # Stop IPC server
    try:
        ipc_server.stop()
    except Exception:
        pass

    logger.info("BAB-Cloud PrintHub stopped")
    logger.info("=" * 60)


def _show_modal_error(title, message):
    """Show native Windows error dialog for modal errors."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(message), title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def _is_compiled():
    """Check if running as compiled executable (Nuitka or PyInstaller)."""
    # PyInstaller sets sys.frozen
    if getattr(sys, 'frozen', False):
        return True
    # Nuitka sets __compiled__ at module level
    if '__compiled__' in globals():
        return True
    # Check if executable ends with .exe and is not python.exe/pythonw.exe
    if sys.executable.lower().endswith('.exe'):
        exe_name = os.path.basename(sys.executable).lower()
        if exe_name not in ('python.exe', 'pythonw.exe', 'python3.exe', 'python313.exe'):
            return True
    return False


def run_modal_standalone(modal_name):
    """
    Run a modal in standalone mode (separate process).
    This is called when the executable is launched with --modal=X argument.
    """
    logger.info(f"[MODAL SUBPROCESS] Starting modal: {modal_name}")

    try:
        from src.core.config_manager import load_config

        # Debug: Log compilation detection
        is_compiled = _is_compiled()
        logger.info(f"[MODAL SUBPROCESS] _is_compiled() = {is_compiled}")
        logger.info(f"[MODAL SUBPROCESS] sys.executable = {sys.executable}")
        logger.info(f"[MODAL SUBPROCESS] sys.frozen = {getattr(sys, 'frozen', False)}")
        logger.info(f"[MODAL SUBPROCESS] __compiled__ in globals = {'__compiled__' in globals()}")

        # Load config - always use executable directory for compiled mode
        if is_compiled:
            config_path = os.path.join(os.path.dirname(sys.executable), 'config.json')
        else:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.json')

        logger.info(f"[MODAL SUBPROCESS] Config path: {config_path}")
        logger.info(f"[MODAL SUBPROCESS] Config exists: {os.path.exists(config_path)}")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        config = load_config(config_path)
        logger.info(f"[MODAL SUBPROCESS] Config loaded successfully")

        if modal_name == 'fiscal_tools':
            logger.info(f"[MODAL SUBPROCESS] Launching fiscal_tools...")
            from src.core.fiscal_ui import _open_fiscal_tools_modal_original
            _open_fiscal_tools_modal_original(config)
        elif modal_name == 'export':
            logger.info(f"[MODAL SUBPROCESS] Launching export...")
            from src.core.export_ui import _open_export_modal_original
            _open_export_modal_original(config)
        elif modal_name == 'settings':
            logger.info(f"[MODAL SUBPROCESS] Launching settings...")
            from src.core.config_settings_ui import _open_config_settings_window
            _open_config_settings_window(config_path, config)
        else:
            logger.error(f"[MODAL SUBPROCESS] Unknown modal: {modal_name}")
            _show_modal_error("Modal Error", f"Unknown modal: {modal_name}")
            sys.exit(1)

        logger.info(f"[MODAL SUBPROCESS] Modal {modal_name} closed normally")

    except Exception as e:
        logger.error(f"[MODAL SUBPROCESS] Error in {modal_name}: {e}", exc_info=True)
        _show_modal_error("Modal Error", f"Error in {modal_name}:\n{e}")
        raise


if __name__ == "__main__":
    # Support for multiprocessing on Windows (required for log viewer)
    import multiprocessing
    multiprocessing.freeze_support()

    # Debug: Log sys.argv to understand what arguments are being passed
    logger.info(f"[STARTUP] sys.argv = {sys.argv}")
    logger.info(f"[STARTUP] sys.executable = {sys.executable}")
    logger.info(f"[STARTUP] sys.argv length = {len(sys.argv)}")
    logger.info(f"[STARTUP] Working directory = {os.getcwd()}")
    logger.info(f"[STARTUP] Executable directory = {os.path.dirname(sys.executable)}")
    logger.info(f"[STARTUP] _IS_MODAL_MODE = {_IS_MODAL_MODE}")
    logger.info(f"[STARTUP] _MODAL_NAME = {_MODAL_NAME}")

    # Check if required files exist
    if _is_compiled():
        exe_dir = os.path.dirname(sys.executable)
        required_paths = [
            os.path.join(exe_dir, 'src'),
            os.path.join(exe_dir, 'config.json'),
        ]
        for path in required_paths:
            exists = os.path.exists(path)
            logger.info(f"[STARTUP] Path exists: {path} = {exists}")
            if not exists:
                logger.warning(f"[STARTUP] Missing required path: {path}")

    # Check for modal mode (launched as subprocess for isolated webview)
    # This check was already done at module level to prevent any initialization conflicts
    if _IS_MODAL_MODE:
        logger.info(f"[STARTUP] Modal mode detected: {_MODAL_NAME}")
        try:
            run_modal_standalone(_MODAL_NAME)
        except Exception as e:
            logger.error(f"[MODAL SUBPROCESS] Fatal error: {e}", exc_info=True)
            _show_modal_error("Modal Error", f"Fatal error in {_MODAL_NAME}:\n{e}")
        sys.exit(0)

    # Normal startup - run main application with system tray
    logger.info(f"[STARTUP] Starting normal application mode...")
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        try:
            input("Press Enter to exit...")
        except (EOFError, OSError):
            # No stdin in GUI mode, just exit
            pass
        sys.exit(1)
