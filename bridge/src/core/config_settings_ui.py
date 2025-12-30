"""
Config Settings UI using PySide6.

Replaces the webview settings modal with a native Qt dialog.
"""

import json
import logging
import os
import sys
import threading
import ctypes
from PySide6 import QtCore, QtGui

from src.logger_module import logger as app_logger

logger = app_logger


def _show_error_messagebox(title, message):
    """Show native Windows error dialog for debugging modal failures."""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(message), title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def _install_excepthook():
    def _hook(exc_type, exc_value, exc_traceback):
        logger.error("Settings modal crash: %s", exc_value, exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = _hook

    def _qt_handler(msg_type, context, message):
        logger.error("Qt message: %s", message)
    try:
        QtCore.qInstallMessageHandler(_qt_handler)
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


def _get_nested(config, path, default=None):
    current = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _validate_changes(changes):
    errors = []

    if "mode" in changes:
        if changes["mode"] not in ["standalone", "cloud"]:
            errors.append("Mode must be 'standalone' or 'cloud'")

    if "software" in changes and "active" in changes["software"]:
        valid_software = ["odoo", "tcpos", "simphony", "quickbooks"]
        if changes["software"]["active"] not in valid_software:
            errors.append(f"Invalid software: {changes['software']['active']}")

    if "printer" in changes and "active" in changes["printer"]:
        valid_printers = ["cts310ii", "star", "citizen", "epson"]
        if changes["printer"]["active"] not in valid_printers:
            errors.append(f"Invalid printer: {changes['printer']['active']}")

    if "polling" in changes:
        for key in ["printer_retry_interval_seconds", "software_retry_interval_seconds"]:
            if key in changes["polling"]:
                try:
                    value = int(changes["polling"][key])
                    if value < 1 or value > 300:
                        errors.append(f"{key} must be between 1 and 300 seconds")
                except ValueError:
                    errors.append(f"{key} must be a number")

    if "babportal" in changes and "poll_interval" in changes["babportal"]:
        try:
            value = int(changes["babportal"]["poll_interval"])
            if value < 1 or value > 60:
                errors.append("BABPortal poll interval must be between 1 and 60 seconds")
        except ValueError:
            errors.append("BABPortal poll interval must be a number")

    if "system" in changes and "log_level" in changes["system"]:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if changes["system"]["log_level"] not in valid_levels:
            errors.append(f"Invalid log level: {changes['system']['log_level']}")

    return errors


class ConfigSettingsWindow:
    def __init__(self, config_path, config):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import (
            QMainWindow,
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QFormLayout,
            QGroupBox,
            QComboBox,
            QLineEdit,
            QSpinBox,
            QCheckBox,
            QMessageBox,
            QScrollArea,
        )

        self._Qt = Qt
        self._QMessageBox = QMessageBox
        self.config_path = config_path
        self.config = config

        _install_excepthook()

        self.window = QMainWindow()
        self.window.setWindowTitle("BAB Cloud - Settings")
        self.window.resize(960, 720)
        self.window.setMinimumSize(820, 600)

        base_dir = _resolve_base_dir()
        icon_path = os.path.join(base_dir, "logo.png")
        arrow_down_path = os.path.join(base_dir, "arrow_down.svg")
        arrow_up_path = os.path.join(base_dir, "arrow_up.svg")
        if os.path.exists(icon_path):
            self.window.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.window.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        title = QLabel("BAB Cloud - Settings")
        title.setObjectName("title")
        subtitle = QLabel("Edit configuration and restart the core")
        subtitle.setObjectName("subtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        title_layout.setSpacing(4)
        title_layout.setAlignment(self._Qt.AlignVCenter)

        logo_label = QLabel()
        logo_label.setObjectName("logo")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QPixmap

            pix = QPixmap(icon_path)
            if not pix.isNull():
                logo_label.setPixmap(pix.scaled(64, 64, self._Qt.KeepAspectRatio, self._Qt.SmoothTransformation))
        header_layout.setAlignment(self._Qt.AlignVCenter)
        header_layout.addWidget(logo_label)
        header_layout.addSpacing(12)
        header_layout.addWidget(title_box, 1)

        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 18)
        content_layout.setSpacing(16)

        content_layout.addWidget(self._build_general_section())
        content_layout.addWidget(self._build_printer_section())
        content_layout.addWidget(self._build_babportal_section())
        content_layout.addWidget(self._build_polling_section())
        content_layout.addWidget(self._build_system_section())
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QWidget()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")

        footer_layout.addWidget(self.status_label, 1)

        restart_btn = QPushButton("Restart App")
        restart_btn.setObjectName("restartButton")
        save_btn = QPushButton("Save & Restart")
        save_btn.setObjectName("saveButton")
        close_btn = QPushButton("Close")
        close_btn.setObjectName("closeButton")

        footer_layout.addWidget(restart_btn)
        footer_layout.addWidget(save_btn)
        footer_layout.addWidget(close_btn)

        layout.addWidget(footer)

        restart_btn.clicked.connect(self.restart_app)
        save_btn.clicked.connect(self.save_config)
        close_btn.clicked.connect(self.window.close)

        self._apply_styles(arrow_down_path, arrow_up_path)
        self._load_config()
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
            QLabel#title {
                font-size: 22px;
                font-weight: 700;
                color: #ffffff;
                margin: 0;
                padding: 0;
                line-height: 22px;
            }
            QLabel#subtitle {
                font-size: 12px;
                color: #f3d6d6;
                margin: 0;
                padding: 0;
                line-height: 12px;
            }
            QComboBox, QSpinBox {
                padding-right: 24px;
                font-size: 18px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 60px;
                margin: 2px;
                border: none;
                background: #f3f4f6;
                border-radius: 8px;
            }
            QComboBox::down-arrow {
                image: url(__ARROW_DOWN__);
                width: 18px;
                height: 18px;
                subcontrol-position: center;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: content;
                subcontrol-position: center right;
                width: 60px;
                margin-top: 6px;
                margin-bottom: 6px;
                margin-right: 6px;
                border: none;
            }
            QSpinBox::up-button {
                background: transparent;
                border-radius: 8px;
            }
            QSpinBox::down-button {
                background: transparent;
            }
            QSpinBox::up-arrow {
                image: url(__ARROW_UP__);
                width: 18px;
                height: 18px;
                subcontrol-position: center right;
                right: 6px;
            }
            QSpinBox::down-arrow {
                image: url(__ARROW_DOWN__);
                width: 18px;
                height: 18px;
                subcontrol-position: center right;
                right: -12px;
            }
            QWidget#scroll {
                background: transparent;
            }
            QGroupBox {
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                margin-top: 16px;
                padding: 18px;
                background: #ffffff;
            }
            QLabel#logo {
                background: #ffffff;
                border-radius: 10px;
                padding: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: padding;
                subcontrol-position: top left;
                left: 12px;
                top: 10px;
                padding: 0 6px;
                color: #111827;
                font-weight: 700;
            }
            QCheckBox {
                color: #111827;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #d1d5db;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #b91c1c;
                border-color: #b91c1c;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                color: #111827;
                font-size: 18px;
            }
            QCheckBox {
                color: #111827;
            }
            QWidget#footer {
                background: #f3f4f6;
                border-top: 1px solid #e5e7eb;
            }
            QLabel#status {
                color: #6b7280;
            }
            QPushButton {
                border: none;
                padding: 7px 16px;
                border-radius: 6px;
                font-weight: 600;
                color: #ffffff;
            }
            QPushButton#saveButton {
                background-color: #b91c1c;
            }
            QPushButton#saveButton:hover {
                background-color: #991b1b;
            }
            QPushButton#restartButton {
                background-color: #374151;
            }
            QPushButton#restartButton:hover {
                background-color: #1f2937;
            }
            QPushButton#closeButton {
                background-color: #6b7280;
            }
            QPushButton#closeButton:hover {
                background-color: #4b5563;
            }
            """
        style = style.replace("__ARROW_DOWN__", arrow_down_url)
        style = style.replace("__ARROW_UP__", arrow_up_url)
        self.window.setStyleSheet(style)

    def _build_general_section(self):
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QComboBox, QCheckBox

        group = QGroupBox("General")
        form = QFormLayout(group)
        self.software_active = QComboBox()
        self.software_active.addItems(["odoo", "tcpos", "simphony", "quickbooks"])
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["standalone", "cloud"])

        form.addRow("Active software", self.software_active)
        form.addRow("Run mode", self.mode_combo)
        return group

    def _build_printer_section(self):
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QComboBox, QLineEdit, QSpinBox

        printer_group = QGroupBox("Printer")
        printer_form = QFormLayout(printer_group)
        self.printer_active = QComboBox()
        self.printer_active.addItems(["cts310ii", "star", "citizen", "epson"])
        self.printer_com_port = QLineEdit()
        self.printer_baud_rate = QSpinBox()
        self.printer_baud_rate.setRange(1200, 115200)
        self.printer_baud_rate.setSingleStep(1200)

        printer_form.addRow("Active printer", self.printer_active)
        printer_form.addRow("COM port", self.printer_com_port)
        printer_form.addRow("Baud rate", self.printer_baud_rate)

        self.printer_active.currentTextChanged.connect(self._load_printer_details)

        return printer_group

    def _build_babportal_section(self):
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QLineEdit, QSpinBox, QCheckBox

        group = QGroupBox("BABPortal")
        form = QFormLayout(group)

        self.babportal_enabled = QCheckBox("Enabled")
        self.babportal_url = QLineEdit()
        self.babportal_device_id = QLineEdit()
        self.babportal_device_token = QLineEdit()
        self.babportal_poll_interval = QSpinBox()
        self.babportal_poll_interval.setRange(1, 60)
        self.babportal_wp_username = QLineEdit()
        self.babportal_wp_password = QLineEdit()
        self.babportal_wp_password.setEchoMode(QLineEdit.Password)

        form.addRow("", self.babportal_enabled)
        form.addRow("URL", self.babportal_url)
        form.addRow("Device ID", self.babportal_device_id)
        form.addRow("Device Token", self.babportal_device_token)
        form.addRow("Poll interval (sec)", self.babportal_poll_interval)
        form.addRow("WP username", self.babportal_wp_username)
        form.addRow("WP app password", self.babportal_wp_password)

        return group

    def _build_polling_section(self):
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QSpinBox

        group = QGroupBox("Polling")
        form = QFormLayout(group)
        self.poll_printer_retry = QSpinBox()
        self.poll_printer_retry.setRange(1, 300)
        self.poll_software_retry = QSpinBox()
        self.poll_software_retry.setRange(1, 300)

        form.addRow("Printer retry (sec)", self.poll_printer_retry)
        form.addRow("Software retry (sec)", self.poll_software_retry)

        return group

    def _build_system_section(self):
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QComboBox, QCheckBox

        group = QGroupBox("System")
        form = QFormLayout(group)
        self.system_log_level = QComboBox()
        self.system_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.system_demo_mode = QCheckBox("Enable demo mode")
        form.addRow("Log level", self.system_log_level)
        form.addRow("", self.system_demo_mode)

        return group

    def _load_config(self):
        self.software_active.setCurrentText(_get_nested(self.config, ["software", "active"], "tcpos"))
        self.mode_combo.setCurrentText(self.config.get("mode", "standalone"))

        self.printer_active.setCurrentText(_get_nested(self.config, ["printer", "active"], "cts310ii"))
        self._load_printer_details(self.printer_active.currentText())

        self.babportal_enabled.setChecked(_get_nested(self.config, ["babportal", "enabled"], False))
        self.babportal_url.setText(_get_nested(self.config, ["babportal", "url"], ""))
        self.babportal_device_id.setText(_get_nested(self.config, ["babportal", "device_id"], ""))
        self.babportal_device_token.setText(_get_nested(self.config, ["babportal", "device_token"], ""))
        self.babportal_poll_interval.setValue(int(_get_nested(self.config, ["babportal", "poll_interval"], 10)))
        self.babportal_wp_username.setText(_get_nested(self.config, ["babportal", "wordpress_username"], ""))
        self.babportal_wp_password.setText(_get_nested(self.config, ["babportal", "wordpress_app_password"], ""))

        self.poll_printer_retry.setValue(int(_get_nested(self.config, ["polling", "printer_retry_interval_seconds"], 5)))
        self.poll_software_retry.setValue(int(_get_nested(self.config, ["polling", "software_retry_interval_seconds"], 5)))

        self.system_log_level.setCurrentText(_get_nested(self.config, ["system", "log_level"], "INFO"))
        self.system_demo_mode.setChecked(_get_nested(self.config, ["system", "demo_mode"], False))

    def _load_printer_details(self, printer_name):
        printer_cfg = _get_nested(self.config, ["printer", printer_name], {})
        self.printer_com_port.setText(str(printer_cfg.get("com_port", "COM1")))
        try:
            self.printer_baud_rate.setValue(int(printer_cfg.get("baud_rate", 9600)))
        except ValueError:
            self.printer_baud_rate.setValue(9600)

    def _set_status(self, message, is_error=False):
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: #f87171;")
        else:
            self.status_label.setStyleSheet("color: #94a3b8;")

    def _collect_changes(self):
        active_printer = self.printer_active.currentText()
        return {
            "software": {
                "active": self.software_active.currentText(),
            },
            "printer": {
                "active": active_printer,
                active_printer: {
                    "com_port": self.printer_com_port.text().strip(),
                    "baud_rate": int(self.printer_baud_rate.value()),
                },
            },
            "mode": self.mode_combo.currentText(),
            "babportal": {
                "enabled": self.babportal_enabled.isChecked(),
                "url": self.babportal_url.text().strip(),
                "device_id": self.babportal_device_id.text().strip(),
                "device_token": self.babportal_device_token.text().strip(),
                "poll_interval": int(self.babportal_poll_interval.value()),
                "wordpress_username": self.babportal_wp_username.text().strip(),
                "wordpress_app_password": self.babportal_wp_password.text().strip(),
            },
            "polling": {
                "printer_retry_interval_seconds": int(self.poll_printer_retry.value()),
                "software_retry_interval_seconds": int(self.poll_software_retry.value()),
            },
            "system": {
                "log_level": self.system_log_level.currentText(),
                "demo_mode": self.system_demo_mode.isChecked(),
            },
        }

    def save_config(self):
        changes = self._collect_changes()
        errors = _validate_changes(changes)
        if errors:
            self._set_status("Validation failed: " + ", ".join(errors), is_error=True)
            return

        try:
            updated = json.loads(json.dumps(self.config))
            updated["mode"] = changes["mode"]

            for section in ["software", "printer", "client", "miscellaneous", "polling", "babportal", "system"]:
                if section not in changes:
                    continue
                if section not in updated:
                    updated[section] = {}
                for key, value in changes[section].items():
                    if isinstance(value, dict):
                        if key not in updated[section]:
                            updated[section][key] = {}
                        updated[section][key].update(value)
                    else:
                        updated[section][key] = value

            if "software" in changes and "active" in changes["software"]:
                active_software = changes["software"]["active"]
                for software_name in ["odoo", "tcpos", "simphony", "quickbooks"]:
                    if software_name in updated["software"]:
                        updated["software"][software_name]["enabled"] = (software_name == active_software)

            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump(updated, handle, indent=2)

            self._set_status("Saved. Restarting core...")
            thread = threading.Thread(target=self._restart_with_delay, daemon=False)
            thread.start()
        except Exception as exc:
            logger.error("Error saving config: %s", exc)
            self._set_status(f"Save failed: {exc}", is_error=True)

    def restart_app(self):
        reply = self._QMessageBox.question(
            self.window,
            "Restart BAB PrintHub",
            "Restart the core application now?",
            self._QMessageBox.Yes | self._QMessageBox.No,
            self._QMessageBox.No,
        )
        if reply != self._QMessageBox.Yes:
            return

        self._set_status("Restarting core...")
        thread = threading.Thread(target=self._restart_with_delay, daemon=False)
        thread.start()

    def _restart_with_delay(self):
        import time
        time.sleep(2)
        self._restart_application()

    def _restart_application(self):
        try:
            import subprocess
            import time

            current_pid = os.getpid()
            main_process = None
            psutil = None
            try:
                import psutil as _psutil
                psutil = _psutil
            except Exception:
                psutil = None

            if psutil:
                for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                    try:
                        if proc.pid == current_pid:
                            continue
                        cmdline = " ".join(proc.info.get("cmdline") or [])
                        if "--modal" in cmdline:
                            continue
                        if "fiscal_printer_hub" in cmdline or "BAB-PrintHub" in cmdline:
                            main_process = proc
                            break
                        if _is_compiled():
                            exe = proc.info.get("exe")
                            if exe and os.path.basename(exe).lower() == os.path.basename(sys.executable).lower():
                                main_process = proc
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            if main_process:
                try:
                    main_process.terminate()
                    main_process.wait(timeout=5)
                except Exception:
                    main_process.kill()
                    main_process.wait(timeout=3)
                time.sleep(2)
            elif _is_compiled():
                exe_name = os.path.basename(sys.executable)
                cmd = f'timeout /t 2 /nobreak >nul & taskkill /F /IM "{exe_name}" >nul 2>&1 & start "" "{sys.executable}"'
                subprocess.Popen(
                    ["cmd", "/c", cmd],
                    cwd=os.path.dirname(sys.executable),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                os._exit(0)

            if _is_compiled():
                executable = sys.executable
                subprocess.Popen([executable], cwd=os.path.dirname(executable))
            else:
                bridge_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                subprocess.Popen(
                    ["py", "-3.13", "-m", "src.fiscal_printer_hub"],
                    cwd=bridge_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
                )

            os._exit(0)
        except Exception as exc:
            logger.error("Error restarting application: %s", exc)
            self._set_status(f"Restart failed: {exc}", is_error=True)


def _open_config_settings_window(config_path, config):
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        _show_error_messagebox("Settings Error", f"PySide6 is not available: {exc}")
        raise

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    try:
        window = ConfigSettingsWindow(config_path, config)
        window.window.show()
        app.exec()
    except Exception as exc:
        logger.error("Settings modal failed to open: %s", exc, exc_info=True)
        _show_error_messagebox("Settings Error", str(exc))
        raise


def open_config_settings_modal(config_path, config):
    """
    Open the config settings modal in a separate subprocess.

    Spawns a new instance of the executable with --modal=settings argument.
    """
    try:
        import subprocess

        exe_path = sys.executable
        logger.info("Opening config settings in separate subprocess (exe: %s)...", exe_path)

        process = subprocess.Popen(
            [exe_path, "--modal=settings"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )

        logger.info("Config settings subprocess started (PID: %s)", process.pid)

    except Exception as exc:
        logger.error("Error opening config settings modal: %s", exc)
        _show_error_messagebox("Settings Error", str(exc))
