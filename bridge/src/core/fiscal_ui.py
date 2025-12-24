"""
Fiscal Tools UI using pywebview - Modern HTML interface for BAB-Cloud PrintHub.

Opens from system tray icon - provides full salesbook/fiscal reporting functionality.
This is a unified version that works with any printer driver implementing BasePrinter.
"""

import json
import datetime
import logging
import os
import sys
import multiprocessing

logger = logging.getLogger(__name__)


def _run_fiscal_tools_process(config_dict):
    """
    Run fiscal tools modal in a separate process.

    This allows the modal to open without blocking the main thread
    and enables multiple windows to be opened simultaneously.

    Args:
        config_dict: Configuration dictionary containing printer and software settings
    """
    try:
        # Reinitialize logging in subprocess
        from logger_module import logger as subprocess_logger
        subprocess_logger.info("Fiscal tools process started")

        # Recreate printer from config
        from printers import create_printer
        printer = create_printer(config_dict)

        # Connect to printer
        if not printer.connect():
            subprocess_logger.error("Failed to connect to printer in subprocess")
            # Continue anyway - some operations might still work

        # Run the actual modal UI (this will block until window closes)
        _open_fiscal_tools_modal_original(printer, config_dict)

        subprocess_logger.info("Fiscal tools process ended")
    except Exception as e:
        logger.error(f"Error in fiscal tools process: {e}")
        import traceback
        traceback.print_exc()


class FiscalToolsAPI:
    """
    JavaScript API bridge for fiscal printer operations.

    This class provides the backend API for the pywebview-based fiscal tools UI.
    All methods are callable from JavaScript via the pywebview API bridge.
    """

    def __init__(self, printer, config):
        """
        Initialize the Fiscal Tools API.

        Args:
            printer: Active printer instance (implements BasePrinter interface)
            config: Full configuration dict from config_manager
        """
        self.printer = printer
        self.config = config
        self.window = None  # Set after window creation

        # Check if cloud mode is enabled
        self.is_cloud_mode = config.get('mode') == 'cloud' and config.get('babportal', {}).get('enabled', False)

        # Initialize WordPress command sender for cloud mode
        self.wp_sender = None
        if self.is_cloud_mode:
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'wordpress'))
                from wordpress_command_sender import WordPressCommandSender
                self.wp_sender = WordPressCommandSender(config)
                logger.info("Cloud mode enabled: Commands will be routed through WordPress API")
            except Exception as e:
                logger.error(f"Failed to initialize WordPress command sender: {e}")
                self.is_cloud_mode = False

    def print_x_report(self):
        """Generate X report (non-fiscal daily report)."""
        try:
            logger.info("X-Report triggered from webview UI")

            # Route through WordPress in cloud mode
            if self.is_cloud_mode and self.wp_sender:
                logger.info("Cloud mode: Routing X-Report through WordPress API")
                return self.wp_sender.print_x_report()

            # Local execution
            response = self.printer.print_x_report()

            if response.get("success"):
                logger.info("X-Report printed successfully")
                return {"success": True, "message": "X Report printed successfully"}
            else:
                logger.warning(f"X-Report failed: {response.get('error')}")
                return {"success": False, "error": response.get("error", "Failed to print X Report")}
        except Exception as e:
            logger.error(f"Error printing X-Report: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report(self):
        """Print today's Z report (fiscal day closing)."""
        try:
            logger.info("Z-Report (Today) triggered from webview UI")

            # Route through WordPress in cloud mode
            if self.is_cloud_mode and self.wp_sender:
                logger.info("Cloud mode: Routing Z-Report through WordPress API")
                return self.wp_sender.print_z_report()

            # Local execution
            # Update timestamp in config
            from .config_manager import save_config
            now = datetime.datetime.now()
            self.config["fiscal_tools"]["last_z_report_print_time"] = now.isoformat()
            save_config(self.config)

            # Send command to printer
            response = self.printer.print_z_report(close_fiscal_day=True)

            if response.get("success"):
                logger.info("Z-Report printed successfully")

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

                return {"success": True, "message": "Z Report command sent to printer"}
            else:
                logger.warning(f"Z-Report response: {response.get('error', 'Unknown error')}")
                # Still return success since command was sent
                return {"success": True, "message": "Z Report command sent to printer"}
        except Exception as e:
            logger.error(f"Error printing Z-Report: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report_by_date(self, start_date, end_date):
        """
        Generate Z reports by date range.

        Args:
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
        """
        try:
            logger.info(f"Z-Report by date range triggered: {start_date} to {end_date}")

            # Route through WordPress in cloud mode
            if self.is_cloud_mode and self.wp_sender:
                logger.info("Cloud mode: Routing Z-Report by Date through WordPress API")
                return self.wp_sender.print_z_report_by_date(start_date, end_date)

            # Local execution
            # Convert string dates to date objects
            start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

            response = self.printer.print_z_report_by_date(start_date_obj, end_date_obj)

            if response.get("success"):
                logger.info("Z-Reports by date printed successfully")
                return {"success": True, "message": response.get("message", "Z Reports printed")}
            else:
                logger.warning(f"Z-Reports by date failed: {response.get('error')}")
                return {"success": False, "error": response.get("error", "Failed to print Z Reports")}
        except Exception as e:
            logger.error(f"Error printing Z-Reports by date: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report_by_number(self, number):
        """
        Generate Z report by number.

        Args:
            number: Report number (integer)
        """
        try:
            logger.info(f"Z-Report by number triggered: {number}")
            response = self.printer.print_z_report_by_number(int(number))

            if response.get("success"):
                logger.info("Z-Report by number printed successfully")
                return {"success": True, "message": response.get("message", "Z Report printed")}
            else:
                logger.warning(f"Z-Report by number failed: {response.get('error')}")
                return {"success": False, "error": response.get("error", "Failed to print Z Report")}
        except Exception as e:
            logger.error(f"Error printing Z-Report by number: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report_by_number_range(self, start_number, end_number):
        """
        Generate Z reports by number range.

        Args:
            start_number: Start report number
            end_number: End report number
        """
        try:
            logger.info(f"Z-Report by number range triggered: {start_number} to {end_number}")

            start_num = int(start_number)
            end_num = int(end_number)

            if start_num > end_num:
                return {"success": False, "error": "Start number must be less than or equal to end number"}

            # Route through WordPress in cloud mode
            if self.is_cloud_mode and self.wp_sender:
                logger.info("Cloud mode: Routing Z-Report Range through WordPress API")
                return self.wp_sender.print_z_report_range(start_num, end_num)

            # Local execution
            response = self.printer.print_z_report_by_number_range(start_num, end_num)

            if response.get("success"):
                logger.info("Z-Reports by number range printed successfully")
                return {"success": True, "message": response.get("message", "Z Reports printed")}
            else:
                logger.warning(f"Z-Reports by number range failed: {response.get('error')}")
                return {"success": False, "error": response.get("error", "Failed to print Z Reports")}
        except Exception as e:
            logger.error(f"Error printing Z-Reports by number range: {e}")
            return {"success": False, "error": str(e)}

    def reprint_document(self, document_number):
        """
        Reprint a document copy (NO SALE).

        Args:
            document_number: Document number to reprint
        """
        try:
            logger.info(f"Reprint document triggered: {document_number}")

            # Route through WordPress in cloud mode
            if self.is_cloud_mode and self.wp_sender:
                logger.info("Cloud mode: Routing Print Check through WordPress API")
                return self.wp_sender.print_check(document_number)

            # Local execution
            response = self.printer.reprint_document(str(document_number))

            if response.get("success"):
                logger.info("Document reprinted successfully")
                return {"success": True, "message": "Document copy printed (NO SALE)"}
            else:
                logger.warning(f"Reprint failed: {response.get('error')}")
                return {"success": False, "error": response.get("error", "Failed to reprint document")}
        except Exception as e:
            logger.error(f"Error reprinting document: {e}")
            return {"success": False, "error": str(e)}

    def print_no_sale(self, reason=""):
        """Open cash drawer (NO SALE receipt)."""
        try:
            logger.info(f"NO SALE triggered from webview UI{f' - Reason: {reason}' if reason else ''}")

            # Route through WordPress in cloud mode
            if self.is_cloud_mode and self.wp_sender:
                logger.info("Cloud mode: Routing No Sale through WordPress API")
                return self.wp_sender.print_no_sale(reason)

            # Local execution
            response = self.printer.print_no_sale(reason)

            if response.get("success"):
                logger.info("NO SALE printed successfully")
                return {"success": True, "message": "No Sale receipt printed"}
            else:
                logger.warning(f"NO SALE failed: {response.get('error')}")
                return {"success": False, "error": response.get("error", "Failed to print No Sale")}
        except Exception as e:
            logger.error(f"Error printing NO SALE: {e}")
            return {"success": False, "error": str(e)}

    def get_z_report_config(self):
        """
        Get Z report configuration (earliest date, last print time).

        Returns:
            dict: Z report configuration
        """
        try:
            fiscal_tools = self.config.get("fiscal_tools", {})

            # Calculate yesterday as the latest allowed date
            today = datetime.date.today()
            yesterday = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # Get last Z report print time
            last_print_time = fiscal_tools.get("last_z_report_print_time")

            # Check if today's Z report was already printed
            today_z_printed = False
            if last_print_time:
                try:
                    last_print_date = datetime.datetime.fromisoformat(last_print_time).date()
                    today_z_printed = (last_print_date == today)
                except:
                    pass

            return {
                "success": True,
                "z_report_from": fiscal_tools.get("Z_report_from", "2025-01-01"),
                "yesterday": yesterday,
                "today": today.strftime("%Y-%m-%d"),
                "today_z_printed": today_z_printed,
                "last_print_time": last_print_time
            }
        except Exception as e:
            logger.error(f"Error getting Z report config: {e}")
            return {"success": False, "error": str(e)}

    def get_config(self):
        """Return fiscal_tools config section (for TCPOS compatibility)"""
        return self.config.get("fiscal_tools", {})

    def get_min_date(self):
        """Return Z_report_from date (for TCPOS compatibility)"""
        return self.config.get("fiscal_tools", {}).get("Z_report_from", datetime.date.today().strftime("%Y-%m-%d"))

    def close_window(self):
        """Close the modal window"""
        if self.window:
            self.window.destroy()


def open_fiscal_tools_modal(printer, config):
    """
    Open the fiscal tools modal window in a separate process.

    Args:
        printer: Active printer instance (not used, config passed instead)
        config: Full configuration dict

    This function launches the fiscal tools UI in a separate process to avoid blocking
    the main thread and to allow multiple windows to be opened simultaneously.
    """
    try:
        logger.info("Launching fiscal tools modal in separate process")
        process = multiprocessing.Process(
            target=_run_fiscal_tools_process,
            args=(config,),
            daemon=True
        )
        process.start()
        logger.info("Fiscal tools modal process started")

    except Exception as e:
        logger.error(f"Error opening fiscal tools modal: {e}")
        raise


def _open_fiscal_tools_modal_original(printer, config):
    """
    Original implementation - opens fiscal tools modal (runs in subprocess).

    Args:
        printer: Active printer instance
        config: Full configuration dict
    """
    try:
        import webview
        import base64

        # Create API instance
        api = FiscalToolsAPI(printer, config)

        # Convert logo.png to base64 for embedding
        logo_base64 = ""
        try:
            if getattr(sys, 'frozen', False):
                logo_path = os.path.join(sys._MEIPASS, 'logo.png')
            else:
                # Go up 3 levels from src/core/fiscal_ui.py to bridge/
                logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logo.png')

            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_base64 = base64.b64encode(f.read()).decode('utf-8')
                logger.debug(f"Logo loaded from {logo_path}")
            else:
                logger.warning(f"Logo not found at {logo_path}")
        except Exception as e:
            logger.warning(f"Error loading logo: {e}")

        # Build HTML content with embedded logo
        if logo_base64:
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="BAB Cloud" class="h-16 w-auto">'
        else:
            # Fallback to text-based logo if image not available
            logo_html = '''<div class="bg-white p-3 rounded-lg shadow-lg">
                        <div class="text-center">
                            <div class="text-red-700 font-black text-2xl leading-none">SOLU</div>
                            <div class="bg-gray-800 text-white font-black text-xl px-2 py-1 mt-1 rounded">TECH</div>
                            <div class="text-gray-800 font-bold text-xs mt-1">BAB REPORTING</div>
                        </div>
                    </div>'''

        # HTML content for the fiscal tools UI (exact copy from TCPOS version)
        html_content = r'''
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BAB Fiscal PrintHub</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {{
            font-family: 'Inter', sans-serif;
        }}
    </style>
</head>
<body class="bg-white m-0 p-0" style="overflow: hidden;">
    <div class="bg-white max-w-4xl mx-auto" style="height: 100vh; display: flex; flex-direction: column; overflow: hidden;">

        <!-- Header with Logo -->
        <div class="bg-gradient-to-r from-red-700 to-red-800 p-4 rounded-t-2xl">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    {logo_html}
                    <div>
                        <h1 class="text-2xl font-bold text-white">Fiscal PrintHub</h1>
                        <p class="text-red-100 text-sm">Quick Report Generation</p>
                    </div>
                </div>

                <!-- Quick Actions in Header -->
                <div class="flex gap-3">
                    <!-- Receipt Copy -->
                    <div class="bg-white/10 backdrop-blur-sm rounded-xl p-3 border border-white/20">
                        <p class="text-xs text-white/90 mb-2 font-semibold">Receipt Copy</p>
                        <div class="flex gap-2">
                            <input type="text" id="check-number" class="w-32 p-2 border-0 rounded-lg text-sm" placeholder="Doc #">
                            <button onclick="printCheckCopy()" class="bg-white text-red-700 hover:bg-red-50 font-semibold px-4 py-2 rounded-lg transition duration-150 text-sm whitespace-nowrap">
                                Print Copy
                            </button>
                        </div>
                    </div>

                    <!-- No Sale -->
                    <div class="bg-white/10 backdrop-blur-sm rounded-xl p-3 border border-white/20">
                        <p class="text-xs text-white/90 mb-2 font-semibold">No Sale</p>
                        <div class="flex gap-2">
                            <input type="text" id="no-sale-reason" class="w-40 p-2 border-0 rounded-lg text-sm" placeholder="Reason (optional)">
                            <button onclick="printNoSale()" class="bg-white text-red-700 hover:bg-red-50 font-semibold px-4 py-2 rounded-lg transition duration-150 text-sm whitespace-nowrap">
                                No Sale
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="p-4 space-y-4" style="flex: 1; overflow-y: auto; overflow-x: hidden;">

            <!-- Primary Actions - Today's Reports -->
            <div class="space-y-3">
                <h2 class="text-lg font-bold text-gray-800 pb-2">Today's Reports</h2>

                <!-- Desktop: side by side, Mobile: stacked -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <!-- Z Report - Most Important -->
                    <div class="bg-red-50 border-2 border-red-600 rounded-xl p-4 shadow-md flex flex-col">
                        <div class="mb-3 flex-grow">
                            <h3 class="text-xl font-bold text-red-800 mb-1">Z Report (Today)</h3>
                            <p class="text-sm text-gray-600">Closes the fiscal day and prints the Z Report. Printer will only print if there are transactions.</p>
                        </div>
                        <button id="z-report-btn" onclick="printZReport()" class="w-full bg-red-700 hover:bg-red-800 text-white font-bold py-4 rounded-lg transition duration-150 shadow-lg hover:shadow-xl transform hover:scale-[1.02] mt-auto">
                            <span class="text-lg">Close Fiscal Day - Z Report</span>
                        </button>
                    </div>

                    <!-- X Report -->
                    <div class="bg-gray-50 border-2 border-gray-400 rounded-xl p-4 shadow-md flex flex-col">
                        <div class="mb-3 flex-grow">
                            <h3 class="text-lg font-bold text-gray-800 mb-1">X Report (Today)</h3>
                            <p class="text-sm text-gray-600">Current shift status without closing the fiscal day.</p>
                        </div>
                        <button onclick="printXReport()" class="w-full bg-gray-700 hover:bg-gray-800 text-white font-bold py-4 rounded-lg transition duration-150 shadow-md hover:shadow-lg mt-auto">
                            <span class="text-lg">Print X Report</span>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Historical Reports -->
            <div class="space-y-3">
                <h2 class="text-lg font-bold text-gray-800 pb-2">Historical Reports</h2>

                <!-- Desktop: side by side, Mobile: stacked -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <!-- Date Range -->
                    <div class="bg-white border border-gray-300 rounded-xl p-4 shadow-sm">
                        <label class="block text-sm font-bold text-gray-700 mb-3">Z Reports by Date Range</label>
                        <div class="space-y-3">
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs font-medium text-gray-600 mb-1">From (dd-mm-yy)</label>
                                    <input type="text" id="start-date" placeholder="dd-mm-yy" pattern="\d{2}-\d{2}-\d{2}" class="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm">
                                </div>
                                <div>
                                    <label class="block text-xs font-medium text-gray-600 mb-1">To (dd-mm-yy)</label>
                                    <input type="text" id="end-date" placeholder="dd-mm-yy" pattern="\d{2}-\d{2}-\d{2}" class="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm">
                                </div>
                            </div>
                            <button onclick="printZByDateRange()" class="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-2.5 rounded-lg transition duration-150 shadow-md text-sm">
                                Print Date Range
                            </button>
                        </div>
                    </div>

                    <!-- Number Range -->
                    <div class="bg-white border border-gray-300 rounded-xl p-4 shadow-sm">
                        <label class="block text-sm font-bold text-gray-700 mb-3">Z Reports by Number Range</label>
                        <div class="space-y-3">
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs font-medium text-gray-600 mb-1">Start #</label>
                                    <input type="number" id="start-number" class="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm" placeholder="100" min="1">
                                </div>
                                <div>
                                    <label class="block text-xs font-medium text-gray-600 mb-1">End #</label>
                                    <input type="number" id="end-number" class="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm" placeholder="150" min="1">
                                </div>
                            </div>
                            <button onclick="printZByNumberRange()" class="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-2.5 rounded-lg transition duration-150 shadow-md text-sm">
                                Print Number Range
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Status Display -->
            <div id="status-message" class="hidden p-4 rounded-lg text-sm font-medium"></div>
        </div>

        <!-- Footer -->
        <div class="bg-gray-50 px-4 py-3 border-t border-gray-200" style="flex-shrink: 0;">
            <button onclick="closeModal()" class="w-full bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2.5 rounded-lg transition duration-150">
                Close
            </button>
        </div>
    </div>

    <script>
        // Status message helper
        function showStatus(message, type = 'info') {
            const statusEl = document.getElementById('status-message');
            statusEl.classList.remove('hidden', 'bg-green-100', 'text-green-800', 'bg-red-100', 'text-red-800', 'bg-blue-100', 'text-blue-800');

            if (type === 'success') {
                statusEl.classList.add('bg-green-100', 'text-green-800');
            } else if (type === 'error') {
                statusEl.classList.add('bg-red-100', 'text-red-800');
            } else {
                statusEl.classList.add('bg-blue-100', 'text-blue-800');
            }

            statusEl.textContent = message;

            setTimeout(() => {
                statusEl.classList.add('hidden');
            }, 5000);
        }

        // Initialize on load
        window.addEventListener('pywebviewready', function() {
            initializeUI();
        });

        async function initializeUI() {
            try {
                const config = await pywebview.api.get_config();
                const minDate = await pywebview.api.get_min_date();

                // Set date constraints
                const today = new Date().toISOString().split('T')[0];
                const yesterday = new Date();
                yesterday.setDate(yesterday.getDate() - 1);

                // Format dates as dd-mm-yy
                const formatDateDDMMYY = (date) => {
                    const dd = String(date.getDate()).padStart(2, '0');
                    const mm = String(date.getMonth() + 1).padStart(2, '0');
                    const yy = String(date.getFullYear()).slice(-2);
                    return `${dd}-${mm}-${yy}`;
                };

                document.getElementById('start-date').value = formatDateDDMMYY(yesterday);
                document.getElementById('end-date').value = formatDateDDMMYY(yesterday);
            } catch (error) {
                console.error('Error initializing UI:', error);
                showStatus('Error loading configuration', 'error');
            }
        }

        // Main functions
        async function printZReport() {
            showStatus('Processing Z Report (closing fiscal day)...', 'info');
            try {
                const result = await pywebview.api.print_z_report();
                if (result.success) {
                    showStatus('✓ ' + result.message, 'success');
                } else {
                    showStatus('✗ ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('Error: ' + error, 'error');
            }
        }

        async function printXReport() {
            showStatus('Processing X Report...', 'info');
            try {
                const result = await pywebview.api.print_x_report();
                if (result.success) {
                    showStatus('✓ ' + result.message, 'success');
                } else {
                    showStatus('✗ ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('Error: ' + error, 'error');
            }
        }

        async function printZByDateRange() {
            const startDateInput = document.getElementById('start-date').value;
            const endDateInput = document.getElementById('end-date').value;

            if (!startDateInput || !endDateInput) {
                showStatus('Please enter both start and end dates.', 'error');
                return;
            }

            // Validate format dd-mm-yy
            const datePattern = /^(\d{2})-(\d{2})-(\d{2})$/;
            const startMatch = startDateInput.match(datePattern);
            const endMatch = endDateInput.match(datePattern);

            if (!startMatch || !endMatch) {
                showStatus('Invalid date format. Please use dd-mm-yy (e.g., 19-12-25)', 'error');
                return;
            }

            // Convert dd-mm-yy to yyyy-mm-dd for API
            const parseDateDDMMYY = (dateStr) => {
                const [dd, mm, yy] = dateStr.split('-');
                const year = parseInt(yy) < 50 ? `20${yy}` : `19${yy}`;  // Assume 00-49 = 2000s, 50-99 = 1900s
                return `${year}-${mm}-${dd}`;
            };

            const startDate = parseDateDDMMYY(startDateInput);
            const endDate = parseDateDDMMYY(endDateInput);

            showStatus(`Processing Z Reports from ${startDateInput} to ${endDateInput}...`, 'info');
            try {
                const result = await pywebview.api.print_z_report_by_date(startDate, endDate);
                if (result.success) {
                    showStatus('✓ ' + result.message, 'success');
                } else {
                    showStatus('✗ ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('Error: ' + error, 'error');
            }
        }

        async function printZByNumberRange() {
            const startNum = document.getElementById('start-number').value;
            const endNum = document.getElementById('end-number').value;

            if (!startNum || !endNum) {
                showStatus('Please enter both start and end numbers.', 'error');
                return;
            }

            showStatus(`Processing Z Reports #${startNum} to #${endNum}...`, 'info');
            try {
                const result = await pywebview.api.print_z_report_by_number_range(startNum, endNum);
                if (result.success) {
                    showStatus('✓ ' + result.message, 'success');
                } else {
                    showStatus('✗ ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('Error: ' + error, 'error');
            }
        }

        async function printCheckCopy() {
            const checkNumber = document.getElementById('check-number').value.trim();

            if (!checkNumber) {
                showStatus('Document number is required.', 'error');
                return;
            }

            showStatus(`Printing copy of document ${checkNumber}...`, 'info');
            try {
                const result = await pywebview.api.reprint_document(checkNumber);
                if (result.success) {
                    showStatus('✓ ' + result.message, 'success');
                    document.getElementById('check-number').value = '';
                } else {
                    showStatus('✗ ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('Error: ' + error, 'error');
            }
        }

        async function printNoSale() {
            const reason = document.getElementById('no-sale-reason').value.trim();

            showStatus('Printing No Sale receipt...', 'info');
            try {
                const result = await pywebview.api.print_no_sale(reason);
                if (result.success) {
                    showStatus('✓ ' + result.message, 'success');
                    document.getElementById('no-sale-reason').value = '';
                } else {
                    showStatus('✗ ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('Error: ' + error, 'error');
            }
        }

        function closeModal() {
            pywebview.api.close_window();
        }
    </script>
</body>
</html>
        '''

        # Replace logo placeholder with actual logo HTML
        html_content = html_content.replace('{logo_html}', logo_html)

        # Add favicon to head section if logo exists
        if logo_base64:
            favicon_tag = f'<link rel="icon" type="image/png" href="data:image/png;base64,{logo_base64}">'
            html_content = html_content.replace('<title>BAB Fiscal PrintHub</title>', f'<title>BAB Fiscal PrintHub</title>\n    {favicon_tag}')

        # Create and show the window
        window = webview.create_window(
            title="BAB Cloud - Fiscal Tools",
            html=html_content,
            js_api=api,
            width=900,
            height=800,
            resizable=True,
            min_size=(700, 600)
        )

        api.window = window
        webview.start()

        logger.info("Fiscal tools modal closed")

    except Exception as e:
        logger.error(f"Error opening fiscal tools modal: {e}")
        raise
