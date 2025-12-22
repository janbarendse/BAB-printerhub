"""
Base abstract class for POS software integrations.

This module defines the interface that all POS software integrations
(Odoo, TCPOS, Simphony, QuickBooks POS) must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseSoftware(ABC):
    """
    Abstract base class for POS software integrations.

    Each integration (Odoo, TCPOS, etc.) must implement this interface.
    This ensures consistent behavior across all software integrations.
    """

    def __init__(self, config: Dict[str, Any], printer):
        """
        Initialize the software integration.

        Args:
            config: Software-specific config dict from config.json
            printer: Active printer instance (implements BasePrinter)
        """
        self.config = config
        self.printer = printer
        self.running = False
        self.thread = None

    @abstractmethod
    def start(self) -> bool:
        """
        Start the integration (polling, watchdog, etc.).

        This should be non-blocking - start a background thread if needed.

        Returns:
            bool: True if started successfully, False otherwise
        """
        pass

    @abstractmethod
    def stop(self) -> bool:
        """
        Stop the integration gracefully.

        This should cleanly shut down any background threads and
        release resources.

        Returns:
            bool: True if stopped successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_last_order_id(self) -> int:
        """
        Get the last processed order ID.

        Returns:
            int: Last order ID processed (0 if none)
        """
        pass

    @abstractmethod
    def set_last_order_id(self, order_id: int) -> bool:
        """
        Update the last processed order ID.

        This is typically saved to config.json to track progress.

        Args:
            order_id: New last order ID

        Returns:
            bool: True if saved successfully
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the integration.

        Returns:
            dict: Status information including:
                - running: bool (is integration active?)
                - last_poll_time: datetime (when last checked for orders)
                - last_order_id: int (last processed order)
                - errors: list (recent errors if any)
                - additional software-specific fields
        """
        pass

    @abstractmethod
    def parse_transaction(self, raw_data: Any) -> Optional[Dict[str, Any]]:
        """
        Parse raw transaction data into standardized format.

        This converts software-specific transaction format into the
        standardized format expected by printer drivers.

        Args:
            raw_data: Raw transaction data (format varies by software)

        Returns:
            dict: Standardized transaction dict, or None if parse fails.
                  See docs/API.md for standardized format specification.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get the software integration name.

        Returns:
            str: Software name (e.g., "odoo", "tcpos", "simphony", "quickbooks")
        """
        pass

    def get_transaction_folder(self) -> str:
        """
        Get the transaction storage folder name.

        Returns:
            str: Folder name (e.g., "odoo-transactions", "tcpos-transactions")
        """
        return f"{self.get_name()}-transactions"

    def __repr__(self) -> str:
        """String representation of the integration."""
        return f"<{self.__class__.__name__} ({self.get_name()}) running={self.running}>"
