"""
Base abstract class for fiscal printer drivers.

This module defines the interface that all printer drivers
(CTS310ii, Star, Citizen, Epson) must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BasePrinter(ABC):
    """
    Abstract base class for fiscal printer drivers.

    Each printer (CTS310ii, Star, Citizen, Epson) must implement this interface.
    This ensures consistent behavior across all printer drivers.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the printer driver.

        Args:
            config: Printer-specific config dict from config.json
        """
        self.config = config
        self.com_port = None
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Detect and connect to the printer.

        This typically scans COM ports to auto-detect the printer.

        Returns:
            bool: True if connected successfully
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the printer.

        Returns:
            bool: True if disconnected successfully
        """
        pass

    @abstractmethod
    def print_document(
        self,
        items: List[Dict],
        payments: List[Dict],
        service_charge: Optional[Dict] = None,
        tips: Optional[List[Dict]] = None,
        discount: Optional[Dict] = None,
        surcharge: Optional[Dict] = None,
        general_comment: str = "",
        is_refund: bool = False,
        receipt_number: Optional[str] = None,
        pos_name: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_crib: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Print a fiscal receipt document.

        Args:
            items: List of item dicts with keys: item_code, item_description,
                   item_quantity, item_price, vat_percent, etc.
            payments: List of payment dicts with keys: method, amount
            service_charge: Service charge dict with percent or amount
            tips: List of tip dicts with amount
            discount: Transaction-level discount dict
            surcharge: Transaction-level surcharge dict
            general_comment: Footer comment for receipt
            is_refund: True if this is a refund/credit note
            receipt_number: Display receipt number
            pos_name: POS terminal name
            customer_name: Customer name (optional)
            customer_crib: Customer tax ID (optional)

        Returns:
            dict: {"success": bool, "error": str, "document_number": str}
        """
        pass

    @abstractmethod
    def print_x_report(self) -> Dict[str, Any]:
        """
        Print X report (non-fiscal daily report).

        Returns:
            dict: {"success": bool, "error": str}
        """
        pass

    @abstractmethod
    def print_z_report(self, close_fiscal_day: bool = True) -> Dict[str, Any]:
        """
        Print Z report (fiscal day closing).

        Args:
            close_fiscal_day: Whether to close the fiscal day (default: True)

        Returns:
            dict: {"success": bool, "error": str}
        """
        pass

    @abstractmethod
    def print_z_report_by_date(self, start_date, end_date) -> Dict[str, Any]:
        """
        Print Z reports for a date range.

        Args:
            start_date: Start date (format varies by printer)
            end_date: End date (format varies by printer)

        Returns:
            dict: {"success": bool, "error": str, "message": str}
        """
        pass

    @abstractmethod
    def print_z_report_by_number(self, report_number: int) -> Dict[str, Any]:
        """
        Print a single Z report by number.

        Args:
            report_number: Z report sequential number

        Returns:
            dict: {"success": bool, "error": str}
        """
        pass

    @abstractmethod
    def print_z_report_by_number_range(self, start: int, end: int) -> Dict[str, Any]:
        """
        Print Z reports by number range.

        Args:
            start: Start report number
            end: End report number

        Returns:
            dict: {"success": bool, "error": str}
        """
        pass

    @abstractmethod
    def reprint_document(self, document_number: str) -> Dict[str, Any]:
        """
        Reprint a document copy (NO SALE).

        Args:
            document_number: Document number to reprint

        Returns:
            dict: {"success": bool, "error": str}
        """
        pass

    @abstractmethod
    def print_no_sale(self) -> Dict[str, Any]:
        """
        Open cash drawer (no sale).

        Returns:
            dict: {"success": bool, "error": str}
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get printer status.

        Returns:
            dict: Status information including:
                - connected: bool
                - com_port: str
                - state: str (printer state machine state)
                - paper_low: bool
                - cover_open: bool
                - error: str (if any)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get printer driver name.

        Returns:
            str: Printer name (e.g., "cts310ii", "star", "citizen", "epson")
        """
        pass

    def __repr__(self) -> str:
        """String representation of the printer."""
        status = "connected" if self.connected else "disconnected"
        return f"<{self.__class__.__name__} ({self.get_name()}) {status} on {self.com_port or 'None'}>"

    def is_demo_mode(self) -> bool:
        """Return True when demo mode is enabled in config."""
        system_cfg = self.config.get("system", {})
        return bool(system_cfg.get("demo_mode", False) or self.config.get("demo_mode", False))
