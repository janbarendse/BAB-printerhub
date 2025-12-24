"""
BABPortal Command Poller Module

Polls BABPortal REST API for printer commands and executes them.
Supports multiple command types: Z-report, X-report, print check, Z-report range/date, no sale.

Phase 2 Implementation - REST API integration with command queue system
"""

import time
import requests
import urllib3
import logging
import threading

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Import version info
import os
import sys
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from src.version import VERSION
except ImportError:
    VERSION = "1.01"  # Fallback if import fails


class BABPortalPoller:
    """Handles polling BABPortal REST API for printer commands."""

    def __init__(self, config, printer):
        """
        Initialize poller with configuration and printer instance.

        Args:
            config: Full configuration dict
            printer: Active printer instance (implements BasePrinter)
        """
        self.config = config
        self.printer = printer
        self.running = False
        self.stop_event = threading.Event()

        # BABPortal configuration
        wp_config = config.get('babportal', {})
        self.wordpress_url = wp_config.get('url', '')
        self.poll_interval = wp_config.get('poll_interval', 5)
        self.device_id = wp_config.get('device_id', '')
        self.device_token = wp_config.get('device_token', '')
        self.api_version = wp_config.get('api_version', 'v1')

        # Legacy support for Phase 1 file-based system
        self.trigger_endpoint = wp_config.get('trigger_endpoint', '')
        self.complete_endpoint = wp_config.get('complete_endpoint', '')

        # Determine if using REST API (Phase 2) or file-based (Phase 1)
        self.use_rest_api = bool(self.device_id and self.device_token)

        logger.info(f"BABPortal Poller initialized")
        logger.info(f"  URL: {self.wordpress_url}")
        logger.info(f"  Poll interval: {self.poll_interval}s")
        logger.info(f"  Mode: {'REST API (Phase 2)' if self.use_rest_api else 'File-based (Phase 1)'}")
        if self.use_rest_api:
            logger.info(f"  Device ID: {self.device_id}")

    def check_for_trigger(self):
        """
        Check if there's a pending Z-report request.

        Returns:
            tuple: (has_trigger: bool, request_id: str)
        """
        try:
            url = f"{self.wordpress_url}{self.trigger_endpoint}"
            response = requests.get(url, timeout=3, verify=False)

            if response.status_code == 200:
                request_id = response.text.strip()
                logger.info(f"Z-report trigger detected: {request_id}")
                return True, request_id
            elif response.status_code == 404:
                # No trigger pending - normal state
                return False, None
            else:
                logger.warning(f"Unexpected response from WordPress: {response.status_code}")
                return False, None

        except requests.exceptions.Timeout:
            logger.debug("Timeout connecting to WordPress portal")
            return False, None
        except requests.exceptions.ConnectionError:
            logger.debug("Connection error to WordPress portal")
            return False, None
        except Exception as e:
            logger.error(f"Error checking for trigger: {e}")
            return False, None

    def execute_report(self):
        """
        Execute the X-report print (test mode) or Z-report (production).

        Returns:
            dict: Result from printer with 'success' and 'error' keys
        """
        # Check if this is test mode (xreport endpoint) or production (zreport endpoint)
        is_test_mode = 'xreport' in self.trigger_endpoint.lower()

        if is_test_mode:
            logger.info("Executing X-report (test mode)...")
            try:
                # X-report for testing - can be run repeatedly
                result = self.printer.print_x_report()
                return result
            except Exception as e:
                logger.error(f"Exception during report execution: {e}")
                return {"success": False, "error": str(e)}
        else:
            logger.info("Executing Z-report (production)...")
            try:
                # Production: Z-report (fiscal day closing)
                result = self.printer.print_z_report(close_fiscal_day=True)

                # Update config timestamp
                from src.core.config_manager import save_config
                import datetime
                now = datetime.datetime.now()
                self.config["fiscal_tools"]["last_z_report_print_time"] = now.isoformat()
                save_config(self.config)

                # Export salesbook CSV after successful Z-report
                if result.get("success"):
                    try:
                        from src.core.salesbook_exporter import export_salesbook_after_z_report
                        export_result = export_salesbook_after_z_report(self.config)
                        if export_result.get("success"):
                            logger.info(f"Salesbook CSV exported: {export_result.get('summary_file', 'N/A')}")
                        else:
                            logger.warning(f"Salesbook export skipped or failed: {export_result.get('error', 'Unknown')}")
                    except Exception as export_error:
                        logger.error(f"Error exporting salesbook CSV: {export_error}")

                return result
            except Exception as e:
                logger.error(f"Exception during report execution: {e}")
                return {"success": False, "error": str(e)}

    def clear_trigger(self, request_id):
        """
        Send completion callback to WordPress to clear the trigger.

        Args:
            request_id: The request ID to clear

        Returns:
            bool: True if cleared successfully
        """
        try:
            url = f"{self.wordpress_url}{self.complete_endpoint}"
            payload = {
                "request_id": request_id,
                "status": "completed"
            }

            response = requests.post(url, json=payload, timeout=5, verify=False)

            if response.status_code == 200:
                logger.info(f"Trigger cleared successfully: {request_id}")
                return True
            else:
                logger.warning(f"Failed to clear trigger. Status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error clearing trigger: {e}")
            return False

    def poll_loop(self):
        """Main polling loop - runs continuously until stopped."""
        if self.use_rest_api:
            self._poll_loop_rest_api()
        else:
            self._poll_loop_legacy()

    def _poll_loop_rest_api(self):
        """Polling loop for Phase 2 REST API."""
        logger.info(f"Starting BABPortal REST API polling loop...")
        self.running = True
        last_heartbeat = 0

        while not self.stop_event.is_set():
            try:
                # Send heartbeat every 60 seconds
                if time.time() - last_heartbeat > 60:
                    try:
                        self.send_heartbeat()
                        last_heartbeat = time.time()
                    except Exception as e:
                        logger.warning(f"Heartbeat failed: {e}")

                # Check for pending commands
                has_command, command = self.check_for_command()

                if has_command and command:
                    command_id = command.get('command_id')
                    logger.info(f"Processing command: {command_id}")

                    # Execute the command
                    result = self.execute_command(command)

                    # Report completion (always, even if failed)
                    self.complete_command(command_id, result)

                # Wait before next poll
                self.stop_event.wait(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in REST API polling loop: {e}")
                self.stop_event.wait(self.poll_interval)

        self.running = False
        logger.info("BABPortal REST API poller stopped")

    def _poll_loop_legacy(self):
        """Polling loop for Phase 1 file-based system (backward compatibility)."""
        is_test_mode = 'xreport' in self.trigger_endpoint.lower()
        mode_text = "X-report (test mode)" if is_test_mode else "Z-report (production)"
        logger.info(f"Starting BABPortal polling loop - {mode_text} (Legacy mode)...")
        self.running = True

        while not self.stop_event.is_set():
            try:
                # Check for trigger
                has_trigger, request_id = self.check_for_trigger()

                if has_trigger:
                    # Execute report
                    result = self.execute_report()

                    if result.get("success"):
                        logger.info("Report completed successfully")
                        # Clear the trigger
                        self.clear_trigger(request_id)
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error(f"Report failed: {error}")
                        # Clear trigger to prevent infinite retries
                        logger.info("Clearing trigger to prevent infinite retries...")
                        self.clear_trigger(request_id)

                # Wait before next poll (or until stop signal)
                self.stop_event.wait(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                self.stop_event.wait(self.poll_interval)

        self.running = False
        logger.info("BABPortal legacy poller stopped")

    def stop(self):
        """Stop the polling loop gracefully."""
        logger.info("Stopping BABPortal poller...")
        self.stop_event.set()

    # Phase 2: REST API Methods

    def check_for_command(self):
        """
        Check for pending commands via REST API (Phase 2).

        Returns:
            tuple: (has_command: bool, command: dict or None)
        """
        try:
            # Add cachebuster to prevent HTTP caching
            cachebuster = int(time.time() * 1000)
            url = f"{self.wordpress_url}/wp-json/babcloud/{self.api_version}/printer/{self.device_id}/commands?_={cachebuster}"
            headers = {'X-Device-Token': self.device_token}

            response = requests.get(url, headers=headers, timeout=3, verify=False)

            if response.status_code == 200:
                data = response.json()
                if data.get('has_command'):
                    command = data.get('command')
                    logger.info(f"Command detected: {command.get('command_type')} (ID: {command.get('command_id')})")
                    return True, command
                return False, None

            elif response.status_code == 401:
                logger.error("Authentication failed - invalid device token")
                return False, None
            elif response.status_code == 404:
                logger.error("Printer not found in WordPress")
                return False, None
            else:
                logger.warning(f"Unexpected response from REST API: {response.status_code}")
                return False, None

        except requests.exceptions.Timeout:
            logger.debug("Timeout connecting to REST API")
            return False, None
        except requests.exceptions.ConnectionError:
            logger.debug("Connection error to REST API")
            return False, None
        except Exception as e:
            logger.error(f"Error checking for command: {e}")
            return False, None

    def execute_command(self, command):
        """
        Execute a command based on command_type (Phase 2).

        Args:
            command: Dict with command_id, command_type, params

        Returns:
            dict: Result with success, result, error
        """
        # Defensive check: ensure command is a dict
        if not isinstance(command, dict):
            logger.error(f"Invalid command format: expected dict, got {type(command)}")
            return {"success": False, "error": "Invalid command format"}

        command_type = command.get('command_type')
        params = command.get('params', {})

        # Defensive check: ensure params is a dict
        if not isinstance(params, dict):
            logger.warning(f"Invalid params format: expected dict, got {type(params)}, using empty dict")
            params = {}

        logger.info(f"Executing command: {command_type}")

        try:
            if command_type == 'zreport':
                result = self.printer.print_z_report(close_fiscal_day=True)

                # Update config timestamp
                if result.get('success'):
                    from src.core.config_manager import save_config
                    import datetime
                    self.config["fiscal_tools"]["last_z_report_print_time"] = datetime.datetime.now().isoformat()
                    save_config(self.config)

                    # Export salesbook CSV after successful Z-report
                    try:
                        from src.core.salesbook_exporter import export_salesbook_after_z_report
                        export_result = export_salesbook_after_z_report(self.config)
                        if export_result.get("success"):
                            logger.info(f"Salesbook CSV exported: {export_result.get('summary_file', 'N/A')}")
                        else:
                            logger.warning(f"Salesbook export skipped or failed: {export_result.get('error', 'Unknown')}")
                    except Exception as export_error:
                        logger.error(f"Error exporting salesbook CSV: {export_error}")

            elif command_type == 'xreport':
                result = self.printer.print_x_report()

            elif command_type == 'print_check':
                document_number = params.get('document_number')
                if document_number:
                    result = self.printer.reprint_document(str(document_number))
                else:
                    result = self.printer.print_check()

            elif command_type == 'zreport_range':
                from_z = params.get('from_z')
                to_z = params.get('to_z')
                result = self.printer.print_z_report_by_number_range(from_z, to_z)

            elif command_type == 'zreport_date':
                import datetime
                start_date_str = params.get('start_date')
                end_date_str = params.get('end_date', start_date_str)  # Default to same date if no range

                # Convert strings to date objects
                start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else start_date

                result = self.printer.print_z_report_by_date(start_date, end_date)

            elif command_type == 'no_sale':
                reason = params.get('reason', '')
                result = self.printer.print_no_sale(reason)

            else:
                result = {"success": False, "error": f"Unknown command type: {command_type}"}

            return result

        except Exception as e:
            logger.error(f"Exception during command execution: {e}")
            return {"success": False, "error": str(e)}

    def complete_command(self, command_id, result):
        """
        Report command completion to REST API (Phase 2).

        Args:
            command_id: The command ID to complete
            result: Dict with execution result

        Returns:
            bool: True if reported successfully
        """
        try:
            # Add cachebuster to prevent HTTP caching
            cachebuster = int(time.time() * 1000)
            url = f"{self.wordpress_url}/wp-json/babcloud/{self.api_version}/printer/{self.device_id}/commands/complete?_={cachebuster}"
            headers = {
                'X-Device-Token': self.device_token,
                'Content-Type': 'application/json'
            }

            payload = {
                'command_id': command_id,
                'status': 'success' if result.get('success') else 'failed',
                'result': result
            }

            # Only include error if it exists (WordPress REST API validates type even when null)
            if result.get('error'):
                payload['error'] = result.get('error')

            response = requests.post(url, json=payload, headers=headers, timeout=5, verify=False)

            if response.status_code == 200:
                logger.info(f"Command {command_id} completion reported")
                return True
            else:
                logger.warning(f"Failed to report completion: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error reporting completion: {e}")
            return False

    def send_heartbeat(self):
        """
        Send heartbeat to REST API (Phase 2).

        Returns:
            dict: Response data with license info
        """
        try:
            url = f"{self.wordpress_url}/wp-json/babcloud/{self.api_version}/printer/{self.device_id}/heartbeat"
            headers = {
                'X-Device-Token': self.device_token,
                'Content-Type': 'application/json'
            }

            payload = {
                'status': 'online',
                'hub_version': VERSION,
                'printer_model': self.config.get('printer', {}).get('active', '')
            }

            response = requests.post(url, json=payload, headers=headers, timeout=5, verify=False)

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Heartbeat sent successfully")
                return data
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
                return None

        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
            return None


def start_babportal_poller(config, printer):
    """
    Start the BABPortal poller in a background thread.

    Args:
        config: Full configuration dict
        printer: Active printer instance

    Returns:
        threading.Thread: Poller thread (already started)
    """
    poller = BABPortalPoller(config, printer)
    thread = threading.Thread(target=poller.poll_loop, daemon=True, name="BABPortalPoller")
    thread.start()

    logger.info("BABPortal poller thread started")
    return thread
