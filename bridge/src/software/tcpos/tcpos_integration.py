"""
TCPOS Integration Wrapper.

This module implements the BaseSoftware interface for TCPOS (file-based POS system).
TCPOS writes transaction XML files to a watched folder, which are then parsed and printed.
"""

import os
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from ..base_software import BaseSoftware
from .tcpos_parser import files_watchdog, tcpos_parse_transaction

# Set up logging
logger = logging.getLogger(__name__)


class TCPOSIntegration(BaseSoftware):
    """
    TCPOS integration - monitors a folder for XML transaction files.

    This is a file-based integration (not API-based like Odoo).
    TCPOS writes XML files to a configured folder, and we watch for new files,
    parse them, and send them to the printer.
    """

    def __init__(self, config: Dict[str, Any], printer, full_config: Dict[str, Any]):
        """
        Initialize TCPOS integration.

        Args:
            config: Software-specific config (config['software']['tcpos'])
            printer: Active printer instance
            full_config: Complete configuration dict
        """
        super().__init__(config, printer)
        self.full_config = full_config
        self.stop_event = threading.Event()
        self.last_file_processed = None
        self.last_scan_time = None
        self.error_log = []

    def start(self) -> bool:
        """
        Start the TCPOS file watchdog.

        This starts a background thread that monitors the transactions folder
        for new XML files.

        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            logger.warning("TCPOS integration is already running")
            return False

        try:
            # Validate configuration
            if 'transactions_folder' not in self.config:
                logger.error("Missing 'transactions_folder' in TCPOS configuration")
                return False

            transactions_folder = self.config['transactions_folder']
            if not os.path.exists(transactions_folder):
                os.makedirs(transactions_folder, exist_ok=True)
                logger.info(f"Created transactions folder: {transactions_folder}")

            # Clear stop event
            self.stop_event.clear()

            # Start watchdog thread
            self.thread = threading.Thread(
                target=files_watchdog,
                args=(self.config, self.printer, self.stop_event),
                daemon=True,
                name="TCPOSWatchdog"
            )
            self.thread.start()
            self.running = True

            logger.info(f"TCPOS integration started - watching {transactions_folder}")
            return True

        except Exception as e:
            logger.error(f"Failed to start TCPOS integration: {e}")
            self.error_log.append({
                "timestamp": datetime.now(),
                "error": str(e)
            })
            return False

    def stop(self) -> bool:
        """
        Stop the TCPOS file watchdog gracefully.

        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.running:
            logger.warning("TCPOS integration is not running")
            return False

        try:
            # Signal thread to stop
            self.stop_event.set()

            # Wait for thread to finish (with timeout)
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5.0)

                if self.thread.is_alive():
                    logger.warning("TCPOS watchdog thread did not stop within timeout")
                    # Thread will be daemon, so it will be killed on exit

            self.running = False
            logger.info("TCPOS integration stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping TCPOS integration: {e}")
            return False

    def get_last_order_id(self) -> int:
        """
        Get the last processed order ID.

        For TCPOS (file-based), we don't track order IDs in the traditional sense.
        Each file is independent.

        Returns:
            int: Always returns 0 for file-based systems
        """
        return 0

    def set_last_order_id(self, order_id: int) -> bool:
        """
        Set the last processed order ID.

        For TCPOS (file-based), this is a no-op since we use marker files
        (.processed/.skipped) to track which files have been processed.

        Args:
            order_id: Order ID (ignored for TCPOS)

        Returns:
            bool: Always returns True (no-op)
        """
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the TCPOS integration.

        Returns:
            dict: Status information including:
                - running: bool (is integration active?)
                - transactions_folder: str (folder being watched)
                - last_file_processed: str (last file processed, if any)
                - last_scan_time: datetime (when last scanned for files)
                - errors: list (recent errors if any)
        """
        status = {
            "running": self.running,
            "transactions_folder": self.config.get('transactions_folder', ''),
            "last_file_processed": self.last_file_processed,
            "last_scan_time": self.last_scan_time,
            "errors": self.error_log[-10:] if self.error_log else []  # Last 10 errors
        }

        # Add file count statistics if folder exists
        transactions_folder = self.config.get('transactions_folder')
        if transactions_folder and os.path.exists(transactions_folder):
            try:
                xml_files = []
                processed_files = []
                skipped_files = []

                for root, dirs, files in os.walk(transactions_folder):
                    for file in files:
                        if file.endswith('.xml'):
                            xml_files.append(file)
                        elif file.endswith('.processed'):
                            processed_files.append(file)
                        elif file.endswith('.skipped'):
                            skipped_files.append(file)

                status['file_counts'] = {
                    'total_xml': len(xml_files),
                    'processed': len(processed_files),
                    'skipped': len(skipped_files)
                }
            except Exception as e:
                logger.error(f"Error counting files: {e}")

        return status

    def parse_transaction(self, raw_data: Any) -> Optional[Dict[str, Any]]:
        """
        Parse raw transaction data into standardized format.

        For TCPOS, raw_data is expected to be a file path to an XML file.

        Args:
            raw_data: Path to XML transaction file (str)

        Returns:
            dict: Standardized transaction dict, or None if parse fails
        """
        if not isinstance(raw_data, str):
            logger.error(f"Expected file path (str), got {type(raw_data)}")
            return None

        if not os.path.exists(raw_data):
            logger.error(f"Transaction file does not exist: {raw_data}")
            return None

        try:
            # Parse the XML file
            items, payments, service_charge, tips, trans_num, is_credit_note, discount, comment, customer = tcpos_parse_transaction(raw_data)

            if not items or not payments:
                logger.warning(f"Failed to parse transaction from {raw_data}")
                return None

            # Convert to standardized format
            transaction = {
                "items": items,
                "payments": payments,
                "service_charge": service_charge,
                "tips": tips,
                "trans_num": trans_num,
                "is_credit_note": is_credit_note,
                "discount": discount,
                "comment": comment,
                "customer": customer,
                "source_file": raw_data,
                "parsed_at": datetime.now().isoformat()
            }

            self.last_file_processed = os.path.basename(raw_data)
            self.last_scan_time = datetime.now()

            return transaction

        except Exception as e:
            logger.error(f"Error parsing transaction from {raw_data}: {e}")
            self.error_log.append({
                "timestamp": datetime.now(),
                "file": raw_data,
                "error": str(e)
            })
            return None

    def get_name(self) -> str:
        """
        Get the software integration name.

        Returns:
            str: "tcpos"
        """
        return "tcpos"

    def __repr__(self) -> str:
        """String representation of the integration."""
        folder = self.config.get('transactions_folder', 'N/A')
        return f"<TCPOSIntegration (tcpos) running={self.running} folder={folder}>"
