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

# Enforce Python 3.13 requirement (pythonnet compatibility)
if sys.version_info < (3, 13) or sys.version_info >= (3, 14):
    print("=" * 60)
    print("ERROR: Python 3.13 is required")
    print(f"Current version: {sys.version}")
    print("pythonnet requires Python 3.13 (not 3.14+)")
    print("Please install Python 3.13 and try again")
    print("=" * 60)
    input("Press Enter to exit...")
    sys.exit(1)

# Setup logging
from logger_module import logger

# Import version info
from version import VERSION

# Queue for main thread communication (for modal UI)
modal_queue = queue.Queue()

# Pre-import webview at startup for faster modal opening
try:
    import webview
    logger.info("Webview module pre-loaded")
except Exception as e:
    logger.warning(f"Could not pre-load webview module: {e}")


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
    from single_instance import check_single_instance

    instance_lock = check_single_instance("BAB_Cloud_PrintHub")
    logger.info("✓ Single instance lock acquired")

    # =========================================================================
    # Step 2: Load Configuration
    # =========================================================================
    logger.info("[2/7] Loading configuration...")
    from core.config_manager import load_config, validate_config

    try:
        config = load_config()
        validate_config(config)
        logger.info(f"✓ Configuration loaded and validated")
        logger.info(f"  Active software: {config['software']['active']}")
        logger.info(f"  Active printer: {config['printer']['active']}")
    except Exception as e:
        logger.error(f"✗ Configuration error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # =========================================================================
    # Step 3: Initialize Printer (Factory Pattern)
    # =========================================================================
    logger.info("[3/7] Initializing printer...")
    from printers import create_printer

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
        input("Press Enter to exit...")
        sys.exit(1)

    # =========================================================================
    # Step 4: Initialize POS Software (Factory Pattern)
    # =========================================================================
    logger.info("[4/7] Initializing POS software integration...")
    from software import create_software

    try:
        software = create_software(config, printer)
        logger.info(f"✓ Software integration loaded: {software.get_name()}")

        # Start the integration
        logger.info("  Starting integration...")
        if software.start():
            logger.info(f"  ✓ {software.get_name()} integration started")
        else:
            logger.warning(f"  ✗ {software.get_name()} integration failed to start")
            # Continue anyway - integration may start later
    except Exception as e:
        logger.error(f"✗ Software integration failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # =========================================================================
    # Step 5: Start BABPortal Poller (Cloud Mode Only)
    # =========================================================================
    logger.info("[5/7] Checking BABPortal configuration...")
    app_mode = config.get('mode', 'local')
    babportal_enabled = config.get('babportal', {}).get('enabled', False)

    babportal_thread = None
    if app_mode == 'cloud' and babportal_enabled:
        logger.info(f"  Mode: cloud - BABPortal polling enabled")
        try:
            from wordpress.wordpress_poller import start_babportal_poller
            babportal_thread = start_babportal_poller(config, printer)
            logger.info("  ✓ BABPortal poller started")
        except Exception as e:
            logger.warning(f"  ✗ BABPortal poller failed: {e}")
            # Continue - BABPortal is optional
    else:
        if app_mode == 'local':
            logger.info(f"  Mode: local - BABPortal polling disabled")
        else:
            logger.info(f"  BABPortal polling: disabled")

    # =========================================================================
    # Step 6: Start System Tray Icon
    # =========================================================================
    logger.info("[6/7] Starting system tray...")
    from core.system_tray import start_system_tray

    try:
        tray_thread = start_system_tray(config, printer, software, modal_queue)
        logger.info("✓ System tray started")
    except Exception as e:
        logger.error(f"✗ System tray failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # =========================================================================
    # Step 7: Main Loop - Listen for Modal UI Requests
    # =========================================================================
    logger.info("[7/7] Main loop ready")
    logger.info("=" * 60)
    logger.info(f"BAB-Cloud PrintHub v{VERSION} is running")
    logger.info("Check system tray for application icon")
    logger.info("=" * 60)

    from core.fiscal_ui import open_fiscal_tools_modal
    from core.log_viewer import open_log_viewer_window

    # Main thread loop: Process modal UI requests
    while True:
        try:
            if not modal_queue.empty():
                command = modal_queue.get()

                if command == 'open_fiscal_tools':
                    logger.info("Opening fiscal tools modal...")
                    try:
                        # Launch modal in separate process (non-blocking)
                        open_fiscal_tools_modal(printer, config)
                    except Exception as e:
                        logger.error(f"Error opening fiscal tools: {e}")

                elif command == 'open_log_window':
                    logger.info("Opening log viewer window...")
                    try:
                        open_log_viewer_window()
                        logger.info("Log viewer window closed")
                    except Exception as e:
                        logger.error(f"Error opening log viewer: {e}")

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

    logger.info("BAB-Cloud PrintHub stopped")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Support for multiprocessing on Windows (required for log viewer)
    import multiprocessing
    multiprocessing.freeze_support()

    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        input("Press Enter to exit...")
        sys.exit(1)
