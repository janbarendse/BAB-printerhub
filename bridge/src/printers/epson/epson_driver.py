"""
Epson Fiscal Printer Driver (STUB)

This is a placeholder stub for the Epson fiscal printer driver.
Epson printers use the ESC/POS protocol, which is different from the MHI protocol
used by CTS310ii, Star, and Citizen printers.

Implementation is planned for Q2 2026.
"""

import os
from typing import Dict, Any, List, Optional

from ..base_printer import BasePrinter

# Import logger from parent directory
import sys
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from logger_module import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


class EpsonDriver(BasePrinter):
    """
    Epson Fiscal Printer Driver (STUB).

    This is a placeholder implementation for Epson fiscal printers.
    Epson uses the ESC/POS protocol, which differs from the MHI protocol
    used by CTS310ii, Star, and Citizen printers.

    All methods raise NotImplementedError until the driver is fully implemented.
    Implementation is planned for Q2 2026.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the Epson driver stub.

        Args:
            config: Printer-specific config dict (not used in stub)
        """
        super().__init__(config)
        logger.warning("Epson driver is a stub. Implementation planned for Q2 2026.")

    def get_name(self) -> str:
        """Get printer driver name."""
        return "epson"

    def connect(self) -> bool:
        """Detect and connect to the printer.

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def disconnect(self) -> bool:
        """Disconnect from the printer.

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

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
        sequential_order_id: Optional[str] = None,
        pos_name: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_crib: Optional[str] = None
    ) -> Dict[str, Any]:
        """Print a fiscal receipt document.

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def print_x_report(self) -> Dict[str, Any]:
        """Print X report (non-fiscal daily report).

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def print_z_report(self, close_fiscal_day: bool = True) -> Dict[str, Any]:
        """Print Z report (fiscal day closing).

        Args:
            close_fiscal_day: Whether to close the fiscal day

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def print_z_report_by_date(self, start_date, end_date) -> Dict[str, Any]:
        """Print Z reports for a date range.

        Args:
            start_date: Start date
            end_date: End date

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def print_z_report_by_number(self, report_number: int) -> Dict[str, Any]:
        """Print a single Z report by number.

        Args:
            report_number: Z report sequential number

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def print_z_report_by_number_range(self, start: int, end: int) -> Dict[str, Any]:
        """Print Z reports by number range.

        Args:
            start: Start report number
            end: End report number

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def reprint_document(self, document_number: str) -> Dict[str, Any]:
        """Reprint a document copy (NO SALE).

        Args:
            document_number: Document number to reprint

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def print_no_sale(self) -> Dict[str, Any]:
        """Open cash drawer (no sale).

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )

    def get_status(self) -> Dict[str, Any]:
        """Get printer status.

        Raises:
            NotImplementedError: Epson driver not implemented yet
        """
        raise NotImplementedError(
            "Epson driver not implemented. Planned for Q2 2026. "
            "Uses different ESC/POS protocol."
        )
