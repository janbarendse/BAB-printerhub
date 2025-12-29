"""
Core IPC command handler implementations.

All protected printer/software actions are executed here.
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
from typing import Dict, Any

from src.logger_module import logger as app_logger
from src.core.config_manager import save_config

logger = app_logger


class CoreCommandHandler:
    """Dispatches IPC actions to the protected core."""

    def __init__(self, config: Dict[str, Any], printer, software) -> None:
        self.config = config
        self.printer = printer
        self.software = software
        self._lock = threading.Lock()

        self._is_cloud_mode = (
            config.get("mode") == "cloud"
            and config.get("babportal", {}).get("enabled", False)
        )
        self._wp_sender = None

    def _ensure_wp_sender(self) -> None:
        if not self._is_cloud_mode or self._wp_sender:
            return
        try:
            wp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "wordpress")
            import sys
            sys.path.insert(0, wp_dir)
            from wordpress_command_sender import WordPressCommandSender

            self._wp_sender = WordPressCommandSender(self.config)
            logger.info("IPC: Cloud mode enabled, WordPress sender initialized")
        except Exception as exc:
            logger.error("IPC: Failed to init WordPress sender: %s", exc)
            self._is_cloud_mode = False

    def handle(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Main dispatcher for IPC actions."""
        if action == "ping":
            return {"success": True, "message": "pong"}

        if action.startswith("fiscal."):
            return self._handle_fiscal(action, payload)

        return {"success": False, "error": f"Unknown action: {action}"}

    def _handle_fiscal(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_wp_sender()

        with self._lock:
            try:
                if action == "fiscal.print_x_report":
                    return self._print_x_report()
                if action == "fiscal.print_z_report":
                    return self._print_z_report()
                if action == "fiscal.print_z_report_by_date":
                    return self._print_z_report_by_date(payload)
                if action == "fiscal.print_z_report_by_number":
                    return self._print_z_report_by_number(payload)
                if action == "fiscal.print_z_report_by_number_range":
                    return self._print_z_report_by_number_range(payload)
                if action == "fiscal.reprint_document":
                    return self._reprint_document(payload)
                if action == "fiscal.print_no_sale":
                    return self._print_no_sale(payload)
                if action == "fiscal.get_config":
                    return {"success": True, "config": self.config.get("fiscal_tools", {})}
                if action == "fiscal.get_min_date":
                    value = self.config.get("fiscal_tools", {}).get(
                        "Z_report_from",
                        datetime.date.today().strftime("%Y-%m-%d"),
                    )
                    return {"success": True, "min_date": value}
                if action == "fiscal.get_z_report_config":
                    return self._get_z_report_config()

            except Exception as exc:
                logger.error("IPC fiscal action failed: %s", exc, exc_info=True)
                return {"success": False, "error": str(exc)}

        return {"success": False, "error": f"Unknown fiscal action: {action}"}

    def _print_x_report(self) -> Dict[str, Any]:
        logger.info("IPC: X-Report requested")
        if self._is_cloud_mode and self._wp_sender:
            return self._wp_sender.print_x_report()

        response = self.printer.print_x_report()
        if response.get("success"):
            return {"success": True, "message": "X Report printed successfully"}
        return {"success": False, "error": response.get("error", "Failed to print X Report")}

    def _print_z_report(self) -> Dict[str, Any]:
        logger.info("IPC: Z-Report requested")
        if self._is_cloud_mode and self._wp_sender:
            return self._wp_sender.print_z_report()

        now = datetime.datetime.now()
        self.config.setdefault("fiscal_tools", {})["last_z_report_print_time"] = now.isoformat()
        save_config(self.config)

        response = self.printer.print_z_report(close_fiscal_day=True)
        if response.get("success"):
            try:
                from src.core.salesbook_exporter import export_salesbook_after_z_report

                export_salesbook_after_z_report(self.config)
            except Exception as exc:
                logger.error("IPC: Salesbook export failed: %s", exc)
            return {"success": True, "message": "Z Report command sent to printer"}
        return {"success": False, "error": response.get("error", "Failed to print Z Report")}

    def _print_z_report_by_date(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        start_date = payload.get("start_date")
        end_date = payload.get("end_date")
        if not start_date or not end_date:
            return {"success": False, "error": "Start and end dates are required"}

        logger.info("IPC: Z-Report by date %s -> %s", start_date, end_date)
        if self._is_cloud_mode and self._wp_sender:
            return self._wp_sender.print_z_report_by_date(start_date, end_date)

        start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        response = self.printer.print_z_report_by_date(start_date_obj, end_date_obj)
        if response.get("success"):
            return {"success": True, "message": response.get("message", "Z Reports printed")}
        return {"success": False, "error": response.get("error", "Failed to print Z Reports")}

    def _print_z_report_by_number(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        number = payload.get("number")
        if number is None:
            return {"success": False, "error": "Report number is required"}

        logger.info("IPC: Z-Report by number %s", number)
        response = self.printer.print_z_report_by_number(int(number))
        if response.get("success"):
            return {"success": True, "message": response.get("message", "Z Report printed")}
        return {"success": False, "error": response.get("error", "Failed to print Z Report")}

    def _print_z_report_by_number_range(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        start_number = payload.get("start_number")
        end_number = payload.get("end_number")
        if start_number is None or end_number is None:
            return {"success": False, "error": "Start and end numbers are required"}

        start_num = int(start_number)
        end_num = int(end_number)
        if start_num > end_num:
            return {"success": False, "error": "Start number must be less than or equal to end number"}

        logger.info("IPC: Z-Report range %s -> %s", start_num, end_num)
        if self._is_cloud_mode and self._wp_sender:
            return self._wp_sender.print_z_report_range(start_num, end_num)

        response = self.printer.print_z_report_by_number_range(start_num, end_num)
        if response.get("success"):
            return {"success": True, "message": response.get("message", "Z Reports printed")}
        return {"success": False, "error": response.get("error", "Failed to print Z Reports")}

    def _reprint_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        document_number = payload.get("document_number")
        if not document_number:
            return {"success": False, "error": "Document number is required"}

        logger.info("IPC: Reprint document %s", document_number)
        if self._is_cloud_mode and self._wp_sender:
            return self._wp_sender.print_check(document_number)

        response = self.printer.reprint_document(str(document_number))
        if response.get("success"):
            return {"success": True, "message": "Document copy printed (NO SALE)"}
        return {"success": False, "error": response.get("error", "Failed to reprint document")}

    def _print_no_sale(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        reason = payload.get("reason", "")
        logger.info("IPC: No Sale requested")
        if self._is_cloud_mode and self._wp_sender:
            return self._wp_sender.print_no_sale(reason)

        response = self.printer.print_no_sale(reason)
        if response.get("success"):
            return {"success": True, "message": "No Sale receipt printed"}
        return {"success": False, "error": response.get("error", "Failed to print No Sale")}

    def _get_z_report_config(self) -> Dict[str, Any]:
        fiscal_tools = self.config.get("fiscal_tools", {})
        today = datetime.date.today()
        yesterday = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        last_print_time = fiscal_tools.get("last_z_report_print_time")
        today_z_printed = False
        if last_print_time:
            try:
                last_print_date = datetime.datetime.fromisoformat(last_print_time).date()
                today_z_printed = last_print_date == today
            except Exception:
                pass

        return {
            "success": True,
            "z_report_from": fiscal_tools.get("Z_report_from", "2025-01-01"),
            "yesterday": yesterday,
            "today": today.strftime("%Y-%m-%d"),
            "today_z_printed": today_z_printed,
            "last_print_time": last_print_time,
        }
