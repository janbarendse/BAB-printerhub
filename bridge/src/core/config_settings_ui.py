"""
Config Settings UI using pywebview - Visual editor for config.json.

Opens from system tray icon - provides role-based configuration editing.
User roles are checked via WordPress Application Password authentication.
"""

import json
import logging
import os
import sys
import multiprocessing
import requests
import base64

logger = logging.getLogger(__name__)


def _run_config_settings_process(config_path, config_dict):
    """
    Run config settings modal in a separate process.

    This allows the modal to open without blocking the main thread.

    Args:
        config_path: Path to config.json file
        config_dict: Current configuration dictionary
    """
    try:
        # Reinitialize logging in subprocess
        from src.logger_module import logger as subprocess_logger
        subprocess_logger.info("Config settings process started")

        # Run the actual modal UI (this will block until window closes)
        _open_config_settings_window(config_path, config_dict)

        subprocess_logger.info("Config settings process ended")
    except Exception as e:
        logger.error(f"Error in config settings process: {e}")
        import traceback
        traceback.print_exc()


class ConfigAPI:
    """
    JavaScript API bridge for config editing operations.

    This class provides the backend API for the pywebview-based settings UI.
    All methods are callable from JavaScript via the pywebview API bridge.
    """

    def __init__(self, config_path, config):
        """
        Initialize the Config Settings API.

        Args:
            config_path: Path to config.json file
            config: Current configuration dict
        """
        self.config_path = config_path
        self.config = config
        self.window = None  # Set after window creation
        self.user_role = None  # Cached user role from WordPress

    def get_user_role(self):
        """
        Get user role from WordPress using Application Password authentication.

        Returns:
            dict: {'success': bool, 'role': str, 'error': str}
        """
        try:
            logger.info("Checking user role via WordPress API")

            # Get WordPress credentials from config
            wp_config = self.config.get('babportal', {})
            username = wp_config.get('wordpress_username', '').strip()
            app_password = wp_config.get('wordpress_app_password', '').strip()
            base_url = wp_config.get('url', '').rstrip('/')

            if not username or not app_password:
                logger.warning("WordPress credentials not configured - defaulting to local administrator mode")
                return {
                    'success': True,
                    'role': 'administrator',  # Local mode: full access
                    'username': 'Local User',
                    'message': 'No WordPress credentials - using local mode'
                }

            # Call WordPress REST API to get current user info
            url = f"{base_url}/wp-json/wp/v2/users/me"
            auth_string = f"{username}:{app_password}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

            headers = {
                'Authorization': f'Basic {auth_b64}'
            }

            response = requests.get(url, headers=headers, timeout=5, verify=False)

            if response.status_code == 200:
                data = response.json()
                user_roles = data.get('roles', [])
                username_display = data.get('name', username)

                # Determine highest privilege role
                if 'administrator' in user_roles:
                    role = 'administrator'
                elif 'shop_manager' in user_roles:
                    role = 'shop_manager'
                else:
                    role = 'customer'

                self.user_role = role  # Cache for later use
                logger.info(f"User role determined: {role} ({username_display})")

                return {
                    'success': True,
                    'role': role,
                    'username': username_display
                }
            else:
                logger.error(f"Failed to get user info: {response.status_code} - falling back to local administrator mode")
                return {
                    'success': True,
                    'role': 'administrator',  # Fallback to local mode
                    'username': 'Local User',
                    'message': f'WordPress API error ({response.status_code}) - using local mode'
                }

        except Exception as e:
            logger.error(f"Error getting user role: {e} - falling back to local administrator mode")
            return {
                'success': True,
                'role': 'administrator',  # Fallback to local mode
                'username': 'Local User',
                'message': f'WordPress API unavailable - using local mode'
            }

    def get_config(self):
        """
        Get current configuration.

        Returns:
            dict: Current configuration
        """
        return self.config

    def get_editable_fields(self):
        """
        Get list of editable fields.

        Note: All fields are editable for local configuration management.
        Role checking removed per user request.

        Returns:
            dict: All fields are editable
        """
        # Always return full access - no role restrictions
        return {
            'software': ['active', 'odoo', 'tcpos', 'simphony', 'quickbooks'],
            'printer': ['active', 'cts310ii', 'star', 'citizen', 'epson'],
            'client': ['NKF'],
            'miscellaneous': ['default_client_name', 'default_client_crib'],
            'polling': ['printer_retry_interval_seconds', 'software_retry_interval_seconds'],
            'mode': True,
            'babportal': ['enabled', 'url', 'poll_interval', 'device_id', 'device_token', 'wordpress_username', 'wordpress_app_password'],
            'system': ['log_level']
        }

    def validate_config(self, changes):
        """
        Validate configuration changes.

        Args:
            changes: Dict of proposed changes

        Returns:
            dict: {'success': bool, 'errors': list}
        """
        errors = []

        # Validate mode
        if 'mode' in changes:
            if changes['mode'] not in ['standalone', 'cloud']:
                errors.append("Mode must be 'standalone' or 'cloud'")

        # Validate software active
        if 'software' in changes and 'active' in changes['software']:
            valid_software = ['odoo', 'tcpos', 'simphony', 'quickbooks']
            if changes['software']['active'] not in valid_software:
                errors.append(f"Invalid software: {changes['software']['active']}")

        # Validate printer active
        if 'printer' in changes and 'active' in changes['printer']:
            valid_printers = ['cts310ii', 'star', 'citizen', 'epson']
            if changes['printer']['active'] not in valid_printers:
                errors.append(f"Invalid printer: {changes['printer']['active']}")

        # Validate polling intervals
        if 'polling' in changes:
            for key in ['printer_retry_interval_seconds', 'software_retry_interval_seconds']:
                if key in changes['polling']:
                    try:
                        value = int(changes['polling'][key])
                        if value < 1 or value > 300:
                            errors.append(f"{key} must be between 1 and 300 seconds")
                    except ValueError:
                        errors.append(f"{key} must be a number")

        # Validate babportal poll_interval
        if 'babportal' in changes and 'poll_interval' in changes['babportal']:
            try:
                value = int(changes['babportal']['poll_interval'])
                if value < 1 or value > 60:
                    errors.append("BABPortal poll interval must be between 1 and 60 seconds")
            except ValueError:
                errors.append("BABPortal poll interval must be a number")

        # Validate system log_level
        if 'system' in changes and 'log_level' in changes['system']:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if changes['system']['log_level'] not in valid_levels:
                errors.append(f"Invalid log level: {changes['system']['log_level']}")

        if errors:
            return {'success': False, 'errors': errors}
        else:
            return {'success': True, 'errors': []}

    def save_config(self, changes):
        """
        Save configuration changes.

        Args:
            changes: Dict of changes to apply

        Returns:
            dict: {'success': bool, 'message': str, 'error': str}
        """
        try:
            logger.info(f"Saving configuration changes: {json.dumps(changes, indent=2)}")

            # Validate changes first
            validation = self.validate_config(changes)
            if not validation['success']:
                logger.error(f"Validation failed: {validation['errors']}")
                return {
                    'success': False,
                    'error': 'Validation failed: ' + ', '.join(validation['errors'])
                }

            # Get editable fields
            editable = self.get_editable_fields()

            # Merge changes into config (only editable fields)
            updated_config = self.config.copy()

            # Update mode (if editable)
            if 'mode' in changes and editable.get('mode', False):
                updated_config['mode'] = changes['mode']

            # Update sections
            for section in ['software', 'printer', 'client', 'miscellaneous', 'polling', 'babportal', 'system']:
                if section in changes:
                    if section not in updated_config:
                        updated_config[section] = {}

                    # Only update editable fields in this section
                    editable_fields = editable.get(section, [])
                    for key, value in changes[section].items():
                        if key in editable_fields or editable_fields == [section]:
                            # Handle nested config (e.g., software.odoo, printer.cts310ii)
                            if isinstance(value, dict):
                                if key not in updated_config[section]:
                                    updated_config[section][key] = {}
                                updated_config[section][key].update(value)
                            else:
                                updated_config[section][key] = value

            # Save to file
            with open(self.config_path, 'w') as f:
                json.dump(updated_config, f, indent=2)

            logger.info(f"Configuration saved successfully to {self.config_path}")

            # Trigger application restart after save
            import threading
            threading.Timer(2.0, self._restart_application).start()

            return {
                'success': True,
                'message': 'Configuration saved successfully. Restarting BAB PrintHub...'
            }

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

    def _restart_application(self):
        """Restart the application to apply configuration changes."""
        try:
            import sys
            import os
            import subprocess

            logger.info("Restarting application to apply configuration changes...")

            # Get the executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                executable = sys.executable
                logger.info(f"Restarting executable: {executable}")
                subprocess.Popen([executable], cwd=os.path.dirname(executable))
            else:
                # Running as script
                python = sys.executable
                script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'fiscal_printer_hub.py')
                logger.info(f"Restarting script: {python} {script}")
                subprocess.Popen([python, script])

            # Exit current instance
            os._exit(0)

        except Exception as e:
            logger.error(f"Error restarting application: {e}")

    def close_window(self):
        """Close the settings window."""
        if self.window:
            self.window.destroy()


def _open_config_settings_window(config_path, config):
    """
    Open the config settings window using pywebview.

    Args:
        config_path: Path to config.json file
        config: Current configuration dict
    """
    try:
        import webview

        logger.info("Opening config settings window")

        # Create API instance
        api = ConfigAPI(config_path, config)

        # Load logo if exists
        logo_base64 = None
        logo_html = '<div class="w-16 h-16 bg-gradient-to-br from-red-600 to-red-800 rounded-xl flex items-center justify-center text-white font-black text-3xl">B</div>'

        if getattr(sys, 'frozen', False):
            logo_path = os.path.join(sys._MEIPASS, 'logo.png')
        else:
            logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logo.png')

        if os.path.exists(logo_path):
            try:
                import base64
                with open(logo_path, 'rb') as f:
                    logo_base64 = base64.b64encode(f.read()).decode('ascii')
                logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="BAB Logo" class="w-16 h-16 rounded-xl">'
            except Exception as e:
                logger.warning(f"Could not load logo: {e}")

        # HTML content for the settings UI
        html_content = r'''
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BAB PrintHub Settings</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {
            font-family: 'Inter', sans-serif;
        }
        .role-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .role-admin {
            background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
            color: white;
        }
        .role-shop_manager {
            background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
            color: white;
        }
        .role-customer {
            background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
            color: white;
        }
    </style>
</head>
<body class="bg-gray-100 m-0 p-0">
    <div class="bg-white max-w-6xl mx-auto shadow-2xl" style="height: 100vh; display: flex; flex-direction: column; overflow: hidden;">

        <!-- Header -->
        <div class="bg-gradient-to-r from-red-700 to-red-800 p-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    {logo_html}
                    <div>
                        <h1 class="text-3xl font-bold text-white">Settings</h1>
                        <p class="text-red-100 text-sm">BAB PrintHub Configuration</p>
                    </div>
                </div>
                <div id="role-badge" class="role-badge role-customer">
                    <span id="role-text">Loading...</span>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="p-6 space-y-6" style="flex: 1; overflow-y: auto;">

            <!-- Status Message -->
            <div id="status-message" class="hidden rounded-lg p-4 mb-4"></div>

            <!-- Software Section -->
            <div class="bg-white border-2 border-gray-200 rounded-xl p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Software Integration</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Active Software</label>
                        <select id="software-active" class="w-full p-3 border-2 border-gray-300 rounded-lg">
                            <option value="odoo">Odoo</option>
                            <option value="tcpos">TCPOS</option>
                            <option value="simphony">Simphony</option>
                            <option value="quickbooks">QuickBooks</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Printer Section -->
            <div class="bg-white border-2 border-gray-200 rounded-xl p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Printer Configuration</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Active Printer</label>
                        <select id="printer-active" class="w-full p-3 border-2 border-gray-300 rounded-lg">
                            <option value="cts310ii">CTS310ii</option>
                            <option value="star">Star</option>
                            <option value="citizen">Citizen</option>
                            <option value="epson">Epson</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">COM Port</label>
                        <input type="text" id="printer-com-port" class="w-full p-3 border-2 border-gray-300 rounded-lg" placeholder="COM4">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Baud Rate</label>
                        <select id="printer-baud-rate" class="w-full p-3 border-2 border-gray-300 rounded-lg">
                            <option value="9600">9600</option>
                            <option value="19200">19200</option>
                            <option value="38400">38400</option>
                            <option value="57600">57600</option>
                            <option value="115200">115200</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Mode Section -->
            <div class="bg-white border-2 border-gray-200 rounded-xl p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Operation Mode</h2>
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Mode</label>
                    <select id="mode" class="w-full p-3 border-2 border-gray-300 rounded-lg">
                        <option value="standalone">Standalone</option>
                        <option value="cloud">Cloud</option>
                    </select>
                    <p class="text-xs text-gray-500 mt-2">Cloud mode enables BABPortal integration</p>
                </div>
            </div>

            <!-- BABPortal Section -->
            <div class="bg-white border-2 border-gray-200 rounded-xl p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">BABPortal Configuration</h2>
                <div class="space-y-4">
                    <div class="flex items-center">
                        <input type="checkbox" id="babportal-enabled" class="w-5 h-5 text-red-600">
                        <label class="ml-3 text-sm font-semibold text-gray-700">Enable BABPortal</label>
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Portal URL</label>
                        <input type="text" id="babportal-url" class="w-full p-3 border-2 border-gray-300 rounded-lg" placeholder="https://babcloud.linux">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Device ID</label>
                        <input type="text" id="babportal-device-id" class="w-full p-3 border-2 border-gray-300 rounded-lg" placeholder="chichi-printer-1">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Device Token</label>
                        <input type="password" id="babportal-device-token" class="w-full p-3 border-2 border-gray-300 rounded-lg" placeholder="••••••••••••••••">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Poll Interval (seconds)</label>
                        <input type="number" id="babportal-poll-interval" class="w-full p-3 border-2 border-gray-300 rounded-lg" min="1" max="60" value="3">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">WordPress Username</label>
                        <input type="text" id="babportal-wp-username" class="w-full p-3 border-2 border-gray-300 rounded-lg" placeholder="username">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">WordPress App Password</label>
                        <input type="password" id="babportal-wp-password" class="w-full p-3 border-2 border-gray-300 rounded-lg" placeholder="xxxx xxxx xxxx xxxx xxxx xxxx">
                    </div>
                </div>
            </div>

            <!-- Polling Section -->
            <div class="bg-white border-2 border-gray-200 rounded-xl p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Polling Configuration</h2>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Printer Retry Interval (seconds)</label>
                        <input type="number" id="polling-printer-retry" class="w-full p-3 border-2 border-gray-300 rounded-lg" min="1" max="300" value="5">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700 mb-2">Software Retry Interval (seconds)</label>
                        <input type="number" id="polling-software-retry" class="w-full p-3 border-2 border-gray-300 rounded-lg" min="1" max="300" value="10">
                    </div>
                </div>
            </div>

            <!-- System Section -->
            <div class="bg-white border-2 border-gray-200 rounded-xl p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">System Configuration</h2>
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Log Level</label>
                    <select id="system-log-level" class="w-full p-3 border-2 border-gray-300 rounded-lg">
                        <option value="DEBUG">DEBUG</option>
                        <option value="INFO">INFO</option>
                        <option value="WARNING">WARNING</option>
                        <option value="ERROR">ERROR</option>
                        <option value="CRITICAL">CRITICAL</option>
                    </select>
                </div>
            </div>

        </div>

        <!-- Footer Buttons -->
        <div class="bg-gray-50 p-6 border-t-2 border-gray-200 flex justify-end space-x-4">
            <button onclick="closeModal()" class="px-6 py-3 bg-gray-300 hover:bg-gray-400 text-gray-800 font-semibold rounded-lg transition duration-150">
                Cancel
            </button>
            <button onclick="saveConfig()" class="px-6 py-3 bg-red-700 hover:bg-red-800 text-white font-semibold rounded-lg transition duration-150">
                Save Configuration
            </button>
        </div>

    </div>

    <script>
        let currentRole = 'customer';
        let editableFields = {};
        let originalConfig = {};

        // Show status message
        function showStatus(message, type) {
            const statusEl = document.getElementById('status-message');
            statusEl.className = `rounded-lg p-4 mb-4 ${type === 'success' ? 'bg-green-100 text-green-800' : type === 'error' ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`;
            statusEl.textContent = message;
            statusEl.classList.remove('hidden');

            // Auto-hide after 5 seconds
            setTimeout(() => {
                statusEl.classList.add('hidden');
            }, 5000);
        }

        // Initialize UI
        window.addEventListener('pywebviewready', function() {
            console.log('pywebview ready, initializing...');
            initializeUI();
        });

        async function initializeUI() {
            try {
                // Get user role
                const roleResult = await pywebview.api.get_user_role();
                if (roleResult.success) {
                    currentRole = roleResult.role;
                    document.getElementById('role-text').textContent = roleResult.username || currentRole;
                    document.getElementById('role-badge').className = `role-badge role-${currentRole}`;
                } else {
                    showStatus('Warning: ' + roleResult.error, 'error');
                }

                // Get editable fields
                editableFields = await pywebview.api.get_editable_fields();

                // Get current config
                const config = await pywebview.api.get_config();
                originalConfig = JSON.parse(JSON.stringify(config));  // Deep copy

                // Populate form
                populateForm(config);

                // Apply permissions
                applyPermissions();

                console.log('UI initialized successfully');
            } catch (error) {
                console.error('Error initializing UI:', error);
                showStatus('Error initializing settings: ' + error, 'error');
            }
        }

        function populateForm(config) {
            // Software
            if (config.software) {
                setValueIfExists('software-active', config.software.active);
            }

            // Printer
            if (config.printer) {
                setValueIfExists('printer-active', config.printer.active);
                const activePrinter = config.printer[config.printer.active];
                if (activePrinter) {
                    setValueIfExists('printer-com-port', activePrinter.com_port);
                    setValueIfExists('printer-baud-rate', activePrinter.baud_rate);
                }
            }

            // Mode
            setValueIfExists('mode', config.mode);

            // BABPortal
            if (config.babportal) {
                setCheckedIfExists('babportal-enabled', config.babportal.enabled);
                setValueIfExists('babportal-url', config.babportal.url);
                setValueIfExists('babportal-device-id', config.babportal.device_id);
                setValueIfExists('babportal-device-token', config.babportal.device_token);
                setValueIfExists('babportal-poll-interval', config.babportal.poll_interval);
                setValueIfExists('babportal-wp-username', config.babportal.wordpress_username);
                setValueIfExists('babportal-wp-password', config.babportal.wordpress_app_password);
            }

            // Polling
            if (config.polling) {
                setValueIfExists('polling-printer-retry', config.polling.printer_retry_interval_seconds);
                setValueIfExists('polling-software-retry', config.polling.software_retry_interval_seconds);
            }

            // System
            if (config.system) {
                setValueIfExists('system-log-level', config.system.log_level);
            }
        }

        function setValueIfExists(id, value) {
            const el = document.getElementById(id);
            if (el && value !== undefined && value !== null) {
                el.value = value;
            }
        }

        function setCheckedIfExists(id, value) {
            const el = document.getElementById(id);
            if (el && value !== undefined && value !== null) {
                el.checked = value;
            }
        }

        function applyPermissions() {
            // Software
            if (!editableFields.software || !editableFields.software.includes('active')) {
                disableField('software-active');
            }

            // Printer
            if (!editableFields.printer || !editableFields.printer.includes('active')) {
                disableField('printer-active');
            }
            if (!editableFields.printer || editableFields.printer.length === 0) {
                disableField('printer-com-port');
                disableField('printer-baud-rate');
            }

            // Mode
            if (!editableFields.mode) {
                disableField('mode');
            }

            // BABPortal
            if (!editableFields.babportal || !editableFields.babportal.includes('enabled')) {
                disableField('babportal-enabled');
            }
            if (!editableFields.babportal || !editableFields.babportal.includes('url')) {
                disableField('babportal-url');
            }
            if (!editableFields.babportal || !editableFields.babportal.includes('device_id')) {
                disableField('babportal-device-id');
            }
            if (!editableFields.babportal || !editableFields.babportal.includes('device_token')) {
                disableField('babportal-device-token');
            }
            if (!editableFields.babportal || !editableFields.babportal.includes('poll_interval')) {
                disableField('babportal-poll-interval');
            }
            if (!editableFields.babportal || !editableFields.babportal.includes('wordpress_username')) {
                disableField('babportal-wp-username');
            }
            if (!editableFields.babportal || !editableFields.babportal.includes('wordpress_app_password')) {
                disableField('babportal-wp-password');
            }

            // Polling
            if (!editableFields.polling || editableFields.polling.length === 0) {
                disableField('polling-printer-retry');
                disableField('polling-software-retry');
            }

            // System
            if (!editableFields.system || !editableFields.system.includes('log_level')) {
                disableField('system-log-level');
            }
        }

        function disableField(id) {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = true;
                el.classList.add('bg-gray-200', 'cursor-not-allowed');
            }
        }

        async function saveConfig() {
            try {
                showStatus('Saving configuration...', 'info');

                // Collect changes
                const changes = {};

                // Software
                changes.software = {
                    active: document.getElementById('software-active').value
                };

                // Printer
                const printerActive = document.getElementById('printer-active').value;
                changes.printer = {
                    active: printerActive,
                    [printerActive]: {
                        com_port: document.getElementById('printer-com-port').value,
                        baud_rate: parseInt(document.getElementById('printer-baud-rate').value)
                    }
                };

                // Mode
                changes.mode = document.getElementById('mode').value;

                // BABPortal
                changes.babportal = {
                    enabled: document.getElementById('babportal-enabled').checked,
                    url: document.getElementById('babportal-url').value,
                    device_id: document.getElementById('babportal-device-id').value,
                    device_token: document.getElementById('babportal-device-token').value,
                    poll_interval: parseInt(document.getElementById('babportal-poll-interval').value),
                    wordpress_username: document.getElementById('babportal-wp-username').value,
                    wordpress_app_password: document.getElementById('babportal-wp-password').value
                };

                // Polling
                changes.polling = {
                    printer_retry_interval_seconds: parseInt(document.getElementById('polling-printer-retry').value),
                    software_retry_interval_seconds: parseInt(document.getElementById('polling-software-retry').value)
                };

                // System
                changes.system = {
                    log_level: document.getElementById('system-log-level').value
                };

                // Save via API
                const result = await pywebview.api.save_config(changes);

                if (result.success) {
                    showStatus(result.message, 'success');
                    setTimeout(() => {
                        closeModal();
                    }, 2000);
                } else {
                    showStatus('Error: ' + result.error, 'error');
                }

            } catch (error) {
                console.error('Error saving config:', error);
                showStatus('Error saving configuration: ' + error, 'error');
            }
        }

        function closeModal() {
            pywebview.api.close_window();
        }
    </script>
</body>
</html>
        '''

        # Replace logo placeholder
        html_content = html_content.replace('{logo_html}', logo_html)

        # Add favicon if logo exists
        if logo_base64:
            favicon_tag = f'<link rel="icon" type="image/png" href="data:image/png;base64,{logo_base64}">'
            html_content = html_content.replace('<title>BAB PrintHub Settings</title>', f'<title>BAB PrintHub Settings</title>\n    {favicon_tag}')

        # Create and show the window
        window = webview.create_window(
            title="BAB Cloud - Settings",
            html=html_content,
            js_api=api,
            width=1000,
            height=900,
            resizable=True,
            min_size=(800, 700)
        )

        api.window = window
        webview.start()

        logger.info("Config settings window closed")

    except Exception as e:
        logger.error(f"Error opening config settings window: {e}")
        raise


def open_config_settings_modal(config_path, config):
    """
    Open config settings modal in a separate process (non-blocking).

    Args:
        config_path: Path to config.json file
        config: Current configuration dict
    """
    try:
        logger.info("Launching config settings modal in separate process")
        process = multiprocessing.Process(
            target=_run_config_settings_process,
            args=(config_path, config),
            daemon=True
        )
        process.start()
        logger.info(f"Config settings process started (PID: {process.pid})")
    except Exception as e:
        logger.error(f"Error launching config settings modal: {e}")
        raise
