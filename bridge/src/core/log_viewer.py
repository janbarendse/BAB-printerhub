"""
Log Viewer Window for BAB-Cloud PrintHub.

PySide6-based modal for viewing and clearing logs.
"""

import os
import sys
import logging
import ctypes

logger = logging.getLogger(__name__)


def _show_error_messagebox(title, message):
    """Show native Windows error dialog for debugging modal failures."""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(message), title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def _is_compiled():
    """Check if running as compiled executable (Nuitka or PyInstaller)."""
    if '__compiled__' in dir():
        return True
    if getattr(sys, 'frozen', False):
        return True
    if '.dist' in sys.executable:
        return True
    return False


def _resolve_base_dir():
    env_base = os.environ.get("BAB_UI_BASE")
    if env_base:
        return env_base
    if _is_compiled():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LogViewerWindow:
    """PySide6 log viewer window."""

    def __init__(self, log_file_path, icon_path):
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QIcon, QTextCursor
        from PySide6.QtWidgets import (
            QMainWindow,
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QPlainTextEdit,
            QMessageBox,
        )

        self._Qt = Qt
        self._QTimer = QTimer
        self._QTextCursor = QTextCursor
        self._QMessageBox = QMessageBox

        self.window = QMainWindow()
        self.window.setWindowTitle("BAB Cloud - Log Viewer")
        self.window.resize(1000, 700)
        self.window.setMinimumSize(800, 500)
        if icon_path and os.path.exists(icon_path):
            self.window.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.window.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(16)

        logo = QLabel()
        logo.setObjectName("logo")
        if icon_path and os.path.exists(icon_path):
            from PySide6.QtGui import QPixmap

            pix = QPixmap(icon_path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(56, 56, self._Qt.KeepAspectRatio, self._Qt.SmoothTransformation))

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        title = QLabel("BAB Cloud - Log Viewer")
        title.setObjectName("title")
        subtitle = QLabel("Application Logs (Last 500 lines)")
        subtitle.setObjectName("subtitle")
        left_layout.addWidget(title)
        left_layout.addWidget(subtitle)
        left_layout.setAlignment(self._Qt.AlignVCenter)

        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("refreshButton")
        clear_btn = QPushButton("Clear Logs")
        clear_btn.setObjectName("clearButton")
        close_btn = QPushButton("Close")
        close_btn.setObjectName("closeButton")

        buttons_layout.addWidget(refresh_btn)
        buttons_layout.addWidget(clear_btn)
        buttons_layout.addWidget(close_btn)

        header_layout.setAlignment(self._Qt.AlignVCenter)
        header_layout.addWidget(logo)
        header_layout.addWidget(left, 1)
        header_layout.addWidget(buttons, 0, self._Qt.AlignRight)

        self.log_content = QPlainTextEdit()
        self.log_content.setReadOnly(True)
        self.log_content.setObjectName("logContent")
        self.log_content.setLineWrapMode(QPlainTextEdit.NoWrap)

        footer = QWidget()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 6, 8, 6)
        footer_layout.setSpacing(0)
        footer_label = QLabel("Auto-refreshes every 2 seconds")
        footer_label.setObjectName("footerText")
        footer_layout.addStretch(1)
        footer_layout.addWidget(footer_label)
        footer_layout.addStretch(1)

        layout.addWidget(header)
        layout.addWidget(self.log_content, 1)
        layout.addWidget(footer)

        self._apply_styles()

        self.log_file_path = log_file_path
        self._max_lines = 500

        refresh_btn.clicked.connect(self.refresh_logs)
        clear_btn.clicked.connect(self.clear_logs)
        close_btn.clicked.connect(self.window.close)

        self.timer = self._QTimer(self.window)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(2000)

        self.refresh_logs()

    def _apply_styles(self):
        self.window.setStyleSheet(
            """
            QMainWindow {
                background-color: #f5f6f8;
                color: #111827;
            }
            QWidget#header {
                background: #b91c1c;
                border-bottom: 1px solid #991b1b;
            }
            QLabel#logo {
                background: #ffffff;
                border-radius: 10px;
                padding: 6px;
            }
            QLabel#title {
                font-size: 22px;
                font-weight: 800;
                color: #ffffff;
                margin: 0;
            }
            QLabel#subtitle {
                font-size: 12px;
                color: #f3d6d6;
                margin: 0;
            }
            QPushButton {
                border: none;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 600;
                color: #ffffff;
            }
            QPushButton#refreshButton {
                background-color: #374151;
            }
            QPushButton#refreshButton:hover {
                background-color: #1f2937;
            }
            QPushButton#clearButton {
                background-color: #dc2626;
            }
            QPushButton#clearButton:hover {
                background-color: #b91c1c;
            }
            QPushButton#closeButton {
                background-color: #4b5563;
            }
            QPushButton#closeButton:hover {
                background-color: #374151;
            }
            QPlainTextEdit#logContent {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #e5e7eb;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
            }
            QWidget#footer {
                background-color: #f3f4f6;
                border-top: 1px solid #e5e7eb;
            }
            QLabel#footerText {
                color: #6b7280;
                font-size: 11px;
            }
            QMessageBox {
                background-color: #ffffff;
                color: #111827;
            }
            QMessageBox QPushButton {
                border: none;
                padding: 6px 14px;
                border-radius: 6px;
                font-weight: 600;
                color: #ffffff;
                background-color: #374151;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #1f2937;
            }
            """
        )

    def refresh_logs(self):
        try:
            if not os.path.exists(self.log_file_path):
                self.log_content.setPlainText("Log file not found")
                return

            with open(self.log_file_path, 'r', encoding='utf-8', errors='replace') as handle:
                lines = handle.readlines()

            if len(lines) > self._max_lines:
                lines = lines[-self._max_lines:]

            self.log_content.setPlainText(''.join(lines) or "No logs available")
            self.log_content.moveCursor(self._QTextCursor.End)
        except Exception as exc:
            self.log_content.setPlainText(f"Error loading logs: {exc}")

    def clear_logs(self):
        dialog = self._QMessageBox(self.window)
        dialog.setWindowTitle("Clear Logs")
        dialog.setText("Clear all logs?")
        dialog.setIcon(self._QMessageBox.Warning)
        dialog.setStandardButtons(self._QMessageBox.Yes | self._QMessageBox.No)
        dialog.setDefaultButton(self._QMessageBox.No)
        dialog.setStyleSheet(self.window.styleSheet())
        if dialog.exec() != self._QMessageBox.Yes:
            return

        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as handle:
                handle.write("")
            self.refresh_logs()
        except Exception as exc:
            self._QMessageBox.warning(self.window, "Clear Logs", f"Error clearing logs: {exc}")


def _run_log_viewer_process(log_file_path, icon_path):
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        _show_error_messagebox("Log Viewer Error", f"PySide6 is not available: {exc}")
        raise

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    viewer = LogViewerWindow(log_file_path, icon_path)
    viewer.window.show()
    app.exec()


def _run_log_viewer_standalone(config):
    """
    Run log viewer as standalone modal (called when exe launched with --modal=log_viewer).
    This runs directly without spawning another subprocess.
    """
    logger.info("[LOG_VIEWER] _run_log_viewer_standalone called")

    base_dir = _resolve_base_dir()
    icon_path = os.path.join(base_dir, 'logo.png')
    log_file_path = os.path.join(base_dir, 'log.log')
    logger.info("[LOG_VIEWER] base_dir: %s", base_dir)
    logger.info("[LOG_VIEWER] log_file_path: %s", log_file_path)
    logger.info("[LOG_VIEWER] icon_path: %s", icon_path)

    _run_log_viewer_process(log_file_path, icon_path)


def open_log_viewer_window():
    """
    Open the log viewer window in a completely separate subprocess.

    Spawns a new instance of the executable with --modal=log_viewer argument.
    This isolates the UI from pystray's event loop.
    """
    try:
        import subprocess

        exe_path = sys.executable
        logger.info("Opening log viewer in separate subprocess (exe: %s)...", exe_path)

        process = subprocess.Popen(
            [exe_path, '--modal=log_viewer'],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
        )

        logger.info("Log viewer subprocess started (PID: %s)", process.pid)

    except Exception as exc:
        logger.error("Error opening log viewer window: %s", exc)
        raise
