"""
WordPress Z-Report Poller Module

Polls WordPress portal for Z-report trigger flags and executes Z-reports.
Refactored to be config-agnostic and work with any printer driver.

PoC Implementation - Phase 1 (temporary until Portal system is built)
"""

import time
import requests
import urllib3
import logging
import threading

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class WordPressPoller:
    """Handles polling WordPress for Z-report triggers."""

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

        # WordPress configuration
        wp_config = config.get('wordpress', {})
        self.wordpress_url = wp_config.get('url', '')
        self.poll_interval = wp_config.get('poll_interval', 5)
        self.trigger_endpoint = wp_config.get('trigger_endpoint', '/wp-content/zreport.flag')
        self.complete_endpoint = wp_config.get('complete_endpoint', '/zreport-complete.php')

        logger.info(f"WordPress Poller initialized")
        logger.info(f"  URL: {self.wordpress_url}")
        logger.info(f"  Poll interval: {self.poll_interval}s")

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
        Execute the Z-report print (or X-report for testing).

        Returns:
            dict: Result from printer with 'success' and 'error' keys
        """
        logger.info("Executing X-report (test mode)...")
        try:
            # Using X-report for testing since it can be run repeatedly
            # In production, this would call: self.printer.print_z_report()
            result = self.printer.print_x_report()
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
        logger.info("Starting WordPress report polling loop (X-report test mode)...")
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
        logger.info("WordPress poller stopped")

    def stop(self):
        """Stop the polling loop gracefully."""
        logger.info("Stopping WordPress poller...")
        self.stop_event.set()


def start_wordpress_poller(config, printer):
    """
    Start the WordPress poller in a background thread.

    Args:
        config: Full configuration dict
        printer: Active printer instance

    Returns:
        threading.Thread: Poller thread (already started)
    """
    poller = WordPressPoller(config, printer)
    thread = threading.Thread(target=poller.poll_loop, daemon=True, name="WordPressPoller")
    thread.start()

    logger.info("WordPress poller thread started")
    return thread
