"""
Log Viewer Window for BAB-Cloud PrintHub.

Opens a separate window to display application logs in real-time.
Uses multiprocessing to allow simultaneous windows with fiscal tools modal.
"""

import os
import sys
import logging
import multiprocessing

logger = logging.getLogger(__name__)


def _run_log_viewer_process(log_file_path, icon_path, logo_base64):
    """Run log viewer in separate process (internal function)."""
    try:
        import webview

        # Create API for log operations
        class LogViewerAPI:
            def __init__(self, log_path):
                self.log_path = log_path
                self.window = None

            def get_logs(self, lines=500):
                """Get last N lines from log file."""
                try:
                    if not os.path.exists(self.log_path):
                        return {"success": False, "error": "Log file not found"}

                    with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                        all_lines = f.readlines()
                        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                        return {"success": True, "logs": ''.join(last_lines)}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            def clear_logs(self):
                """Clear the log file."""
                try:
                    with open(self.log_path, 'w', encoding='utf-8') as f:
                        f.write("")
                    return {"success": True, "message": "Logs cleared"}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            def close_window(self):
                """Close the log viewer window."""
                if self.window:
                    self.window.destroy()

        # Create API instance
        api = LogViewerAPI(log_file_path)

        # HTML content
        html_content = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BAB Cloud - Log Viewer</title>
    FAVICON_PLACEHOLDER
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
        body {
            font-family: 'Inter', sans-serif;
        }
        #logContent {
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    </style>
</head>
<body class="bg-gray-900 p-0 m-0">
    <div class="flex flex-col h-screen">
        <!-- Header -->
        <div class="bg-gradient-to-r from-gray-800 to-gray-900 p-4 border-b border-gray-700">
            <div class="flex items-center justify-between">
                <div>
                    <h1 class="text-2xl font-bold text-white">📋 BAB Cloud - Log Viewer</h1>
                    <p class="text-gray-400 text-sm">Application Logs (Last 500 lines)</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="refreshLogs()" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition duration-150">
                        🔄 Refresh
                    </button>
                    <button onclick="clearLogs()" class="bg-red-600 hover:bg-red-700 text-white font-semibold px-4 py-2 rounded-lg transition duration-150">
                        🗑️ Clear Logs
                    </button>
                    <button onclick="closeWindow()" class="bg-gray-600 hover:bg-gray-700 text-white font-semibold px-4 py-2 rounded-lg transition duration-150">
                        ✖ Close
                    </button>
                </div>
            </div>
        </div>

        <!-- Log Content -->
        <div class="flex-1 overflow-auto bg-black p-4">
            <pre id="logContent" class="text-green-400 text-xs select-text">Loading logs...</pre>
        </div>

        <!-- Footer -->
        <div class="bg-gray-800 p-2 border-t border-gray-700">
            <p class="text-gray-500 text-xs text-center">Auto-refreshes every 2 seconds</p>
        </div>
    </div>

    <script>
        let autoRefreshInterval;

        async function refreshLogs() {
            try {
                const result = await pywebview.api.get_logs(500);
                if (result.success) {
                    const logContent = document.getElementById('logContent');
                    logContent.textContent = result.logs || 'No logs available';
                    // Auto-scroll to bottom
                    logContent.scrollTop = logContent.scrollHeight;
                } else {
                    document.getElementById('logContent').textContent = 'Error: ' + result.error;
                }
            } catch (error) {
                console.error('Error loading logs:', error);
                document.getElementById('logContent').textContent = 'Error loading logs: ' + error;
            }
        }

        async function clearLogs() {
            if (confirm('Are you sure you want to clear all logs?')) {
                try {
                    const result = await pywebview.api.clear_logs();
                    if (result.success) {
                        refreshLogs();
                    } else {
                        alert('Error clearing logs: ' + result.error);
                    }
                } catch (error) {
                    alert('Error: ' + error);
                }
            }
        }

        function closeWindow() {
            pywebview.api.close_window();
        }

        // Initialize on load
        window.addEventListener('pywebviewready', function() {
            refreshLogs();
            // Auto-refresh every 2 seconds
            autoRefreshInterval = setInterval(refreshLogs, 2000);
        });

        // Clean up on window close
        window.addEventListener('beforeunload', function() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
        });
    </script>
</body>
</html>
        '''

        # Add favicon to HTML
        favicon_tag = ""
        if logo_base64:
            favicon_tag = f'<link rel="icon" type="image/png" href="data:image/png;base64,{logo_base64}">'
        html_content = html_content.replace('FAVICON_PLACEHOLDER', favicon_tag)

        # Create window
        window = webview.create_window(
            title="BAB Cloud - Log Viewer",
            html=html_content,
            js_api=api,
            width=1000,
            height=700,
            resizable=True,
            min_size=(800, 500)
        )
        api.window = window
        webview.start()

    except Exception as e:
        raise


def open_log_viewer_window():
    """
    Open the log viewer window in a separate process.

    Displays the contents of log.log file in a webview window with auto-refresh.
    Uses multiprocessing to allow simultaneous windows.
    """
    try:
        # Determine log file path
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            icon_path = os.path.join(sys._MEIPASS, 'logo.png')
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_dir, 'logo.png')

        log_file_path = os.path.join(base_dir, 'log.log')

        # Load logo as base64 for favicon
        logo_base64 = ""
        if os.path.exists(icon_path):
            try:
                import base64
                with open(icon_path, 'rb') as f:
                    logo_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not load logo for favicon: {e}")

        # Launch log viewer in separate process to allow simultaneous windows
        logger.info(f"Launching log viewer in separate process for {log_file_path}")
        process = multiprocessing.Process(
            target=_run_log_viewer_process,
            args=(log_file_path, icon_path, logo_base64),
            daemon=True
        )
        process.start()
        logger.info("Log viewer process started")

    except Exception as e:
        logger.error(f"Error opening log viewer window: {e}")
        raise
