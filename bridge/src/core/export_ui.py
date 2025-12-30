"""
Export UI using PySide6 - Salesbook CSV Export.

Opens from system tray icon - provides salesbook export by date, month, and range.
"""

import datetime
import calendar
import logging
import os
import sys
import ctypes
import time

from PySide6 import QtCore

from src.logger_module import logger as app_logger

logger = app_logger


def _install_excepthook():
    def _hook(exc_type, exc_value, exc_traceback):
        logger.error("Export modal crash: %s", exc_value, exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = _hook

    def _qt_handler(msg_type, context, message):
        logger.error("Qt message: %s", message)
    try:
        QtCore.qInstallMessageHandler(_qt_handler)
    except Exception:
        pass


class ExportWorker(QtCore.QObject):
    progress = QtCore.Signal(int, int, str, float)
    finished = QtCore.Signal(list, list, float)

    def __init__(self, dates):
        super().__init__()
        self._dates = dates

    @QtCore.Slot()
    def run(self):
        from .ipc_client import IpcClient

        client = IpcClient()
        exported_files = []
        failed_dates = []
        start = time.perf_counter()
        try:
            for index, date_str in enumerate(self._dates, start=1):
                result = client.request("salesbook.export_daily", {"date": date_str})
                if result.get("success"):
                    file_path = result.get("file") or result.get("summary_file")
                    if file_path:
                        exported_files.append({
                            "date": date_str,
                            "file": file_path,
                            "summary": result.get("summary_file", ""),
                            "details": result.get("details_file"),
                        })
                else:
                    error_text = result.get("error", "")
                    if "No transactions" not in error_text and "No salesbook data" not in error_text:
                        failed_dates.append(date_str)

                elapsed = time.perf_counter() - start
                self.progress.emit(index, len(self._dates), date_str, elapsed)
        except Exception as exc:
            logger.error("Export worker crashed: %s", exc, exc_info=True)
            failed_dates.extend(self._dates)

        total_elapsed = time.perf_counter() - start
        self.finished.emit(exported_files, failed_dates, total_elapsed)


def _show_error_messagebox(title, message):
    """Show native Windows error dialog for debugging modal failures."""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(message), title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def _is_compiled() -> bool:
    if "__compiled__" in dir():
        return True
    if getattr(sys, "frozen", False):
        return True
    if ".dist" in sys.executable:
        return True
    return False


def _resolve_base_dir() -> str:
    env_base = os.environ.get("BAB_UI_BASE")
    if env_base:
        return env_base.strip()
    if _is_compiled():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ExportWindow(QtCore.QObject):
    def __init__(self, config):
        super().__init__()
        from PySide6.QtCore import Qt, QDate
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import (
            QMainWindow,
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QGridLayout,
            QLabel,
            QPushButton,
            QDateEdit,
            QComboBox,
            QSpinBox,
            QFrame,
            QGroupBox,
            QScrollArea,
            QProgressBar,
        )

        from .ipc_client import IpcClient

        self._Qt = Qt
        self._QDate = QDate
        self.config = config
        self.client = IpcClient()
        _install_excepthook()

        self.window = QMainWindow()
        self.window.setWindowTitle("BAB Cloud - Salesbook Export")
        self.window.resize(920, 720)
        self.window.setMinimumSize(820, 640)

        base_dir = _resolve_base_dir()
        icon_path = os.path.join(base_dir, "logo.png")
        if os.path.exists(icon_path):
            self.window.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.window.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(16)

        logo = QLabel()
        if os.path.exists(icon_path):
            from PySide6.QtGui import QPixmap

            pix = QPixmap(icon_path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(64, 64, self._Qt.KeepAspectRatio, self._Qt.SmoothTransformation))

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title = QLabel("Salesbook Export")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Export CSV summaries and detail files")
        subtitle.setObjectName("headerSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header_layout.addWidget(logo)
        header_layout.addWidget(title_box, 1)

        open_folder_btn = QPushButton("Open Export Folder")
        open_folder_btn.setObjectName("darkButtonWide")
        open_folder_btn.clicked.connect(self.open_export_folder)
        self.open_folder_btn = open_folder_btn
        header_layout.addWidget(open_folder_btn)

        root_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 18)
        content_layout.setSpacing(16)

        actions_grid = QGridLayout()
        actions_grid.setSpacing(16)

        # Export by date card
        date_card = QFrame()
        date_card.setObjectName("card")
        date_layout = QVBoxLayout(date_card)
        date_layout.setContentsMargins(16, 14, 16, 14)
        date_layout.setSpacing(10)

        date_title = QLabel("Export by Date")
        date_title.setObjectName("cardTitle")
        date_desc = QLabel("Export a single day salesbook CSV.")
        date_desc.setObjectName("cardDesc")
        date_desc.setWordWrap(True)

        self.single_date = QDateEdit()
        self.single_date.setObjectName("inputField")
        self.single_date.setDisplayFormat("dd-MM-yy")
        self.single_date.setCalendarPopup(True)
        self.single_date.setDate(QDate.currentDate())

        date_btn = QPushButton("Export Date")
        date_btn.setObjectName("primaryButtonWide")
        date_btn.clicked.connect(self.export_by_date)
        self.date_btn = date_btn

        date_layout.addWidget(date_title)
        date_layout.addWidget(date_desc)
        date_layout.addWidget(self.single_date)
        date_layout.addWidget(date_btn)

        # Export by month card
        month_card = QFrame()
        month_card.setObjectName("card")
        month_layout = QVBoxLayout(month_card)
        month_layout.setContentsMargins(16, 14, 16, 14)
        month_layout.setSpacing(10)

        month_title = QLabel("Export by Month")
        month_title.setObjectName("cardTitle")
        month_desc = QLabel("Export every day in a month. This may take a moment.")
        month_desc.setObjectName("cardDesc")
        month_desc.setWordWrap(True)

        month_row = QWidget()
        month_row_layout = QHBoxLayout(month_row)
        month_row_layout.setContentsMargins(0, 0, 0, 0)
        month_row_layout.setSpacing(8)

        self.month_select = QComboBox()
        self.month_select.setObjectName("inputField")
        for i in range(1, 13):
            self.month_select.addItem(datetime.date(2000, i, 1).strftime("%B"), i)
        self.month_select.setCurrentIndex(datetime.date.today().month - 1)

        self.year_select = QSpinBox()
        self.year_select.setObjectName("inputField")
        self.year_select.setRange(2000, 2100)
        self.year_select.setValue(datetime.date.today().year)

        month_row_layout.addWidget(self.month_select, 1)
        month_row_layout.addWidget(self.year_select, 0)

        month_btn = QPushButton("Export Month")
        month_btn.setObjectName("primaryButtonWide")
        month_btn.clicked.connect(self.export_by_month)
        self.month_btn = month_btn

        month_layout.addWidget(month_title)
        month_layout.addWidget(month_desc)
        month_layout.addWidget(month_row)
        month_layout.addWidget(month_btn)

        # Export by range card
        range_card = QFrame()
        range_card.setObjectName("card")
        range_layout = QVBoxLayout(range_card)
        range_layout.setContentsMargins(16, 14, 16, 14)
        range_layout.setSpacing(10)

        range_title = QLabel("Export by Date Range")
        range_title.setObjectName("cardTitle")
        range_desc = QLabel("Export a continuous date range of daily salesbooks.")
        range_desc.setObjectName("cardDesc")
        range_desc.setWordWrap(True)

        range_row = QWidget()
        range_row_layout = QHBoxLayout(range_row)
        range_row_layout.setContentsMargins(0, 0, 0, 0)
        range_row_layout.setSpacing(8)

        self.range_start = QDateEdit()
        self.range_start.setObjectName("inputField")
        self.range_start.setDisplayFormat("dd-MM-yy")
        self.range_start.setCalendarPopup(True)
        self.range_start.setDate(QDate.currentDate())

        self.range_end = QDateEdit()
        self.range_end.setObjectName("inputField")
        self.range_end.setDisplayFormat("dd-MM-yy")
        self.range_end.setCalendarPopup(True)
        self.range_end.setDate(QDate.currentDate())

        range_row_layout.addWidget(self.range_start, 1)
        range_row_layout.addWidget(self.range_end, 1)

        range_btn = QPushButton("Export Date Range")
        range_btn.setObjectName("primaryButtonWide")
        range_btn.clicked.connect(self.export_by_date_range)
        self.range_btn = range_btn

        range_layout.addWidget(range_title)
        range_layout.addWidget(range_desc)
        range_layout.addWidget(range_row)
        range_layout.addWidget(range_btn)

        actions_grid.addWidget(date_card, 0, 0)
        actions_grid.addWidget(month_card, 0, 1)
        actions_grid.addWidget(range_card, 1, 0, 1, 2)
        content_layout.addLayout(actions_grid)

        results_group = QGroupBox("Export Results")
        results_group.setObjectName("resultsGroup")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(14, 12, 14, 12)
        results_layout.setSpacing(8)

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(8)

        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setWidget(self.results_container)
        results_layout.addWidget(results_scroll)

        content_layout.addWidget(results_group)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        root_layout.addWidget(scroll, 1)

        footer = QWidget()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        footer_layout.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progress")
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        footer_layout.addWidget(self.progress_bar, 0)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("darkButtonWide")
        close_btn.clicked.connect(self.window.close)
        footer_layout.addWidget(close_btn)

        root_layout.addWidget(footer)

        self._apply_styles()
        self._export_thread = None
        self._export_worker = None
        self._avg_day_seconds = None
        QtCore.QTimer.singleShot(0, self._finalize_layout)

    def _finalize_layout(self):
        self.window.adjustSize()
        self.window.setMaximumHeight(self.window.sizeHint().height())

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
            QLabel#headerTitle {
                font-size: 22px;
                font-weight: 800;
                color: #ffffff;
            }
            QLabel#headerSubtitle {
                font-size: 12px;
                color: #f3d6d6;
            }
            QWidget#scroll {
                background: transparent;
            }
            QFrame#card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
            QLabel#cardTitle {
                font-size: 15px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#cardDesc {
                font-size: 12px;
                color: #6b7280;
            }
            QGroupBox#resultsGroup {
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                background: #ffffff;
            }
            QGroupBox#resultsGroup::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                font-weight: 700;
                color: #111827;
            }
            QLineEdit#inputField, QComboBox#inputField, QSpinBox#inputField, QDateEdit#inputField {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 6px 8px;
                color: #111827;
            }
            QPushButton#primaryButtonWide {
                background-color: #b91c1c;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 700;
            }
            QPushButton#primaryButtonWide:hover {
                background-color: #991b1b;
            }
            QPushButton#darkButtonWide {
                background-color: #374151;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 700;
            }
            QPushButton#darkButtonWide:hover {
                background-color: #1f2937;
            }
            QWidget#footer {
                background: #f3f4f6;
                border-top: 1px solid #e5e7eb;
            }
            QLabel#status {
                color: #6b7280;
            }
            QProgressBar#progress {
                min-width: 180px;
                max-width: 240px;
                height: 18px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: #ffffff;
                text-align: center;
                color: #374151;
            }
            QProgressBar#progress::chunk {
                background-color: #b91c1c;
                border-radius: 8px;
            }
            QWidget#resultItem {
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
            QLabel#resultDate {
                font-weight: 700;
                color: #111827;
            }
            QLabel#resultFile {
                font-size: 12px;
                color: #6b7280;
            }
            """
        )

    def _set_status(self, message, is_error=False):
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: #dc2626;")
        else:
            self.status_label.setStyleSheet("color: #6b7280;")

    def _set_export_controls_enabled(self, enabled):
        self.date_btn.setEnabled(enabled)
        self.month_btn.setEnabled(enabled)
        self.range_btn.setEnabled(enabled)
        self.open_folder_btn.setEnabled(enabled)

    def _start_worker(self, dates, label):
        if self._export_thread and self._export_thread.isRunning():
            self._set_status("Export already in progress...", is_error=True)
            return

        self._set_export_controls_enabled(False)
        self.progress_bar.setVisible(True)

        total = len(dates)
        if total > 1:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 0)

        if total == 1 and self._avg_day_seconds:
            self._set_status(f"{label} ETA ~{self._format_eta(self._avg_day_seconds)}")
        else:
            self._set_status(label)

        self._export_thread = QtCore.QThread()
        self._export_worker = ExportWorker(dates)
        self._export_worker.moveToThread(self._export_thread)
        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.progress.connect(self._on_export_progress, QtCore.Qt.QueuedConnection)
        self._export_worker.finished.connect(self._on_export_finished, QtCore.Qt.QueuedConnection)
        self._export_worker.finished.connect(self._export_thread.quit)
        self._export_worker.finished.connect(self._export_worker.deleteLater)
        self._export_thread.finished.connect(self._cleanup_export_thread)
        self._export_thread.finished.connect(self._export_thread.deleteLater)
        self._export_thread.start()

    @QtCore.Slot(int, int, str, float)
    def _on_export_progress(self, completed, total, date_str, elapsed):
        if total > 1:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(completed)
            eta = ""
            if completed > 0:
                avg = elapsed / completed
                remaining = max(0, total - completed)
                eta = f" ETA ~{self._format_eta(avg * remaining)}"
            self._set_status(f"Exporting {completed}/{total} (last {date_str}){eta}")

    @QtCore.Slot(list, list, float)
    def _on_export_finished(self, exported_files, failed_dates, elapsed):
        self._finish_export_ui(exported_files, failed_dates, elapsed)

    def _finish_export_ui(self, exported_files, failed_dates, elapsed):
        try:
            total = max(len(exported_files) + len(failed_dates), 1)
            self._avg_day_seconds = elapsed / total
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
            self.progress_bar.setVisible(False)
            self._set_export_controls_enabled(True)

            if exported_files:
                self._show_results(exported_files)
                self._set_status(f"Exported {len(exported_files)} day(s)")
            else:
                self._set_status("No transactions found for the selected range", is_error=True)

            if failed_dates:
                logger.warning("Export failed for dates: %s", ", ".join(failed_dates))
        except Exception as exc:
            logger.error("Export completion failed: %s", exc, exc_info=True)
            self._set_status(str(exc), is_error=True)

    def _cleanup_export_thread(self):
        self._export_thread = None
        self._export_worker = None

    @staticmethod
    def _format_eta(seconds):
        seconds = max(0, int(seconds))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"
    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def _show_results(self, files):
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget

        self._clear_results()
        if not files:
            label = QLabel("No files exported")
            label.setObjectName("resultFile")
            self.results_layout.addWidget(label)
            return

        for file_info in files:
            card = QWidget()
            card.setObjectName("resultItem")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(4)

            date_label = QLabel(file_info.get("date", ""))
            date_label.setObjectName("resultDate")
            layout.addWidget(date_label)

            file_path = file_info.get("file")
            if file_path:
                file_label = QLabel(f"File: {file_path}")
                file_label.setObjectName("resultFile")
                layout.addWidget(file_label)
            else:
                summary_label = QLabel(f"Summary: {file_info.get('summary', '')}")
                summary_label.setObjectName("resultFile")
                layout.addWidget(summary_label)
                details = file_info.get("details")
                if details:
                    details_label = QLabel(f"Details: {details}")
                    details_label.setObjectName("resultFile")
                    layout.addWidget(details_label)

            self.results_layout.addWidget(card)

    def export_by_date(self):
        date_str = self.single_date.date().toString("yyyy-MM-dd")
        self._start_worker([date_str], f"Exporting salesbook for {date_str}...")

    def export_by_month(self):
        year = int(self.year_select.value())
        month = int(self.month_select.currentData())
        today = datetime.date.today()
        if (year, month) > (today.year, today.month):
            self._set_status("Selected month is in the future", is_error=True)
            return

        _, num_days = calendar.monthrange(year, month)
        end_day = num_days
        if (year, month) == (today.year, today.month):
            end_day = today.day

        dates = [
            datetime.date(year, month, day).strftime("%Y-%m-%d")
            for day in range(1, end_day + 1)
        ]
        self._start_worker(dates, f"Exporting salesbook for {year}-{month:02d}...")

    def export_by_date_range(self):
        start_date = self.range_start.date().toString("yyyy-MM-dd")
        end_date = self.range_end.date().toString("yyyy-MM-dd")

        if self.range_start.date() > self.range_end.date():
            self._set_status("Start date must be before end date", is_error=True)
            return

        today = datetime.date.today()
        end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        if end_date_obj > today:
            end_date_obj = today
            end_date = end_date_obj.strftime("%Y-%m-%d")

        current_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        dates = []
        while current_date <= end_date_obj:
            dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += datetime.timedelta(days=1)
        self._start_worker(dates, f"Exporting salesbook from {start_date} to {end_date}...")

    def open_export_folder(self):
        try:
            export_path = self.config.get("salesbook", {}).get("csv_export_path", "C:\\Fbook")
            if os.path.exists(export_path):
                os.startfile(export_path)
                self._set_status(f"Opened folder: {export_path}")
            else:
                self._set_status(f"Export folder not found: {export_path}", is_error=True)
        except Exception as exc:
            logger.error("Open folder failed: %s", exc)
            self._set_status(str(exc), is_error=True)


def open_export_modal(config):
    """Open the export modal in a separate subprocess."""
    try:
        import subprocess

        exe_path = sys.executable
        logger.info("Opening export modal in separate subprocess (exe: %s)...", exe_path)

        process = subprocess.Popen(
            [exe_path, "--modal=export"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )

        logger.info("Export modal subprocess started (PID: %s)", process.pid)

    except Exception as exc:
        logger.error("Error opening export modal: %s", exc)
        _show_error_messagebox("Export Modal Error", str(exc))


def _open_export_modal_original(config):
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        _show_error_messagebox("Export Modal Error", f"PySide6 is not available: {exc}")
        raise

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    window = ExportWindow(config)
    window.window.show()
    app.exec()
