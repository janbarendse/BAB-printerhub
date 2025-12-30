"""
Fiscal Tools UI using PySide6.

Provides the same layout as the webview modal with a native Qt UI.
"""

import datetime
import logging
import os
import sys
import ctypes

from PySide6 import QtCore, QtGui

logger = logging.getLogger(__name__)


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


class FiscalToolsWindow:
    def __init__(self):
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
            QLineEdit,
            QDateEdit,
            QSpinBox,
            QFrame,
            QScrollArea,
        )

        from .ipc_client import IpcClient

        self._Qt = Qt
        self._QDate = QDate
        self.client = IpcClient()

        self.window = QMainWindow()
        self.window.setWindowTitle("BAB Cloud - Fiscal Tools")
        self.window.resize(920, 700)
        self.window.setMinimumSize(800, 600)

        base_dir = _resolve_base_dir()
        icon_path = os.path.join(base_dir, "logo.png")
        arrow_down_path = os.path.join(base_dir, "assets", "icons", "arrow_down.svg")
        arrow_up_path = os.path.join(base_dir, "assets", "icons", "arrow_up.svg")
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
        logo.setObjectName("logo")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QPixmap

            pix = QPixmap(icon_path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(72, 72, self._Qt.KeepAspectRatio, self._Qt.SmoothTransformation))

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title = QLabel("Fiscal PrintHub")
        title.setObjectName("headerTitle")
        subtitle = QLabel("Quick Report Generation")
        subtitle.setObjectName("headerSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        title_layout.setSpacing(4)
        title_layout.setAlignment(self._Qt.AlignVCenter)

        header_layout.setAlignment(self._Qt.AlignVCenter)
        header_layout.addWidget(logo)
        header_layout.addWidget(title_box, 1)

        header_actions = QWidget()
        header_actions_layout = QHBoxLayout(header_actions)
        header_actions_layout.setContentsMargins(0, 0, 0, 0)
        header_actions_layout.setSpacing(12)

        self.receipt_doc = QLineEdit()
        self.receipt_doc.setPlaceholderText("Doc #")
        self.receipt_doc.setObjectName("inputField")
        receipt_btn = QPushButton("Print Copy")
        receipt_btn.setObjectName("headerButton")
        receipt_btn.clicked.connect(self.print_copy)
        receipt_card = self._build_action_card("Receipt Copy", [self.receipt_doc, receipt_btn])

        self.no_sale_reason = QLineEdit()
        self.no_sale_reason.setPlaceholderText("Reason (optional)")
        self.no_sale_reason.setObjectName("inputField")
        no_sale_btn = QPushButton("No Sale")
        no_sale_btn.setObjectName("headerButton")
        no_sale_btn.clicked.connect(self.print_no_sale)
        no_sale_card = self._build_action_card("No Sale", [self.no_sale_reason, no_sale_btn])

        header_actions_layout.addWidget(receipt_card)
        header_actions_layout.addWidget(no_sale_card)
        header_layout.addWidget(header_actions)

        root_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 18)
        content_layout.setSpacing(18)

        today_label = QLabel("Today's Reports")
        today_label.setObjectName("sectionTitle")
        content_layout.addWidget(today_label)

        today_grid = QGridLayout()
        today_grid.setSpacing(16)

        z_card = self._build_report_card(
            title="Z Report (Today)",
            description="Closes the fiscal day and prints the Z Report. Printer will only print if there are transactions.",
            button_text="Close Fiscal Day - Z Report",
            button_object="primaryButtonWide",
            handler=self.print_z_report,
            accent="red",
        )
        x_card = self._build_report_card(
            title="X Report (Today)",
            description="Current shift status without closing the fiscal day.",
            button_text="Print X Report",
            button_object="darkButtonWide",
            handler=self.print_x_report,
            accent="gray",
        )
        today_grid.addWidget(z_card, 0, 0)
        today_grid.addWidget(x_card, 0, 1)
        content_layout.addLayout(today_grid)

        history_label = QLabel("Historical Reports")
        history_label.setObjectName("sectionTitle")
        content_layout.addWidget(history_label)

        history_grid = QGridLayout()
        history_grid.setSpacing(16)

        date_card = self._build_date_range_card()
        number_card = self._build_number_range_card()
        history_grid.addWidget(date_card, 0, 0)
        history_grid.addWidget(number_card, 0, 1)
        content_layout.addLayout(history_grid)

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

        close_btn = QPushButton("Close")
        close_btn.setObjectName("darkButtonWide")
        close_btn.clicked.connect(self.window.close)
        footer_layout.addWidget(close_btn)

        root_layout.addWidget(footer)

        self._apply_styles(arrow_down_path, arrow_up_path)
        self._init_dates()
        QtCore.QTimer.singleShot(0, self._finalize_layout)

    def _finalize_layout(self):
        self.window.adjustSize()
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen:
            max_height = max(480, screen.availableGeometry().height() - 40)
            target_height = min(self.window.sizeHint().height(), max_height)
            self.window.setMaximumHeight(target_height)
            if self.window.height() > target_height:
                self.window.resize(self.window.width(), target_height)

    def _apply_styles(self, arrow_down_path, arrow_up_path):
        arrow_down_url = arrow_down_path.replace("\\", "/")
        arrow_up_url = arrow_up_path.replace("\\", "/")
        style = """
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
                margin: 0;
                padding: 0;
                line-height: 22px;
            }
            QLabel#headerSubtitle {
                font-size: 12px;
                color: #f3d6d6;
                margin: 0;
                padding: 0;
                line-height: 12px;
            }
            QDateEdit#inputField, QSpinBox#inputField {
                padding-right: 24px;
                font-size: 18px;
            }
            QDateEdit#inputField::drop-down, QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 60px;
                margin: 2px;
                border: none;
                background: #f3f4f6;
                border-radius: 8px;
            }
            QDateEdit#inputField::down-arrow, QDateEdit::down-arrow {
                image: url(__ARROW_DOWN__);
                width: 18px;
                height: 18px;
                subcontrol-position: center;
            }
            QSpinBox#inputField::up-button, QSpinBox#inputField::down-button {
                subcontrol-origin: content;
                subcontrol-position: center right;
                width: 60px;
                margin-top: 6px;
                margin-bottom: 6px;
                margin-right: 6px;
                border: none;
            }
            QSpinBox#inputField::up-button {
                background: transparent;
                border-radius: 8px;
            }
            QSpinBox#inputField::down-button {
                background: transparent;
            }
            QSpinBox#inputField::up-arrow {
                image: url(__ARROW_UP__);
                width: 18px;
                height: 18px;
                subcontrol-position: center right;
                right: 6px;
            }
            QSpinBox#inputField::down-arrow {
                image: url(__ARROW_DOWN__);
                width: 18px;
                height: 18px;
                subcontrol-position: center right;
                right: -12px;
            }
            QLabel#sectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #111827;
                padding-left: 2px;
            }
            QWidget#actionCard {
                background: #a6252a;
                border: 1px solid #b33a3f;
                border-radius: 10px;
            }
            QLabel#actionTitle {
                font-size: 12px;
                font-weight: 700;
                color: #ffffff;
            }
            QWidget#scroll {
                background: transparent;
            }
            QLabel#logo {
                background: #ffffff;
                border-radius: 10px;
                padding: 6px;
            }
            QFrame#card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
            QFrame#cardRed {
                background: #fff5f5;
                border: 2px solid #ef4444;
                border-radius: 12px;
            }
            QFrame#cardGray {
                background: #ffffff;
                border: 2px solid #9ca3af;
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
            QLineEdit#inputField {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                color: #111827;
            }
            QDateEdit#inputField {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                color: #111827;
            }
            QSpinBox#inputField {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                color: #111827;
            }
            QPushButton#headerButton {
                background-color: #ffffff;
                color: #b91c1c;
                border: 1px solid #fecaca;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
            }
            QPushButton#headerButton:hover {
                background-color: #fef2f2;
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
            """
        style = style.replace("__ARROW_DOWN__", arrow_down_url)
        style = style.replace("__ARROW_UP__", arrow_up_url)
        self.window.setStyleSheet(style)

    def _build_action_card(self, title, widgets):
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QWidget

        card = QWidget()
        card.setObjectName("actionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        label = QLabel(title)
        label.setObjectName("actionTitle")
        layout.addWidget(label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        for widget in widgets:
            row_layout.addWidget(widget)
        layout.addWidget(row)
        return card

    def _build_report_card(self, title, description, button_text, button_object, handler, accent):
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QFrame

        frame = QFrame()
        if accent == "red":
            frame.setObjectName("cardRed")
        elif accent == "gray":
            frame.setObjectName("cardGray")
        else:
            frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("cardDesc")
        desc_label.setWordWrap(True)

        btn = QPushButton(button_text)
        btn.setObjectName(button_object)
        btn.clicked.connect(handler)

        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch(1)
        layout.addWidget(btn)
        return frame

    def _build_date_range_card(self):
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QGridLayout, QPushButton, QFrame, QDateEdit
        from PySide6.QtCore import QDate

        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Z Reports by Date Range")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)

        from_label = QLabel("From (dd-mm-yy)")
        to_label = QLabel("To (dd-mm-yy)")
        self.date_start = QDateEdit()
        self.date_start.setObjectName("inputField")
        self.date_start.setDisplayFormat("dd-MM-yy")
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate())
        self.date_end = QDateEdit()
        self.date_end.setObjectName("inputField")
        self.date_end.setDisplayFormat("dd-MM-yy")
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())

        grid.addWidget(from_label, 0, 0)
        grid.addWidget(to_label, 0, 1)
        grid.addWidget(self.date_start, 1, 0)
        grid.addWidget(self.date_end, 1, 1)
        layout.addLayout(grid)

        btn = QPushButton("Print Date Range")
        btn.setObjectName("primaryButtonWide")
        btn.clicked.connect(self.print_z_report_by_date)
        layout.addWidget(btn)
        return frame

    def _build_number_range_card(self):
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QGridLayout, QPushButton, QSpinBox, QFrame

        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Z Reports by Number Range")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)

        start_label = QLabel("Start #")
        end_label = QLabel("End #")
        self.start_number = QSpinBox()
        self.start_number.setObjectName("inputField")
        self.start_number.setRange(1, 1000000)
        self.start_number.setValue(100)
        self.end_number = QSpinBox()
        self.end_number.setObjectName("inputField")
        self.end_number.setRange(1, 1000000)
        self.end_number.setValue(150)

        grid.addWidget(start_label, 0, 0)
        grid.addWidget(end_label, 0, 1)
        grid.addWidget(self.start_number, 1, 0)
        grid.addWidget(self.end_number, 1, 1)
        layout.addLayout(grid)

        btn = QPushButton("Print Number Range")
        btn.setObjectName("primaryButtonWide")
        btn.clicked.connect(self.print_z_report_by_number_range)
        layout.addWidget(btn)
        return frame

    def _init_dates(self):
        today = self._QDate.currentDate()
        self.date_start.setDate(today)
        self.date_end.setDate(today)

    def _set_status(self, message, is_error=False):
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: #dc2626;")
        else:
            self.status_label.setStyleSheet("color: #6b7280;")

    def _call(self, action, payload=None):
        return self.client.request(action, payload or {})

    def _handle_result(self, result, success_message, error_prefix="Error"):
        if result.get("success"):
            self._set_status(success_message)
        else:
            error = result.get("error", "Unknown error")
            self._set_status(f"{error_prefix}: {error}", is_error=True)

    def print_x_report(self):
        self._set_status("Printing X Report...")
        result = self._call("fiscal.print_x_report")
        self._handle_result(result, result.get("message", "X Report printed"))

    def print_z_report(self):
        self._set_status("Printing Z Report...")
        result = self._call("fiscal.print_z_report")
        self._handle_result(result, result.get("message", "Z Report printed"))

    def print_z_report_by_date(self):
        start_date = self.date_start.date().toString("yyyy-MM-dd")
        end_date = self.date_end.date().toString("yyyy-MM-dd")
        self._set_status(f"Printing Z Reports {start_date} to {end_date}...")
        result = self._call("fiscal.print_z_report_by_date", {"start_date": start_date, "end_date": end_date})
        self._handle_result(result, result.get("message", "Z Reports printed"))

    def print_z_report_by_number_range(self):
        start_number = int(self.start_number.value())
        end_number = int(self.end_number.value())
        self._set_status(f"Printing Z Reports #{start_number} to #{end_number}...")
        result = self._call(
            "fiscal.print_z_report_by_number_range",
            {"start_number": start_number, "end_number": end_number},
        )
        self._handle_result(result, result.get("message", "Z Reports printed"))

    def print_copy(self):
        document_number = self.receipt_doc.text().strip()
        if not document_number:
            self._set_status("Document number is required.", is_error=True)
            return
        self._set_status(f"Printing copy of document {document_number}...")
        result = self._call("fiscal.reprint_document", {"document_number": document_number})
        if result.get("success"):
            self.receipt_doc.clear()
        self._handle_result(result, result.get("message", "Document copy printed"))

    def print_no_sale(self):
        reason = self.no_sale_reason.text().strip()
        self._set_status("Printing No Sale receipt...")
        result = self._call("fiscal.print_no_sale", {"reason": reason})
        if result.get("success"):
            self.no_sale_reason.clear()
        self._handle_result(result, result.get("message", "No Sale printed"))


def _open_fiscal_tools_modal_original(config):
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        _show_error_messagebox("Fiscal Tools Error", f"PySide6 is not available: {exc}")
        raise

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    window = FiscalToolsWindow()
    window.window.show()
    app.exec()


def open_fiscal_tools_modal(config, printer=None, software=None):
    """Entry point retained for compatibility (uses IPC-backed UI)."""
    _open_fiscal_tools_modal_original(config)
