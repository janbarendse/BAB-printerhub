"""
System tray icon and menu management for BAB-Cloud PrintHub.

Provides a system tray icon with menu for quick access to fiscal tools,
reports, and application control.
"""

import os
import sys
import logging
import threading
import queue
import datetime
import math
from PIL import Image
import pystray
from pystray import Menu as menu, MenuItem as item

# Import version info
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.version import VERSION

logger = logging.getLogger(__name__)


# Determine base directory for logo
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    RESOURCE_DIR = sys._MEIPASS  # For bundled resources (logo.png)
    BASE_DIR = os.path.dirname(sys.executable)  # For user files
else:
    # Running as script from src/core/ directory
    # Need to go up 3 levels: core -> src -> bridge
    RESOURCE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    BASE_DIR = RESOURCE_DIR


class SystemTray:
    """
    System tray icon manager.

    Provides a system tray icon with menu for:
    - Opening fiscal tools modal
    - Quick X/Z reports
    - NO SALE operation
    - Application quit
    """

    def __init__(self, config, printer, software, modal_queue):
        """
        Initialize system tray.

        Args:
            config: Full configuration dict
            printer: Active printer instance
            software: Active software instance
            modal_queue: Queue for signaling main thread to open modals
        """
        self.config = config
        self.printer = printer
        self.software = software
        self.modal_queue = modal_queue
        self.icon = None

        # Initialize WordPress command sender for cloud mode
        self.wp_sender = None
        if self._should_use_cloud():
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'wordpress'))
                from wordpress_command_sender import WordPressCommandSender
                self.wp_sender = WordPressCommandSender(config)
                logger.info("System tray: Cloud mode enabled, commands will route through WordPress")
            except Exception as e:
                logger.error(f"Failed to initialize WordPress command sender: {e}")
                self.wp_sender = None

    def _cloud_mode_enabled(self) -> bool:
        return self.config.get('mode') == 'cloud' and self.config.get('babportal', {}).get('enabled', False)

    def _demo_mode(self) -> bool:
        return bool(self.config.get('system', {}).get('demo_mode', False))

    def _cloud_policy_enabled(self) -> bool:
        return bool(self.config.get('babportal', {}).get('cloud_only', False))

    def _cloud_grace_hours(self) -> int:
        try:
            return int(self.config.get('babportal', {}).get('cloud_grace_hours', 72))
        except (TypeError, ValueError):
            return 72

    def _within_cloud_grace(self) -> bool:
        last_check = self.config.get('babportal', {}).get('last_license_check')
        if not last_check:
            return self._cloud_grace_hours() > 0
        try:
            last_dt = datetime.datetime.fromisoformat(last_check)
        except Exception:
            return False
        return (datetime.datetime.now() - last_dt) <= datetime.timedelta(hours=self._cloud_grace_hours())

    def _grace_remaining_hours(self) -> int:
        grace_hours = self._cloud_grace_hours()
        last_check = self.config.get('babportal', {}).get('last_license_check')
        if not last_check:
            return grace_hours
        try:
            last_dt = datetime.datetime.fromisoformat(last_check)
        except Exception:
            return grace_hours
        elapsed = datetime.datetime.now() - last_dt
        remaining = datetime.timedelta(hours=grace_hours) - elapsed
        remaining_hours = max(0, math.ceil(remaining.total_seconds() / 3600))
        return remaining_hours

    def _portal_unreachable_over_hours(self, hours: int) -> bool:
        last_check = self.config.get('babportal', {}).get('last_license_check')
        if not last_check:
            return False
        try:
            last_dt = datetime.datetime.fromisoformat(last_check)
        except Exception:
            return False
        return (datetime.datetime.now() - last_dt) >= datetime.timedelta(hours=hours)

    def _should_use_cloud(self) -> bool:
        if self._demo_mode():
            return False
        return self._cloud_mode_enabled() or self._cloud_policy_enabled()

    def _should_fallback_to_local(self, result) -> bool:
        if not self._cloud_policy_enabled():
            return False
        if not self._within_cloud_grace():
            return False
        return result.get("error_code") in ("connection_error", "config_missing")

    def _open_fiscal_tools(self):
        """Signal main thread to open fiscal tools modal."""
        try:
            logger.info("Fiscal Tools requested from system tray")
            self.modal_queue.put('open_fiscal_tools')
        except Exception as e:
            logger.error(f"Error signaling fiscal tools: {e}")

    def _open_export_modal(self):
        """Signal main thread to open export modal."""
        try:
            logger.info("Export modal requested from system tray")
            self.modal_queue.put('open_export_modal')
        except Exception as e:
            logger.error(f"Error signaling export modal: {e}")

    def _print_x_report(self):
        """Print X report from system tray."""
        try:
            logger.info("X-Report triggered from system tray")

            # Route through WordPress in cloud mode
            if self._should_use_cloud() and self.wp_sender:
                logger.info("Cloud mode: Routing X-Report through WordPress API")
                result = self.wp_sender.print_x_report()
                if not result.get("success") and self._should_fallback_to_local(result):
                    logger.warning("Cloud-only enforced, portal unreachable; using grace fallback")
                    result = self.printer.print_x_report()
            else:
                # Local execution
                result = self.printer.print_x_report()

            if result.get("success"):
                logger.info("X-Report printed successfully from system tray")
            else:
                logger.warning(f"X-Report failed from system tray: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error printing X-Report from system tray: {e}")

    def _print_z_report(self):
        """Print Z report from system tray."""
        try:
            logger.info("Z-Report triggered from system tray")

            # Route through WordPress in cloud mode
            if self._should_use_cloud() and self.wp_sender:
                logger.info("Cloud mode: Routing Z-Report through WordPress API")
                result = self.wp_sender.print_z_report()
                if not result.get("success") and self._should_fallback_to_local(result):
                    logger.warning("Cloud-only enforced, portal unreachable; using grace fallback")
                    result = self.printer.print_z_report(close_fiscal_day=True)
            else:
                # Local execution
                result = self.printer.print_z_report(close_fiscal_day=True)

            if result.get("success"):
                logger.info("Z-Report printed successfully from system tray")

                # Export salesbook CSV after successful Z-report
                try:
                    from .salesbook_exporter import export_salesbook_after_z_report
                    export_result = export_salesbook_after_z_report(self.config)
                    if export_result.get("success"):
                        logger.info(f"Salesbook CSV exported: {export_result.get('summary_file', 'N/A')}")
                    else:
                        logger.warning(f"Salesbook export skipped or failed: {export_result.get('error', 'Unknown')}")
                except Exception as export_error:
                    logger.error(f"Error exporting salesbook CSV: {export_error}")
            else:
                logger.warning(f"Z-Report failed from system tray: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error printing Z-Report from system tray: {e}")

    def _print_no_sale(self):
        """Print NO SALE receipt from system tray."""
        try:
            logger.info("NO SALE triggered from system tray")

            # Route through WordPress in cloud mode
            if self._should_use_cloud() and self.wp_sender:
                logger.info("Cloud mode: Routing NO SALE through WordPress API")
                result = self.wp_sender.print_no_sale()
                if not result.get("success") and self._should_fallback_to_local(result):
                    logger.warning("Cloud-only enforced, portal unreachable; using grace fallback")
                    result = self.printer.print_no_sale()
            else:
                # Local execution
                result = self.printer.print_no_sale()

            if result.get("success"):
                logger.info("NO SALE printed successfully from system tray")
            else:
                logger.warning(f"NO SALE failed from system tray: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error printing NO SALE from system tray: {e}")

    def _open_log_window(self):
        """Open log viewer window."""
        try:
            logger.info("Log window requested from system tray")
            self.modal_queue.put('open_log_window')
        except Exception as e:
            logger.error(f"Error signaling log window: {e}")

    def _open_pos_frontend(self):
        """Open POS frontend (URL for Odoo, executable for TCPOS)."""
        try:
            logger.info("POS frontend requested from system tray")
            active_software = self.config.get('software', {}).get('active', '')

            if active_software == 'odoo':
                # Open Odoo URL in browser
                try:
                    odoo_url = self.config.get('software', {}).get('odoo', {}).get('url')
                    if odoo_url:
                        import webbrowser
                        webbrowser.open(odoo_url)
                        logger.info(f"Opening Odoo at {odoo_url}")
                    else:
                        logger.warning("Odoo URL not configured in config.json")
                except Exception as e:
                    logger.error(f"Error opening Odoo URL: {e}")

            elif active_software == 'tcpos':
                # Launch TCPOS executable
                tcpos_exe = r"D:\TCpos\FrontEnd\TCPOS.AppStarter.exe"
                if os.path.exists(tcpos_exe):
                    import subprocess
                    subprocess.Popen([tcpos_exe])
                    logger.info(f"Launching TCPOS from {tcpos_exe}")
                else:
                    logger.warning(f"TCPOS executable not found at {tcpos_exe}")
            else:
                logger.warning(f"POS frontend not configured for {active_software}")

        except Exception as e:
            logger.error(f"Error opening POS frontend: {e}")

    def _open_babcloud_portal(self):
        """Open BABCloud portal in browser with automatic login."""
        try:
            import webbrowser
            import requests
            import base64
            from urllib.parse import urljoin

            logger.info("Opening BABCloud portal...")

            # Get WordPress credentials from config
            wp_config = self.config.get('babportal', {})
            username = wp_config.get('wordpress_username', '').strip()
            app_password = wp_config.get('wordpress_app_password', '').strip()
            base_url = wp_config.get('url', '').rstrip('/')

            if not username or not app_password:
                logger.error("WordPress credentials not configured. Please add wordpress_username and wordpress_app_password to config.json")
                webbrowser.open(f"{base_url}/my-printers")
                return

            try:
                # Generate autologin token via REST API
                token_url = f"{base_url}/wp-json/babcloud/v1/autologin/generate-token"
                auth_string = f"{username}:{app_password}"
                auth_bytes = auth_string.encode('ascii')
                auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

                headers = {
                    'Authorization': f'Basic {auth_b64}'
                }

                response = requests.post(token_url, headers=headers, timeout=5, verify=False)

                if response.status_code == 200:
                    data = response.json()
                    token = data.get('token')

                    # Open browser with autologin token
                    autologin_url = f"{base_url}/my-printers?autologin_token={token}"
                    logger.info(f"Opening portal: {autologin_url}")
                    webbrowser.open(autologin_url)
                else:
                    logger.error(f"Failed to generate autologin token: {response.status_code}")
                    # Fallback: Just open the portal page (user will need to log in manually)
                    webbrowser.open(f"{base_url}/my-printers")

            except Exception as e:
                logger.error(f"Error opening portal: {e}")
                # Fallback: Just open the portal page
                webbrowser.open(f"{base_url}/my-printers")

        except Exception as e:
            logger.error(f"Error in _open_babcloud_portal: {e}")

    def _open_settings(self):
        """Open config settings editor."""
        try:
            logger.info("Opening settings editor...")
            self.modal_queue.put('open_settings')

        except Exception as e:
            logger.error(f"Error opening settings: {e}")

    def _quit_application(self):
        """Quit the application."""
        try:
            logger.info("Quit requested from system tray")

            # Stop software integration gracefully
            if self.software and self.software.running:
                logger.info(f"Stopping {self.software.get_name()} integration...")
                self.software.stop()

            # Disconnect printer
            if self.printer and self.printer.connected:
                logger.info(f"Disconnecting {self.printer.get_name()} printer...")
                self.printer.disconnect()

            logger.info("Application shutting down")
            os._exit(0)

        except Exception as e:
            logger.error(f"Error during quit: {e}")
            os._exit(1)

    def create_menu(self) -> menu:
        """
        Create the system tray menu.

        Returns:
            pystray.Menu: Configured menu
        """
        # Get active software and printer names for status display
        active_software = self.config.get('software', {}).get('active', 'unknown').upper()
        active_printer = self.config.get('printer', {}).get('active', 'unknown').upper()

        items = [
            item('Fiscal Tools', self._open_fiscal_tools, default=True),
            item('Export Salesbook', self._open_export_modal),
            menu.SEPARATOR,
            item('Access BABCloud Portal', self._open_babcloud_portal),
            item(f'Open {active_software} POS', self._open_pos_frontend),
            menu.SEPARATOR,
            item('Print X-Report', self._print_x_report),
            item('Print Z-Report', self._print_z_report),
            menu.SEPARATOR,
            item('View Logs', self._open_log_window),
            item('Settings', self._open_settings),
            item(f'Status: {active_software} > {active_printer}', None, enabled=False),
            menu.SEPARATOR,
            item(f'Quit BAB PrintHub v{VERSION}', self._quit_application)
        ]

        if self._demo_mode():
            remaining_hours = self._grace_remaining_hours()
            items.insert(
                10,
                item(f'Demo mode (Grace {remaining_hours}h)', None, enabled=False),
            )
        elif (
            self._cloud_policy_enabled()
            and self._within_cloud_grace()
            and self._portal_unreachable_over_hours(1)
        ):
            remaining_hours = self._grace_remaining_hours()
            items.insert(
                10,
                item(f'App in Grace mode ({remaining_hours}h left)', None, enabled=False),
            )

        return menu(*items)

    def run(self):
        """
        Run the system tray icon (blocking).

        This should be called in a background thread.
        """
        try:
            # Load logo image
            logo_path = os.path.join(RESOURCE_DIR, 'logo.png')
            if not os.path.exists(logo_path):
                logger.warning(f"Logo not found at {logo_path}, using default icon")
                # Create a simple default icon if logo missing
                logo = Image.new('RGB', (64, 64), color='blue')
            else:
                logo = Image.open(logo_path)

            # Create icon with on_activated for direct click
            self.icon = pystray.Icon(
                name='BAB Cloud PrintHub',
                icon=logo,
                title='BAB Cloud PrintHub',
                menu=self.create_menu(),
                on_activated=lambda: self._open_fiscal_tools()  # Open modal on direct click
            )

            logger.info("System tray icon created, starting...")
            self.icon.run()  # Blocking call

        except Exception as e:
            logger.error(f"Error in system tray: {e}")
            raise

    def stop(self):
        """Stop the system tray icon."""
        if self.icon:
            try:
                self.icon.stop()
                logger.info("System tray icon stopped")
            except Exception as e:
                logger.error(f"Error stopping system tray: {e}")


def start_system_tray(config, printer, software, modal_queue) -> threading.Thread:
    """
    Start the system tray icon in a background thread.

    Args:
        config: Full configuration dict
        printer: Active printer instance
        software: Active software instance
        modal_queue: Queue for modal signaling

    Returns:
        threading.Thread: System tray thread (already started)
    """
    tray = SystemTray(config, printer, software, modal_queue)
    tray_thread = threading.Thread(target=tray.run, daemon=True, name="SystemTray")
    tray_thread.start()

    logger.info("System tray thread started")
    return tray_thread
