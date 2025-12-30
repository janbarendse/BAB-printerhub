"""
Standalone Log Viewer Application.

This is a separate executable that displays log files in a webview window.
Completely isolated from the main PrintHub app to avoid pystray/webview conflicts.

Usage: log_viewer_app.exe [--log-file=path]
"""

import os
import sys
import glob


def get_base_dir():
    """Get the base directory (where the executable or script is located)."""
    if getattr(sys, 'frozen', False) or '.dist' in sys.executable or '__compiled__' in dir():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _find_webview2_runtime():
    """Return the path to msedgewebview2.exe if WebView2 runtime is installed, else None."""
    candidates = [
        r"C:\Program Files\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
        r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application\*\msedgewebview2.exe",
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def _start_webview_with_edge_fallback():
    """Start pywebview preferring Edge/WebView2 and fall back to mshtml if Edge is unavailable."""
    import webview
    runtime_path = _find_webview2_runtime()
    if runtime_path:
        print(f"[LOG_VIEWER APP] WebView2 runtime detected at: {runtime_path}")
    else:
        print("[LOG_VIEWER APP] WebView2 runtime NOT found; will try Edge and fall back to mshtml")

    try:
        webview.start(gui='edgechromium', debug=False, private_mode=True)
        return
    except Exception as edge_err:
        print(f"[LOG_VIEWER APP] Edge/WebView2 backend failed: {edge_err}")

    try:
        webview.start(gui='mshtml', debug=True)
    except Exception as mshtml_err:
        print(f"[LOG_VIEWER APP] mshtml backend failed: {mshtml_err}")
        raise


def main():
    """Main entry point for standalone log viewer."""
    import webview

    base_dir = get_base_dir()

    # Parse command line for custom log file path
    log_file_path = None
    for arg in sys.argv[1:]:
        if arg.startswith('--log-file='):
            log_file_path = arg.split('=', 1)[1]

    # Default log file path
    if not log_file_path:
        log_file_path = os.path.join(base_dir, 'log.log')

    # Load logo for favicon
    icon_path = os.path.join(base_dir, 'src', 'assets', 'logo.png')
    logo_base64 = ""
    if os.path.exists(icon_path):
        try:
            import base64
            with open(icon_path, 'rb') as f:
                logo_base64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            pass

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

    # Build favicon tag
    favicon_tag = ""
    if logo_base64:
        favicon_tag = f'<link rel="icon" type="image/png" href="data:image/png;base64,{logo_base64}">'

    # HTML content with embedded CSS - dark theme
    html_content = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>BAB Cloud - Log Viewer</title>
{favicon_tag}
<style type="text/css">
html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
    background-color: #111827;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    color: #ffffff;
}}
.container {{
    display: flex;
    flex-direction: column;
    height: 100vh;
    background-color: #111827;
}}
.header {{
    background: linear-gradient(to right, #1f2937, #111827);
    padding: 16px;
    border-bottom: 1px solid #374151;
}}
.header-content {{
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.title {{
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
}}
.subtitle {{
    color: #9ca3af;
    font-size: 14px;
    margin-top: 4px;
}}
.buttons {{
    display: flex;
    gap: 8px;
}}
.btn {{
    padding: 8px 16px;
    border-radius: 8px;
    border: none;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    color: #ffffff;
}}
.btn-blue {{
    background-color: #2563eb;
}}
.btn-blue:hover {{
    background-color: #1d4ed8;
}}
.btn-red {{
    background-color: #dc2626;
}}
.btn-red:hover {{
    background-color: #b91c1c;
}}
.btn-gray {{
    background-color: #4b5563;
}}
.btn-gray:hover {{
    background-color: #374151;
}}
.log-container {{
    flex: 1;
    overflow: auto;
    background-color: #000000;
    padding: 16px;
}}
.log-content {{
    font-family: Consolas, Monaco, "Courier New", monospace;
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: #4ade80;
    margin: 0;
}}
.footer {{
    background-color: #1f2937;
    padding: 8px;
    border-top: 1px solid #374151;
    text-align: center;
}}
.footer-text {{
    color: #6b7280;
    font-size: 12px;
    margin: 0;
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-content">
            <div>
                <h1 class="title">📋 BAB Cloud - Log Viewer</h1>
                <p class="subtitle">Application Logs (Last 500 lines)</p>
            </div>
            <div class="buttons">
                <button class="btn btn-blue" onclick="refreshLogs()">🔄 Refresh</button>
                <button class="btn btn-red" onclick="clearLogs()">🗑️ Clear Logs</button>
                <button class="btn btn-gray" onclick="closeWindow()">✖ Close</button>
            </div>
        </div>
    </div>
    <div class="log-container">
        <pre id="logContent" class="log-content">Loading logs...</pre>
    </div>
    <div class="footer">
        <p class="footer-text">Auto-refreshes every 2 seconds</p>
    </div>
</div>
<script>
var autoRefreshInterval;

function refreshLogs() {{
    pywebview.api.get_logs(500).then(function(result) {{
        if (result.success) {{
            var el = document.getElementById('logContent');
            el.textContent = result.logs || 'No logs available';
            el.scrollTop = el.scrollHeight;
        }} else {{
            document.getElementById('logContent').textContent = 'Error: ' + result.error;
        }}
    }}).catch(function(error) {{
        document.getElementById('logContent').textContent = 'Error: ' + error;
    }});
}}

function clearLogs() {{
    if (confirm('Are you sure you want to clear all logs?')) {{
        pywebview.api.clear_logs().then(function(result) {{
            if (result.success) {{
                refreshLogs();
            }} else {{
                alert('Error: ' + result.error);
            }}
        }});
    }}
}}

function closeWindow() {{
    if (autoRefreshInterval) {{
        clearInterval(autoRefreshInterval);
    }}
    pywebview.api.close_window();
}}

window.addEventListener('pywebviewready', function() {{
    refreshLogs();
    autoRefreshInterval = setInterval(refreshLogs, 2000);
}});
</script>
</body>
</html>'''

    # Write HTML to temp file (bypasses any Nuitka caching issues)
    import tempfile
    temp_dir = tempfile.gettempdir()
    html_file = os.path.join(temp_dir, 'bab_log_viewer.html')
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Create window loading from file
    window = webview.create_window(
        title="BAB Cloud - Log Viewer",
        url=html_file,
        js_api=api,
        width=1000,
        height=700,
        resizable=True,
        min_size=(800, 500)
    )
    api.window = window

    # Start webview
    _start_webview_with_edge_fallback()

    # Cleanup temp file
    try:
        os.remove(html_file)
    except:
        pass


if __name__ == "__main__":
    main()
