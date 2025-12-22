"""
WordPress Command Sender for Cloud Mode

In cloud mode, local UI actions (system tray, modal) should send commands
to WordPress REST API instead of executing locally on the printer.

This ensures:
1. All commands go through the portal's REST API
2. Consistent command flow in cloud vs local mode
3. Proper authentication and logging
"""

import requests
import logging
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

logger = logging.getLogger(__name__)


class WordPressCommandSender:
    """
    Sends commands to WordPress REST API to queue printer operations.
    Used in cloud mode when local UI (modal/system tray) is activated.
    """

    def __init__(self, config):
        """
        Initialize WordPress command sender.

        Args:
            config: Full config dict containing babportal settings
        """
        self.config = config
        self.wordpress_config = config.get('babportal', {})
        self.wordpress_url = self.wordpress_config.get('url')
        self.device_id = self.wordpress_config.get('device_id')
        self.device_token = self.wordpress_config.get('device_token')

    def _send_command(self, command_type, params=None):
        """
        Send a command to WordPress REST API.

        Args:
            command_type: Type of command (zreport, xreport, print_check, no_sale, etc.)
            params: Optional dict of command parameters

        Returns:
            dict: Response with success/error
        """
        if not all([self.wordpress_url, self.device_id, self.device_token]):
            logger.error(f"Portal API not configured - URL: {self.wordpress_url}, Device ID: {self.device_id}, Token present: {bool(self.device_token)}")
            return {"success": False, "error": "Portal API not configured"}

        url = f"{self.wordpress_url}/wp-json/babcloud/v1/printer/{self.device_id}/trigger/{command_type}"

        headers = {
            'X-Device-Token': self.device_token,
            'Content-Type': 'application/json'
        }

        payload = params or {}

        try:
            logger.info(f"Sending command to Portal: {command_type}")
            logger.debug(f"  URL: {url}")
            logger.debug(f"  Device ID: {self.device_id}")
            logger.debug(f"  Token (first 10 chars): {self.device_token[:10] if self.device_token else 'None'}...")
            response = requests.post(url, json=payload, headers=headers, verify=False, timeout=5)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Command queued successfully: {data.get('command_id')}")
                return {
                    "success": True,
                    "message": f"Command queued. Check back in a few seconds.",
                    "command_id": data.get('command_id')
                }
            else:
                logger.error(f"Failed to queue command: {response.status_code}")
                if response.status_code == 401:
                    logger.error("  Authentication failed - check device_token in config.json and device_token_hash in WordPress")
                try:
                    error_data = response.json()
                    logger.error(f"  Response: {error_data}")
                except:
                    logger.error(f"  Response text: {response.text}")
                return {
                    "success": False,
                    "error": f"Failed to queue command: {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Exception sending command to WordPress: {e}")
            return {
                "success": False,
                "error": f"Failed to connect to Portal: {str(e)}"
            }

    def print_x_report(self):
        """Queue X-Report via WordPress."""
        return self._send_command('xreport')

    def print_z_report(self):
        """Queue Z-Report via WordPress."""
        return self._send_command('zreport')

    def print_check(self):
        """Queue Print Check via WordPress."""
        return self._send_command('print_check')

    def print_no_sale(self):
        """Queue No Sale via WordPress."""
        return self._send_command('no_sale')

    def print_z_report_range(self, from_z, to_z):
        """Queue Z-Report Range via WordPress."""
        return self._send_command('zreport_range', {'from_z': from_z, 'to_z': to_z})

    def print_z_report_by_date(self, date_str):
        """Queue Z-Report by Date via WordPress."""
        return self._send_command('zreport_date', {'date': date_str})
