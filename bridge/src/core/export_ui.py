"""
Export UI using pywebview - Modern HTML interface for Salesbook CSV Export.

Opens from system tray icon - provides salesbook export by date and month.
"""

import json
import datetime
import logging
import os
import sys
import multiprocessing
import calendar

logger = logging.getLogger(__name__)


def _run_export_modal_process(config_dict):
    """
    Run export modal in a separate process.

    Args:
        config_dict: Configuration dictionary containing salesbook settings
    """
    try:
        # Reinitialize logging in subprocess
        from logger_module import logger as subprocess_logger
        subprocess_logger.info("Export modal process started")

        # Run the actual modal UI (this will block until window closes)
        _open_export_modal_original(config_dict)

        subprocess_logger.info("Export modal process ended")
    except Exception as e:
        logger.error(f"Error in export modal process: {e}")
        import traceback
        traceback.print_exc()


class ExportAPI:
    """
    JavaScript API bridge for salesbook export operations.

    This class provides the backend API for the pywebview-based export UI.
    All methods are callable from JavaScript via the pywebview API bridge.
    """

    def __init__(self, config):
        """
        Initialize the Export API.

        Args:
            config: Full configuration dict from config_manager
        """
        self.config = config
        self.window = None  # Set after window creation

    def export_by_date(self, date_str):
        """
        Export salesbook for a specific date.

        Args:
            date_str: Date string (YYYY-MM-DD)

        Returns:
            dict: {"success": bool, "message": str, "summary_file": str, "details_file": str}
        """
        try:
            logger.info(f"Export by date triggered: {date_str}")

            # Parse date
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

            # Import and use exporter
            from .salesbook_exporter import SalesbookExporter
            exporter = SalesbookExporter(self.config)

            result = exporter.export_daily_salesbook(date_obj)

            if result.get("success"):
                logger.info(f"Export successful for {date_str}")
                return {
                    "success": True,
                    "message": f"Successfully exported salesbook for {date_str}",
                    "summary_file": result.get("summary_file", ""),
                    "details_file": result.get("details_file", "")
                }
            else:
                logger.warning(f"Export failed for {date_str}: {result.get('error')}")
                return {
                    "success": False,
                    "error": result.get("error", "Export failed")
                }
        except Exception as e:
            logger.error(f"Error exporting by date: {e}")
            return {"success": False, "error": str(e)}

    def export_by_month(self, year, month):
        """
        Export salesbook for an entire month.

        Args:
            year: Year (int)
            month: Month (int, 1-12)

        Returns:
            dict: {"success": bool, "message": str, "files": list}
        """
        try:
            logger.info(f"Export by month triggered: {year}-{month:02d}")

            from .salesbook_exporter import SalesbookExporter
            exporter = SalesbookExporter(self.config)

            # Get number of days in the month
            _, num_days = calendar.monthrange(int(year), int(month))

            exported_files = []
            failed_dates = []

            # Export each day in the month
            for day in range(1, num_days + 1):
                date_obj = datetime.date(int(year), int(month), day)
                result = exporter.export_daily_salesbook(date_obj)

                if result.get("success"):
                    if result.get("summary_file"):
                        exported_files.append({
                            "date": date_obj.strftime("%Y-%m-%d"),
                            "summary": result.get("summary_file"),
                            "details": result.get("details_file")
                        })
                else:
                    # Only track as failed if there was an actual error (not just no transactions)
                    if "No transactions" not in result.get("error", ""):
                        failed_dates.append(date_obj.strftime("%Y-%m-%d"))

            if exported_files:
                logger.info(f"Month export completed: {len(exported_files)} days exported")
                return {
                    "success": True,
                    "message": f"Exported {len(exported_files)} days from {year}-{month:02d}",
                    "files": exported_files,
                    "failed_dates": failed_dates
                }
            else:
                logger.warning(f"No transactions found for {year}-{month:02d}")
                return {
                    "success": False,
                    "error": f"No transactions found for {year}-{month:02d}"
                }
        except Exception as e:
            logger.error(f"Error exporting by month: {e}")
            return {"success": False, "error": str(e)}

    def export_by_date_range(self, start_date_str, end_date_str):
        """
        Export salesbook for a date range.

        Args:
            start_date_str: Start date string (YYYY-MM-DD)
            end_date_str: End date string (YYYY-MM-DD)

        Returns:
            dict: {"success": bool, "message": str, "files": list}
        """
        try:
            logger.info(f"Export by date range triggered: {start_date_str} to {end_date_str}")

            # Parse dates
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()

            if start_date > end_date:
                return {"success": False, "error": "Start date must be before or equal to end date"}

            from .salesbook_exporter import SalesbookExporter
            exporter = SalesbookExporter(self.config)

            exported_files = []
            failed_dates = []
            current_date = start_date

            # Export each day in the range
            while current_date <= end_date:
                result = exporter.export_daily_salesbook(current_date)

                if result.get("success"):
                    if result.get("summary_file"):
                        exported_files.append({
                            "date": current_date.strftime("%Y-%m-%d"),
                            "summary": result.get("summary_file"),
                            "details": result.get("details_file")
                        })
                else:
                    # Only track as failed if there was an actual error (not just no transactions)
                    if "No transactions" not in result.get("error", ""):
                        failed_dates.append(current_date.strftime("%Y-%m-%d"))

                current_date += datetime.timedelta(days=1)

            if exported_files:
                logger.info(f"Date range export completed: {len(exported_files)} days exported")
                return {
                    "success": True,
                    "message": f"Exported {len(exported_files)} days from {start_date_str} to {end_date_str}",
                    "files": exported_files,
                    "failed_dates": failed_dates
                }
            else:
                logger.warning(f"No transactions found for date range {start_date_str} to {end_date_str}")
                return {
                    "success": False,
                    "error": f"No transactions found for the selected date range"
                }
        except Exception as e:
            logger.error(f"Error exporting by date range: {e}")
            return {"success": False, "error": str(e)}

    def get_export_config(self):
        """
        Get export configuration.

        Returns:
            dict: Export configuration
        """
        try:
            salesbook_config = self.config.get("salesbook", {})

            return {
                "success": True,
                "enabled": salesbook_config.get("csv_export_enabled", True),
                "export_path": salesbook_config.get("csv_export_path", "C:\\Fbook"),
                "include_details": salesbook_config.get("include_transaction_details", True)
            }
        except Exception as e:
            logger.error(f"Error getting export config: {e}")
            return {"success": False, "error": str(e)}

    def open_export_folder(self):
        """Open the export folder in Windows Explorer."""
        try:
            export_path = self.config.get("salesbook", {}).get("csv_export_path", "C:\\Fbook")

            if os.path.exists(export_path):
                os.startfile(export_path)
                logger.info(f"Opened export folder: {export_path}")
                return {"success": True, "message": f"Opened folder: {export_path}"}
            else:
                logger.warning(f"Export folder does not exist: {export_path}")
                return {"success": False, "error": f"Export folder not found: {export_path}"}
        except Exception as e:
            logger.error(f"Error opening export folder: {e}")
            return {"success": False, "error": str(e)}

    def close_window(self):
        """Close the modal window"""
        if self.window:
            self.window.destroy()


def open_export_modal(config):
    """
    Open the export modal window in a separate process.

    Args:
        config: Full configuration dict

    This function launches the export UI in a separate process to avoid blocking
    the main thread and to allow multiple windows to be opened simultaneously.
    """
    try:
        logger.info("Launching export modal in separate process")
        process = multiprocessing.Process(
            target=_run_export_modal_process,
            args=(config,),
            daemon=True
        )
        process.start()
        logger.info("Export modal process started")

    except Exception as e:
        logger.error(f"Error opening export modal: {e}")
        raise


def _open_export_modal_original(config):
    """
    Original implementation - opens export modal (runs in subprocess).

    Args:
        config: Full configuration dict
    """
    try:
        import webview
        import base64

        # Create API instance
        api = ExportAPI(config)

        # Convert logo.png to base64 for embedding
        logo_base64 = ""
        try:
            if getattr(sys, 'frozen', False):
                logo_path = os.path.join(sys._MEIPASS, 'logo.png')
            else:
                # Go up 3 levels from src/core/export_ui.py to bridge/
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
                            <div class="text-blue-700 font-black text-2xl leading-none">SOLU</div>
                            <div class="bg-gray-800 text-white font-black text-xl px-2 py-1 mt-1 rounded">TECH</div>
                            <div class="text-gray-800 font-bold text-xs mt-1">SALESBOOK EXPORT</div>
                        </div>
                    </div>'''

        # HTML content for the export UI
        html_content = r'''
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Salesbook Export</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {{
            font-family: 'Inter', sans-serif;
        }}
        .status-message {{
            transition: all 0.3s ease;
        }}
    </style>
</head>
<body class="bg-gray-50 m-0 p-0">
    <div class="bg-white max-w-4xl mx-auto shadow-xl" style="min-height: 100vh;">

        <!-- Header with Logo -->
        <div class="bg-gradient-to-r from-blue-700 to-blue-800 p-6 rounded-b-2xl shadow-lg">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    {logo_html}
                    <div>
                        <h1 class="text-3xl font-bold text-white">Salesbook Export</h1>
                        <p class="text-blue-100 text-sm">Export transaction data to CSV</p>
                    </div>
                </div>

                <!-- Quick Action: Open Folder -->
                <button onclick="openExportFolder()" class="bg-white/10 backdrop-blur-sm border border-white/20 text-white hover:bg-white/20 font-semibold px-6 py-3 rounded-lg transition duration-150">
                    📁 Open Export Folder
                </button>
            </div>
        </div>

        <!-- Main Content -->
        <div class="p-6 space-y-6">

            <!-- Export by Single Date -->
            <div class="bg-white border-2 border-blue-500 rounded-xl p-6 shadow-md">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Export by Date</h2>
                <p class="text-sm text-gray-600 mb-4">Export salesbook for a specific date</p>

                <div class="flex gap-3">
                    <input type="date" id="single-date" class="flex-1 p-3 border-2 border-gray-300 rounded-lg text-base focus:border-blue-500 focus:outline-none">
                    <button onclick="exportByDate()" class="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-lg transition duration-150 shadow hover:shadow-lg whitespace-nowrap">
                        Export Date
                    </button>
                </div>
            </div>

            <!-- Export by Month -->
            <div class="bg-white border-2 border-green-500 rounded-xl p-6 shadow-md">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Export by Month</h2>
                <p class="text-sm text-gray-600 mb-4">Export all transactions for an entire month</p>

                <div class="flex gap-3">
                    <select id="month-select" class="flex-1 p-3 border-2 border-gray-300 rounded-lg text-base focus:border-green-500 focus:outline-none">
                        <option value="1">January</option>
                        <option value="2">February</option>
                        <option value="3">March</option>
                        <option value="4">April</option>
                        <option value="5">May</option>
                        <option value="6">June</option>
                        <option value="7">July</option>
                        <option value="8">August</option>
                        <option value="9">September</option>
                        <option value="10">October</option>
                        <option value="11">November</option>
                        <option value="12">December</option>
                    </select>
                    <input type="number" id="year-select" min="2020" max="2030" class="w-32 p-3 border-2 border-gray-300 rounded-lg text-base focus:border-green-500 focus:outline-none" placeholder="Year">
                    <button onclick="exportByMonth()" class="bg-green-600 hover:bg-green-700 text-white font-bold px-8 py-3 rounded-lg transition duration-150 shadow hover:shadow-lg whitespace-nowrap">
                        Export Month
                    </button>
                </div>
            </div>

            <!-- Export by Date Range -->
            <div class="bg-white border-2 border-purple-500 rounded-xl p-6 shadow-md">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Export by Date Range</h2>
                <p class="text-sm text-gray-600 mb-4">Export transactions for a custom date range</p>

                <div class="flex gap-3">
                    <div class="flex-1 flex gap-2 items-center">
                        <label class="text-sm font-semibold text-gray-700 whitespace-nowrap">From:</label>
                        <input type="date" id="start-date" class="flex-1 p-3 border-2 border-gray-300 rounded-lg text-base focus:border-purple-500 focus:outline-none">
                    </div>
                    <div class="flex-1 flex gap-2 items-center">
                        <label class="text-sm font-semibold text-gray-700 whitespace-nowrap">To:</label>
                        <input type="date" id="end-date" class="flex-1 p-3 border-2 border-gray-300 rounded-lg text-base focus:border-purple-500 focus:outline-none">
                    </div>
                    <button onclick="exportByDateRange()" class="bg-purple-600 hover:bg-purple-700 text-white font-bold px-8 py-3 rounded-lg transition duration-150 shadow hover:shadow-lg whitespace-nowrap">
                        Export Range
                    </button>
                </div>
            </div>

            <!-- Status Messages -->
            <div id="status-container" class="hidden status-message">
                <div id="status-message" class="p-4 rounded-lg"></div>
            </div>

            <!-- Export Results -->
            <div id="results-container" class="hidden">
                <div class="bg-gray-50 border-2 border-gray-300 rounded-xl p-6">
                    <h3 class="text-lg font-bold text-gray-800 mb-3">Export Results</h3>
                    <div id="results-content" class="space-y-2"></div>
                </div>
            </div>

        </div>

    </div>

    <script>
        // Initialize date inputs with today's date
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('single-date').value = today;
        document.getElementById('start-date').value = today;
        document.getElementById('end-date').value = today;

        // Set current month and year
        const now = new Date();
        document.getElementById('month-select').value = (now.getMonth() + 1).toString();
        document.getElementById('year-select').value = now.getFullYear();

        function showStatus(message, isError = false) {{
            const container = document.getElementById('status-container');
            const statusDiv = document.getElementById('status-message');

            container.classList.remove('hidden');
            statusDiv.className = `p-4 rounded-lg ${{isError ? 'bg-red-100 border-2 border-red-400 text-red-800' : 'bg-green-100 border-2 border-green-400 text-green-800'}}`;
            statusDiv.innerHTML = `<p class="font-semibold">${{message}}</p>`;

            // Auto-hide success messages after 5 seconds
            if (!isError) {{
                setTimeout(() => {{
                    container.classList.add('hidden');
                }}, 5000);
            }}
        }}

        function showResults(files) {{
            const container = document.getElementById('results-container');
            const content = document.getElementById('results-content');

            container.classList.remove('hidden');

            let html = '';
            files.forEach(file => {{
                html += `
                    <div class="bg-white p-3 rounded border border-gray-200">
                        <p class="font-semibold text-gray-800">${{file.date}}</p>
                        <p class="text-xs text-gray-600 mt-1">Summary: ${{file.summary}}</p>
                        ${{file.details ? `<p class="text-xs text-gray-600">Details: ${{file.details}}</p>` : ''}}
                    </div>
                `;
            }});

            content.innerHTML = html;
        }}

        async function exportByDate() {{
            const dateInput = document.getElementById('single-date');
            const date = dateInput.value;

            if (!date) {{
                showStatus('Please select a date', true);
                return;
            }}

            showStatus('Exporting salesbook for ' + date + '...', false);

            try {{
                const result = await pywebview.api.export_by_date(date);

                if (result.success) {{
                    showStatus(result.message, false);
                    if (result.summary_file) {{
                        showResults([{{
                            date: date,
                            summary: result.summary_file,
                            details: result.details_file
                        }}]);
                    }}
                }} else {{
                    showStatus('Error: ' + result.error, true);
                }}
            }} catch (error) {{
                showStatus('Error: ' + error, true);
            }}
        }}

        async function exportByMonth() {{
            const month = document.getElementById('month-select').value;
            const year = document.getElementById('year-select').value;

            if (!year) {{
                showStatus('Please enter a year', true);
                return;
            }}

            showStatus(`Exporting salesbook for ${{year}}-${{month.padStart(2, '0')}}... This may take a moment.`, false);

            try {{
                const result = await pywebview.api.export_by_month(year, month);

                if (result.success) {{
                    showStatus(result.message, false);
                    if (result.files && result.files.length > 0) {{
                        showResults(result.files);
                    }}
                }} else {{
                    showStatus('Error: ' + result.error, true);
                }}
            }} catch (error) {{
                showStatus('Error: ' + error, true);
            }}
        }}

        async function exportByDateRange() {{
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;

            if (!startDate || !endDate) {{
                showStatus('Please select both start and end dates', true);
                return;
            }}

            showStatus(`Exporting salesbook from ${{startDate}} to ${{endDate}}... This may take a moment.`, false);

            try {{
                const result = await pywebview.api.export_by_date_range(startDate, endDate);

                if (result.success) {{
                    showStatus(result.message, false);
                    if (result.files && result.files.length > 0) {{
                        showResults(result.files);
                    }}
                }} else {{
                    showStatus('Error: ' + result.error, true);
                }}
            }} catch (error) {{
                showStatus('Error: ' + error, true);
            }}
        }}

        async function openExportFolder() {{
            try {{
                const result = await pywebview.api.open_export_folder();

                if (!result.success) {{
                    showStatus('Error: ' + result.error, true);
                }}
            }} catch (error) {{
                showStatus('Error: ' + error, true);
            }}
        }}
    </script>
</body>
</html>
'''

        # Inject logo into HTML
        html_content = html_content.replace('{logo_html}', logo_html)

        # Create and show the window
        window = webview.create_window(
            'Salesbook Export',
            html=html_content,
            js_api=api,
            width=900,
            height=700,
            resizable=True,
            frameless=False
        )

        api.window = window

        logger.info("Starting export modal webview")
        webview.start(debug=False)
        logger.info("Export modal window closed")

    except Exception as e:
        logger.error(f"Error in export modal: {e}")
        import traceback
        traceback.print_exc()
        raise
