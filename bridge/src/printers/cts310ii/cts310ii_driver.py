"""
CTS310ii Fiscal Printer Driver

This module implements the BasePrinter interface for the CTS310ii fiscal printer.
It merges functionality from both Odoo and TCPOS versions with bug fixes and enhancements.

Based on the protocol specification: MHI_Programacion_CW_(EN).pdf
"""

import os
import serial
import serial.tools.list_ports
import time
import datetime
import json
from typing import Dict, Any, List, Optional

from ..base_printer import BasePrinter
from .protocol import *

# Import logger and fiscal utilities from parent directory
import sys
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from logger_module import logger
    from core.fiscal_utils import generate_nkf
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    # Try alternative import path for fiscal_utils
    try:
        from core.fiscal_utils import generate_nkf
    except ImportError:
        logger.error("Failed to import fiscal_utils - NKF generation will not work")
        def generate_nkf(*args, **kwargs):
            return "1234567890123456789"  # Fallback


# =============================================================================
# UTILITY FUNCTIONS (module-level helpers)
# =============================================================================

def convert_to_tax(string: str) -> float:
    """Convert tax string from printer format to float.

    Args:
        string: Tax rate string (e.g., "0600" for 6.00%)

    Returns:
        float: Tax rate as float (e.g., 6.00)

    Examples:
        >>> convert_to_tax("0600")
        6.0
        >>> convert_to_tax("0750")
        7.5
    """
    return float(string[0:2] + "." + string[2:4])


def string_to_hex(string: str) -> str:
    """Convert string to hex representation.

    Args:
        string: String to convert

    Returns:
        str: Hex representation of the string
    """
    return string.encode("utf-8").hex()


def dict_values_to_hex(dictionary: Dict[str, str]) -> Dict[str, str]:
    """Convert all values in a dictionary to hex representation.

    Args:
        dictionary: Dictionary with string values

    Returns:
        dict: Dictionary with hex-encoded values
    """
    for key, value in dictionary.items():
        dictionary[key] = string_to_hex(value)
    return dictionary


def hex_to_string(hex_string: str) -> str:
    """Convert hex string to ASCII string.

    Args:
        hex_string: Hex representation of a string

    Returns:
        str: Decoded ASCII string
    """
    return bytes.fromhex(hex_string).decode('ascii')


def string_number_to_number(string: str, decimals: int = 0) -> float:
    """Convert a string number to a float number.

    Args:
        string: The string number to convert
        decimals: The number of decimal places

    Returns:
        float: The converted float number

    Examples:
        >>> string_number_to_number("8000")
        8.0
        >>> string_number_to_number("8000", decimals=2)
        80.0
        >>> string_number_to_number("8000", decimals=3)
        8.0
    """
    length = len(string) - decimals
    integer = string[:length]
    decimal = string[length:]
    return float(integer + "." + decimal)


def hex_cmd_to_bytes(hex_cmd: str) -> Optional[bytearray]:
    """Convert hex command string to bytes.

    Args:
        hex_cmd: Hex command string

    Returns:
        bytearray: Command as bytes, or None if conversion fails
    """
    try:
        if len(hex_cmd) % 2 == 0:
            return bytearray.fromhex(hex_cmd)
    except Exception as e:
        logger.error(f"Error while converting command to bytes: {e}")
        return None


def split_comment_into_lines(comment: str, max_chars: int = 48) -> List[str]:
    """Split a long comment into multiple lines of max_chars length.

    Splits on word boundaries to avoid breaking mid-word.

    Args:
        comment: Comment text to split
        max_chars: Maximum characters per line (default: 48)

    Returns:
        list: List of strings, each max_chars long
    """
    if not comment or not comment.strip():
        return []

    words = comment.strip().split()
    lines = []
    current_line = ""

    for word in words:
        # Check if adding this word would exceed max_chars
        if current_line and len(current_line) + 1 + len(word) <= max_chars:
            current_line += " " + word
        elif not current_line and len(word) <= max_chars:
            current_line = word
        elif not current_line and len(word) > max_chars:
            # Single word is too long, split it forcefully
            current_line = word[:max_chars]
            words.insert(words.index(word) + 1, word[max_chars:])
        else:
            # Current line is full, start a new one
            lines.append(current_line)
            current_line = word

    # Add the last line if not empty
    if current_line:
        lines.append(current_line)

    return lines


# =============================================================================
# MAIN DRIVER CLASS
# =============================================================================

class CTS310iiDriver(BasePrinter):
    """
    CTS310ii Fiscal Printer Driver.

    Implements the BasePrinter interface for CTS310ii fiscal printers.
    Supports fiscal document printing, X/Z reports, and document management.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the CTS310ii driver.

        Args:
            config: Printer-specific config dict containing:
                - baud_rate: Serial baud rate (default: 9600)
                - serial_timeout: Serial timeout in seconds (default: 5)
                - debug: Debug mode flag (default: False)
                - client: Client fiscal information (NKF, etc.)
                - miscellaneous: Default customer info
        """
        super().__init__(config)

        # Extract configuration
        self.baud_rate = config.get('baud_rate', DEFAULT_BAUD_RATE)
        self.serial_timeout = config.get('serial_timeout', DEFAULT_SERIAL_TIMEOUT)
        self.debug = config.get('debug', False)

        # Client and customer defaults
        self.client_config = config.get('client', {})
        self.misc_config = config.get('miscellaneous', {})

        logger.info(f"CTS310ii driver initialized (debug={self.debug})")

    def get_name(self) -> str:
        """Get printer driver name."""
        return "cts310ii"

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    def connect(self) -> bool:
        """Detect and connect to the printer.

        Smart connection: First tries configured COM port, then auto-detects if needed.

        Returns:
            bool: True if connected successfully
        """
        try:
            if self.debug:
                logger.debug("DEBUG mode enabled - skipping printer detection")
                self.connected = True
                self.com_port = "DEBUG"
                return True

            # Get configured COM port from printer config
            configured_port = self.config.get('printer', {}).get('cts310ii', {}).get('com_port')

            # Try configured port first if specified and not null
            if configured_port and configured_port.upper() not in ['AUTO', 'NULL', 'NONE']:
                logger.info(f"Trying configured COM port: {configured_port}")
                self.com_port = configured_port

                # Send identification command (0x21)
                code = "21"
                cmd = f"{STX}{code}{ETX}"
                response = self._send_to_serial(cmd)

                if self._is_success_response(response):
                    logger.info(f"Found CTS310ii printer on configured port {self.com_port}")
                    self.connected = True

                    # Synchronize datetime
                    self._sync_datetime()

                    # Get and log fiscal information
                    self._log_fiscal_info()

                    return True
                else:
                    logger.warning(f"Configured port {configured_port} did not respond, falling back to auto-detection")

            # Auto-detect: Scan all COM ports
            logger.info("Scanning for CTS310ii printer...")
            ports = serial.tools.list_ports.comports()

            if len(ports) == 0:
                logger.error("No COM ports found")
                return False

            # Try ports in reverse order
            for port in reversed(ports):
                # Skip if we already tried this port as the configured one
                if configured_port and port.name == configured_port:
                    continue

                self.com_port = port.name
                logger.debug(f"Checking {self.com_port}...")

                # Send identification command (0x21)
                code = "21"
                cmd = f"{STX}{code}{ETX}"
                response = self._send_to_serial(cmd)

                if self._is_success_response(response):
                    logger.info(f"Found CTS310ii printer on {self.com_port}")
                    self.connected = True

                    # Synchronize datetime
                    self._sync_datetime()

                    # Get and log fiscal information
                    self._log_fiscal_info()

                    return True

            logger.error("CTS310ii printer not found on any COM port")
            return False

        except Exception as e:
            logger.error(f"Error connecting to printer: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from the printer.

        Returns:
            bool: True if disconnected successfully
        """
        self.connected = False
        self.com_port = None
        logger.info("Disconnected from printer")
        return True

    # =========================================================================
    # SERIAL COMMUNICATION (private methods)
    # =========================================================================

    def _send_to_serial(self, hex_cmd: str, wait_for_response: bool = True) -> Optional[str]:
        """Send command to printer via serial port.

        Args:
            hex_cmd: Command in hex format
            wait_for_response: Whether to wait for response

        Returns:
            str: Response in hex format, or None on error
        """
        try:
            if self.debug:
                logger.debug("DEBUG mode - returning mock response")
                return f"{STX}{ETX}{ACK}"

            # Convert command to bytes
            bytes_cmd = hex_cmd_to_bytes(hex_cmd)
            if bytes_cmd is None:
                return None

            # Send command
            ser = serial.Serial(self.com_port, self.baud_rate)
            ser.timeout = 3.0
            ser.write(bytes_cmd)

            if not wait_for_response:
                ser.close()
                return None

            # Wait for response
            et = time.time() + self.serial_timeout
            data = ""
            while time.time() < et:
                data += ser.read(1).hex()
                if data.endswith(ETX + ACK) or data.endswith(NAK) or data.endswith(ACK):
                    break

            ser.close()
            logger.debug(f"Response length: {len(data)}")
            logger.debug(f"Response: {data}")
            return data

        except Exception as e:
            logger.error(f"Serial communication error: {e}")
            return None

    def _is_success_response(self, data: Optional[str]) -> bool:
        """Check if response indicates success.

        Args:
            data: Response data in hex format

        Returns:
            bool: True if response indicates success
        """
        # Handle None response (TCPOS bug fix)
        if data is None:
            return False

        # Check for various success patterns
        if data.startswith(STX) and data.endswith(ETX + ACK):
            return True
        if data.startswith(BEL) and data.endswith(ETX + ACK):
            return True
        if data.endswith(ACK):  # Standalone ACK (from Odoo version)
            return True

        return False

    # =========================================================================
    # PRINTER STATE & STATUS
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get printer status.

        Returns:
            dict: Status information including connection, state, paper, errors
        """
        if not self.connected:
            return {
                "connected": False,
                "com_port": None,
                "error": "Not connected"
            }

        try:
            # Get printer state
            state_info = self._get_printer_state()

            # Get printer status
            status_info = self._get_printer_status()

            return {
                "connected": True,
                "com_port": self.com_port,
                "state": state_info.get("state_description", "Unknown") if state_info else "Unknown",
                "state_code": state_info.get("state_code", "?") if state_info else "?",
                "response_code": state_info.get("response_code", "?") if state_info else "?",
                "paper_low": status_info.get("end_of_paper_sensor") == "NO_PAPER" if status_info else False,
                "cover_open": status_info.get("cover") == "OPEN" if status_info else False,
                "online": status_info.get("online", False) if status_info else False,
                "error": None
            }

        except Exception as e:
            logger.error(f"Error getting printer status: {e}")
            return {
                "connected": self.connected,
                "com_port": self.com_port,
                "error": str(e)
            }

    def _get_printer_state(self) -> Optional[Dict[str, Any]]:
        """Get printer state (internal method).

        Returns:
            dict: Printer state information
        """
        try:
            code = "20"
            cmd = f"{STX}{code}{ETX}"
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                return self._decode_printer_state(response)

            logger.error(f"Failed to get printer state, response: {response}")
            return None

        except Exception as e:
            logger.error(f"Error getting printer state: {e}")
            return None

    def _get_printer_status(self) -> Optional[Dict[str, Any]]:
        """Get printer hardware status (internal method).

        Returns:
            dict: Printer hardware status
        """
        try:
            code = "3F"
            cmd = f"{STX}{code}{ETX}"
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                return self._decode_printer_status(response)

            logger.error(f"Failed to get printer status, response: {response}")
            return None

        except Exception as e:
            logger.error(f"Error getting printer status: {e}")
            return None

    # =========================================================================
    # RESPONSE DECODERS (private methods)
    # =========================================================================

    def _decode_printer_datetime(self, data: str) -> Optional[datetime.datetime]:
        """Decode printer datetime response."""
        try:
            data = data.upper()[2:-4]  # Remove STX and ETX+ACK
            fields = data.split(FS)
            date = hex_to_string(fields[0])  # DDMMYYYY
            time = hex_to_string(fields[1])  # HHMMSS
            return datetime.datetime.strptime(date + time, '%d%m%Y%H%M%S')
        except Exception as e:
            logger.error(f"Error decoding printer datetime: {e}")
            return None

    def _decode_fiscal_information(self, data: str) -> Optional[Dict[str, Any]]:
        """Decode fiscal information response."""
        try:
            data = data[2:-4].upper()  # Remove STX and ETX+ACK
            fields = data.split(FS)
            return {
                "CRIB": hex_to_string(fields[0]),
                "business_name": hex_to_string(fields[1]),
                "phone_number": hex_to_string(fields[2]),
                "address1": hex_to_string(fields[3]),
                "address2": hex_to_string(fields[4]),
                "tax1": convert_to_tax(hex_to_string(fields[5])),
                "tax2": convert_to_tax(hex_to_string(fields[6])),
                "tax3": convert_to_tax(hex_to_string(fields[7])),
                "tax4": convert_to_tax(hex_to_string(fields[8])),
                "tax5": convert_to_tax(hex_to_string(fields[9])),
                "tax6": convert_to_tax(hex_to_string(fields[10])),
                "tax7": convert_to_tax(hex_to_string(fields[11])),
                "tax8": convert_to_tax(hex_to_string(fields[12])),
                "tax9": convert_to_tax(hex_to_string(fields[13])),
                "tax10": convert_to_tax(hex_to_string(fields[14])),
            }
        except Exception as e:
            logger.error(f"Error decoding fiscal information: {e}")
            return None

    def _decode_printer_status(self, data: str) -> Optional[Dict[str, Any]]:
        """Decode printer status response."""
        try:
            data = data[2:-4].upper()  # Remove STX and ETX+ACK
            bits = bin(int(data, 16))[2:].zfill(32)
            return {
                "online": True if bits[0] == "0" else False,
                "cover": "OK" if bits[1] == "0" else "OPEN",
                "temperature": "OK" if bits[2] == "0" else "HIGH",
                "non_recoverable_error": "OK" if bits[3] == "0" else "ERROR",
                "paper_cutter": "OK" if bits[4] == "0" else "ERROR",
                "buffer_overflow": "OK" if bits[5] == "0" else "ERROR",
                "end_of_paper_sensor": "OK" if bits[6] == "0" else "NO_PAPER",
                "out_of_paper_sensor": "OK" if bits[7] == "0" else "NO_PAPER",
                "station_TOF_detection": "OK" if bits[16] == "0" else "NO_PAPER",
                "station_COF_error": "OK" if bits[17] == "0" else "NO_PAPER",
                "station_BOF_detection": "OK" if bits[18] == "0" else "NO_PAPER",
            }
        except Exception as e:
            logger.error(f"Error decoding printer status: {e}")
            return None

    def _decode_printer_state(self, data: str) -> Optional[Dict[str, Any]]:
        """Decode printer state response."""
        try:
            data = data[2:-4].upper()  # Remove STX and ETX+ACK
            fields = data.split(FS)

            response_code = hex(int(hex_to_string(fields[0])))[2:].zfill(4)
            state_code = hex_to_string(fields[1])

            return {
                "response_code": response_code,
                "response_description": response_codes.get(response_code, "unknown_response_code"),
                "state_code": state_code,
                "state_description": states_codes.get(state_code, "unknown_state_code"),
                "fiscal_status": fields[2],
            }
        except Exception as e:
            logger.error(f"Error decoding printer state: {e}")
            return None

    def _decode_document_number(self, data: str) -> Optional[str]:
        """Decode document number response."""
        try:
            data = data[2:-4].upper()  # Remove STX and ETX+ACK
            fields = data.split(FS)
            return hex_to_string(fields[0])
        except Exception as e:
            logger.error(f"Error decoding document number: {e}")
            return None

    def _decode_sub_or_total_response(self, data: str) -> Optional[Dict[str, Any]]:
        """Decode subtotal/total response."""
        try:
            data = data[2:-4].upper()  # Remove STX and ETX+ACK
            fields = data.split(FS)

            result = {
                "total_exempt": string_number_to_number(hex_to_string(fields[0]), decimals=2),
                "total_sale_tax_1": string_number_to_number(hex_to_string(fields[1]), decimals=2),
                "total_tax_1": string_number_to_number(hex_to_string(fields[2]), decimals=2),
                "total_sale_tax_2": string_number_to_number(hex_to_string(fields[3]), decimals=2),
                "total_tax_2": string_number_to_number(hex_to_string(fields[4]), decimals=2),
                "total_sale_tax_3": string_number_to_number(hex_to_string(fields[5]), decimals=2),
                "total_tax_3": string_number_to_number(hex_to_string(fields[6]), decimals=2),
                "total_sale_tax_4": string_number_to_number(hex_to_string(fields[7]), decimals=2),
                "total_tax_4": string_number_to_number(hex_to_string(fields[8]), decimals=2),
                "total_sale_tax_5": string_number_to_number(hex_to_string(fields[9]), decimals=2),
                "total_tax_5": string_number_to_number(hex_to_string(fields[10]), decimals=2),
                "total_sale_tax_6": string_number_to_number(hex_to_string(fields[11]), decimals=2),
                "total_tax_6": string_number_to_number(hex_to_string(fields[12]), decimals=2),
                "total_sale_tax_7": string_number_to_number(hex_to_string(fields[13]), decimals=2),
                "total_tax_7": string_number_to_number(hex_to_string(fields[14]), decimals=2),
                "total_sale_tax_8": string_number_to_number(hex_to_string(fields[15]), decimals=2),
                "total_tax_8": string_number_to_number(hex_to_string(fields[16]), decimals=2),
                "total_sale_tax_9": string_number_to_number(hex_to_string(fields[17]), decimals=2),
                "total_tax_9": string_number_to_number(hex_to_string(fields[18]), decimals=2),
                "total_sale_tax_10": string_number_to_number(hex_to_string(fields[19]), decimals=2),
                "total_tax_10": string_number_to_number(hex_to_string(fields[20]), decimals=2),
                "document_total": string_number_to_number(hex_to_string(fields[21]), decimals=2),
                "item_quantity": string_number_to_number(hex_to_string(fields[22])),
            }

            logger.debug(json.dumps(result, indent=4))
            return result

        except Exception as e:
            logger.error(f"Error decoding sub/total response: {e}")
            return None

    # =========================================================================
    # DATETIME SYNCHRONIZATION (private)
    # =========================================================================

    def _sync_datetime(self) -> bool:
        """Synchronize printer datetime with system time.

        Returns:
            bool: True if synchronized successfully
        """
        try:
            # Get printer datetime
            code = "24"
            cmd = f"{STX}{code}{ETX}"
            response = self._send_to_serial(cmd)

            if not self._is_success_response(response):
                logger.error("Failed to get printer datetime")
                return False

            printer_datetime = self._decode_printer_datetime(response)
            if not printer_datetime:
                return False

            # Check if synchronization is needed (2 minute threshold)
            now = datetime.datetime.now()
            delta = abs((printer_datetime - now).total_seconds())

            if delta > 120:
                logger.info(f"Printer datetime differs by {delta}s - synchronizing")
                logger.debug(f"System: {now}, Printer: {printer_datetime}")

                # Set printer datetime
                date = string_to_hex(now.strftime("%d%m%Y"))
                time_hex = string_to_hex(now.strftime("%H%M%S"))
                code = "23"
                cmd = f"{STX}{code}{FS}{date}{FS}{time_hex}{ETX}"
                response = self._send_to_serial(cmd)

                if response == ACK:
                    logger.info("Printer datetime synchronized")
                    return True
                else:
                    logger.error("Failed to synchronize printer datetime")
                    return False
            else:
                logger.debug("Printer datetime is already synchronized")
                return True

        except Exception as e:
            logger.error(f"Error synchronizing datetime: {e}")
            return False

    def _log_fiscal_info(self):
        """Log fiscal information from the printer."""
        try:
            code = "26"
            cmd = f"{STX}{code}{ETX}"
            response = self._send_to_serial(cmd)

            if not self._is_success_response(response):
                logger.error("Failed to get fiscal information")
                return

            fiscal_info = self._decode_fiscal_information(response)
            if not fiscal_info:
                return

            # Log key information
            logger.info(f"CRIB: {fiscal_info['CRIB']}")
            logger.info(f"Business: {fiscal_info['business_name']}")
            logger.info(f"Phone: {fiscal_info['phone_number']}")
            logger.info(f"Address: {fiscal_info['address1']}")

            # Check for unconfigured fields
            for field in ['CRIB', 'business_name', 'phone_number', 'address1']:
                if fiscal_info[field].startswith("?"):
                    logger.warning(f"Printer {field} is not configured!")

        except Exception as e:
            logger.error(f"Error logging fiscal info: {e}")

    # =========================================================================
    # DOCUMENT OPERATIONS (private)
    # =========================================================================

    def _cancel_document(self, reason: str = "Completed operation") -> bool:
        """Cancel the current document.

        Args:
            reason: Reason for cancellation

        Returns:
            bool: True if cancelled successfully
        """
        try:
            code = "46"
            cmd = f"{STX}{code}{ETX}"
            response = self._send_to_serial(cmd)

            # Handle None response (TCPOS bug fix)
            if response is None:
                logger.warning(f"No response for cancel_document, reason: {reason}")
                return False

            if response == f"0707{ACK}":
                logger.debug(f"Document cancelled: {reason}")
                return True

            # NAK response means no document to cancel (TCPOS bug fix)
            if response == NAK or response == "15":
                logger.debug("No document to cancel (printer in standby)")
                return True

            logger.error(f"Failed to cancel document, response: {response}")
            return False

        except Exception as e:
            logger.error(f"Error cancelling document: {e}")
            return False

    def _prepare_document(self, fiscal_object: Dict[str, str]) -> Optional[str]:
        """Prepare a new fiscal document.

        Args:
            fiscal_object: Document parameters (type, branch, POS, customer, etc.)

        Returns:
            str: Document number, or None on error
        """
        try:
            code = "40"

            # Build command with fields in the protocol-required order
            # For doc types 1&3, send empty customer_CRIB (not omit it)
            cmd = f"{STX}{code}{FS}"
            cmd += string_to_hex(fiscal_object["type"]) + FS
            cmd += string_to_hex(fiscal_object["branch"]) + FS
            cmd += string_to_hex(fiscal_object["POS"]) + FS
            cmd += string_to_hex(fiscal_object["customer_name"]) + FS

            # Always include customer_CRIB field position
            # For types 1&3: send empty string (zero-length field)
            # For types 2&4: send actual CRIB value
            if "customer_CRIB" in fiscal_object:
                cmd += string_to_hex(fiscal_object["customer_CRIB"]) + FS
            else:
                # Send empty field (just FS separator, no content between)
                cmd += FS

            cmd += string_to_hex(fiscal_object["NKF"]) + FS
            cmd += string_to_hex(fiscal_object["NKF_affected"]) + FS

            # Remove last FS
            cmd = cmd[:-2] + ETX

            logger.debug(f"Prepare document command: {cmd}")
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                document_number = self._decode_document_number(response)
                logger.info(f"Document prepared: {document_number}")
                return document_number

            logger.error(f"Failed to prepare document, response: {response}")
            state = self._get_printer_state()
            if state:
                logger.debug(json.dumps(state, indent=4))

            return None

        except Exception as e:
            logger.error(f"Error preparing document: {e}")
            return None

    def _add_item_to_document(self, item: Dict[str, str]) -> bool:
        """Add item to current document.

        Args:
            item: Item parameters (type, description, quantity, price, tax, etc.)

        Returns:
            bool: True if added successfully
        """
        try:
            code = "41"
            a = dict_values_to_hex(item)

            cmd = f"{STX}{code}{FS}"
            for k, v in a.items():
                cmd += f"{v}{FS}"

            # Remove last FS and add required trailing fields
            cmd = cmd[:-2] + "1C321C32" + ETX

            logger.debug(f"Add item command: {cmd}")
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                logger.debug("Item added successfully")
                return True

            logger.error(f"Failed to add item, response: {response}")
            state = self._get_printer_state()
            if state:
                logger.debug(json.dumps(state, indent=4))

            return False

        except Exception as e:
            logger.error(f"Error adding item: {e}")
            return False

    def _document_sub_or_total(self, doc_type: str) -> Optional[Dict[str, Any]]:
        """Calculate document subtotal or total.

        Args:
            doc_type: "0" for subtotal, "1" for total (NOT hex encoded)

        Returns:
            dict: Totals information, or None on error
        """
        try:
            code = "42"
            cmd = f"{STX}{code}{FS}{string_to_hex(doc_type)}{ETX}"
            logger.debug(f"Subtotal/total command: {cmd}")

            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                type_str = "subtotal" if doc_type == "0" else "total"
                logger.debug(f"Document {type_str} calculated")
                return self._decode_sub_or_total_response(response)

            logger.error(f"Failed to calculate {doc_type}, response: {response}")
            state = self._get_printer_state()
            if state:
                logger.debug(json.dumps(state, indent=4))

            return None

        except Exception as e:
            logger.error(f"Error calculating subtotal/total: {e}")
            return None

    def _discount_surcharge_service(self, data: Dict[str, str]) -> bool:
        """Apply discount, surcharge, or service charge.

        Args:
            data: Discount/surcharge parameters (type, description, amount, percent)

        Returns:
            bool: True if applied successfully
        """
        try:
            code = "43"
            a = dict_values_to_hex(data)

            cmd = f"{STX}{code}{FS}"
            for k, v in a.items():
                cmd += f"{v}{FS}"

            # Remove last FS
            cmd = cmd[:-2] + ETX

            logger.info(f"Discount/surcharge data: {json.dumps(data, indent=2)}")
            logger.debug(f"Command: {cmd}")

            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                logger.debug("Discount/surcharge applied")
                return True

            logger.error(f"Failed to apply discount/surcharge, response: {response}")
            state = self._get_printer_state()
            if state:
                logger.debug(json.dumps(state, indent=4))

            return False

        except Exception as e:
            logger.error(f"Error applying discount/surcharge: {e}")
            return False

    def _payment(self, data: Dict[str, str]) -> bool:
        """Process payment.

        Args:
            data: Payment parameters (type, method, description, amount)

        Returns:
            bool: True if processed successfully
        """
        try:
            code = "44"
            a = dict_values_to_hex(data)

            cmd = f"{STX}{code}{FS}"
            for k, v in a.items():
                cmd += f"{v}{FS}"

            # Remove last FS
            cmd = cmd[:-2] + ETX

            logger.debug(f"Payment command: {cmd}")
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                logger.debug("Payment processed")
                return True

            logger.error(f"Failed to process payment, response: {response}")
            state = self._get_printer_state()
            if state:
                logger.debug(json.dumps(state, indent=4))

            return False

        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            return False

    def _add_comment(self, comment: str) -> bool:
        """Add comment line to document.

        Args:
            comment: Comment text

        Returns:
            bool: True if added successfully
        """
        try:
            text_hex = string_to_hex(comment)
            code = "4A"
            cmd = f"{STX}{code}{FS}{text_hex}{ETX}"

            logger.debug(f"Adding comment: {comment}")
            response = self._send_to_serial(cmd)

            # Handle None response (Odoo bug fix)
            if response is None:
                logger.warning(f"No response for add_comment: {comment}")
                return False

            # Check for success - both full response and standalone ACK (TCPOS bug fix)
            if self._is_success_response(response) or response == ACK:
                logger.debug("Comment added")
                return True

            logger.error(f"Failed to add comment, response: {response}")
            return False

        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return False

    def _close_document(self, reason: str = "Completed operation") -> Optional[str]:
        """Close the current document.

        Args:
            reason: Reason for closing

        Returns:
            str: Response data, or None on error
        """
        try:
            code = "45"
            cmd = f"{STX}{code}{ETX}"

            logger.debug(f"Close document command: {cmd}")
            response = self._send_to_serial(cmd)
            logger.debug(f"Close document response: {response}")

            if self._is_success_response(response):
                logger.info(f"Document closed: {reason}")
                return response

            # If close failed, try to cancel
            logger.error(f"Failed to close document, response: {response}")
            state = self._get_printer_state()
            if state:
                logger.debug(json.dumps(state, indent=4))

            if self._cancel_document(f"Cancelled due to close error: {reason}"):
                logger.debug("Document cancelled after close error")

            return None

        except Exception as e:
            logger.error(f"Error closing document: {e}")
            return None

    # =========================================================================
    # PUBLIC API METHODS (BasePrinter interface)
    # =========================================================================

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
        """Print a fiscal receipt document.

        This merges functionality from both Odoo and TCPOS versions.

        Args:
            items: List of item dicts
            payments: List of payment dicts
            service_charge: Service charge dict
            tips: List of tip dicts
            discount: Transaction-level discount
            surcharge: Transaction-level surcharge
            general_comment: Footer comment
            is_refund: True if refund/credit note
            receipt_number: Display receipt number
            pos_name: POS terminal name
            customer_name: Customer name
            customer_crib: Customer tax ID

        Returns:
            dict: {"success": bool, "error": str, "document_number": str}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            # Get default customer info
            default_customer_name = self.misc_config.get("default_client_name", "Regular client")
            default_customer_crib = self.misc_config.get("default_client_crib", "1000000000")

            # Determine if customer is present
            has_customer = (
                customer_name and
                customer_crib and
                customer_name != default_customer_name
            )

            # Use customer info or defaults
            final_customer_name = customer_name if customer_name else default_customer_name
            final_customer_crib = customer_crib if customer_crib else default_customer_crib

            # Ensure CRIB is exactly 10 digits
            if final_customer_crib:
                final_customer_crib = str(final_customer_crib).zfill(10)

            # Document type intelligence (from Odoo version)
            # Type 1 (Invoice Final Consumer) → Type 2 (Invoice Fiscal Credit) when customer present
            # Type 3 (Credit Note Final Consumer) → Type 4 (Credit Note Fiscal) when customer present
            if has_customer:
                doc_type = "4" if is_refund else "2"
                logger.info(f"Customer present - using document type {doc_type}")
            else:
                doc_type = "3" if is_refund else "1"

            # Generate dynamic NKF
            nkf_config = self.client_config.get("NKF", {})

            # Extract sequential number from receipt_number (last 6 digits of Odoo receipt ID)
            sequential_number = 0
            if receipt_number:
                # Extract numeric digits from receipt_number and take last 6
                receipt_digits = ''.join(filter(str.isdigit, str(receipt_number)))
                if receipt_digits:
                    sequential_number = int(receipt_digits[-6:]) if len(receipt_digits) >= 6 else int(receipt_digits)

            # Generate NKF using fiscal_utils
            client_nkf = generate_nkf(nkf_config, doc_type, sequential_number)
            logger.info(f"Generated NKF: {client_nkf} (type={doc_type}, receipt={receipt_number}, sequential={sequential_number})")

            # Prepare fiscal object
            # For doc types 1 and 3 (final consumer), use minimal customer info
            # For doc types 2 and 4 (with customer), use actual customer info
            if doc_type in ["1", "3"]:
                # Final consumer - use default/minimal customer data
                # Try empty string to suppress CRIB NUMBER line on printer
                fiscal_customer_name = default_customer_name
                fiscal_customer_crib = ""  # Empty string to suppress CRIB NUMBER/ID CONSUMER line
            else:
                # Types 2 and 4 - use actual customer data
                fiscal_customer_name = final_customer_name
                fiscal_customer_crib = final_customer_crib

            # Build fiscal object - only include customer_CRIB for doc types 2 and 4
            fiscal_object = {
                "type": doc_type,
                "branch": "9001",
                "POS": receipt_number if receipt_number else "1001",
                "customer_name": fiscal_customer_name,
                "NKF": client_nkf,
                "NKF_affected": client_nkf,
            }

            # Only add customer_CRIB for fiscal credit documents (types 2 and 4)
            # Omitting it entirely for types 1 and 3 prevents the line from printing
            if doc_type in ["2", "4"]:
                fiscal_object["customer_CRIB"] = fiscal_customer_crib

            # Cancel any previous document
            self._cancel_document()

            # Prepare document
            document_number = self._prepare_document(fiscal_object)
            if not document_number:
                return {"success": False, "error": "Failed to prepare document"}

            # Add customer details for doc types 2 and 4 only
            # Types 1 and 3 (final consumer) don't show customer details
            if doc_type in ["2", "4"] and has_customer:
                # Use the actual customer info stored in final_customer_name/crib
                result = self._add_comment(f"Customer: {final_customer_name}")
                if not result:
                    logger.warning("Failed to add customer name comment (non-critical)")

                result = self._add_comment(f"CRIB: {final_customer_crib}")
                if not result:
                    logger.warning("Failed to add CRIB comment (non-critical)")

            # Add items
            for item in items:
                # Hide article number on printout (from TCPOS)
                item['product_code'] = " "

                # Check for item-level percentage discount and add info to description
                if 'discount_percent' in item:
                    try:
                        discount_pct = float(item.get('discount_percent', 0))
                        if discount_pct > 0:
                            original_desc = item.get('item_description', 'Item')
                            item['item_description'] = f"[Discount of {discount_pct:.0f}% applied] {original_desc}"
                    except (ValueError, TypeError):
                        pass  # Ignore if discount_percent is not a valid number

                if not self._add_item_to_document(item):
                    self._cancel_document("Failed to add item")
                    return {"success": False, "error": "Failed to add item to document"}

            # Apply service charge if present
            if service_charge:
                if not self._discount_surcharge_service(service_charge):
                    logger.warning("Failed to apply service charge")

            # Calculate subtotal
            subtotal = self._document_sub_or_total("0")
            if not subtotal:
                self._cancel_document("Failed to calculate subtotal")
                return {"success": False, "error": "Failed to calculate subtotal"}

            # Apply discount at subtotal level (from TCPOS)
            if discount:
                if self._discount_surcharge_service(discount):
                    logger.info(f"Applied discount: {discount.get('description', 'N/A')}")
                else:
                    logger.warning("Failed to apply discount")

            # Apply surcharge if present
            if surcharge:
                if self._discount_surcharge_service(surcharge):
                    logger.info(f"Applied surcharge: {surcharge.get('description', 'N/A')}")
                else:
                    logger.warning("Failed to apply surcharge")

            # Calculate total
            total = self._document_sub_or_total("1")
            if not total:
                self._cancel_document("Failed to calculate total")
                return {"success": False, "error": "Failed to calculate total"}

            # Process payments
            for pay in payments:
                if not self._payment(pay):
                    self._cancel_document("Failed to process payment")
                    return {"success": False, "error": "Failed to process payment"}

            # Process tips
            if tips:
                for tip in tips:
                    if not self._payment(tip):
                        logger.warning("Failed to process tip")

            # Add footer info (Receipt ID, POS, Cash Register, Document Nr) after payments, before close
            if has_customer:
                self._add_comment("================================================")
                self._add_comment(f"CUSTOMER: {final_customer_name}")
                self._add_comment(f"CRIB: {final_customer_crib}")
                self._add_comment("================================================")

            if receipt_number:
                self._add_comment(f"Receipt ID: {receipt_number}")
            if pos_name:
                # Display as "Operator: 1701" if operator code, otherwise "POS: [name]"
                if pos_name.startswith("Operator:"):
                    self._add_comment(pos_name)
                else:
                    self._add_comment(f"POS: {pos_name}")

            # Add cash register info
            cash_register = nkf_config.get("cash_register", "")
            if cash_register:
                self._add_comment(f"Cash Register: {cash_register}")

            self._add_comment(f"Document Nr: {document_number}")

            # Add general comment if present
            if general_comment:
                self._add_comment("------------------------------------------------")
                self._add_comment("Customer note:")
                comment_lines = split_comment_into_lines(general_comment, 48)
                for line in comment_lines:
                    self._add_comment(line)
                self._add_comment("------------------------------------------------")

            # Close document
            close_response = self._close_document()
            if not close_response:
                return {"success": False, "error": "Failed to close document"}

            logger.info(f"Document printed successfully: {document_number}")
            return {
                "success": True,
                "document_number": document_number
            }

        except Exception as e:
            logger.error(f"Error printing document: {e}")
            self._cancel_document("Exception during print")
            return {"success": False, "error": str(e)}

    def print_x_report(self) -> Dict[str, Any]:
        """Print X report (non-fiscal daily report).

        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            logger.info("Generating X Report")
            code = "71"
            cmd = f"{STX}{code}{ETX}"
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                logger.info("X Report printed successfully")
                return {"success": True}

            # NAK response usually means no transactions to report
            error_msg = "Printer rejected X-Report (NAK response)"
            if response == "15":
                error_msg += " - Likely no transactions to report or fiscal day already closed"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"Exception during X Report: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report(self, close_fiscal_day: bool = True) -> Dict[str, Any]:
        """Print Z report (fiscal day closing).

        Args:
            close_fiscal_day: Whether to close the fiscal day (default: True)
                             If False, prints a copy without closing

        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            action = "closing fiscal period" if close_fiscal_day else "printing copy"
            logger.info(f"Generating Z Report ({action})")

            code = "70"
            param_value = "1" if close_fiscal_day else "0"
            param = string_to_hex(param_value)
            cmd = f"{STX}{code}{FS}{param}{ETX}"
            response = self._send_to_serial(cmd)

            if response is None:
                error_msg = "Failed to print Z Report - No response from printer"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            if self._is_success_response(response):
                logger.info(f"Z Report printed successfully ({action})")
                return {"success": True}

            # Provide helpful error message
            error_msg = "Failed to print Z Report"
            if response == NAK or response == "15":
                error_msg += " - No transactions to report or fiscal day already closed"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"Exception during Z Report: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report_by_date(self, start_date, end_date=None) -> Dict[str, Any]:
        """Print Z reports for a date range.

        Args:
            start_date: Start date (datetime.date object)
            end_date: End date (defaults to today if not provided)

        Returns:
            dict: {"success": bool, "error": str, "message": str, "reports_count": int}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            if end_date is None:
                end_date = datetime.date.today()

            start_date_str = start_date.strftime("%d%m%Y")
            end_date_str = end_date.strftime("%d%m%Y")

            logger.info(f"Generating Z Reports for date range: {start_date_str} - {end_date_str}")

            reserved_field = string_to_hex("0")
            start_hex = string_to_hex(start_date_str)
            end_hex = string_to_hex(end_date_str)

            code = "74"  # z_report_by_date command
            cmd = f"{STX}{code}{FS}{reserved_field}{FS}{start_hex}{FS}{end_hex}{ETX}"

            logger.debug(f"Sending Z report by date command: {cmd}")
            response = self._send_to_serial(cmd)
            logger.debug(f"Received response: {response}")

            if not self._is_success_response(response):
                logger.error(f"Failed to initialize Z reports by date - Response: {response}")
                return {
                    "success": False,
                    "error": "Failed to initialize Z reports by date. The printer may not have Z reports for this date range, or the dates may be invalid."
                }

            # Retrieve all reports in range
            reports_count = 0
            while True:
                get_code = "76"  # get_next_z_report command
                get_cmd = f"{STX}{get_code}{ETX}"
                report_response = self._send_to_serial(get_cmd)

                if report_response and report_response.endswith(NAK):
                    logger.info(f"Retrieved {reports_count} Z report(s)")
                    break

                if self._is_success_response(report_response):
                    reports_count += 1
                else:
                    logger.warning("Failed to get next Z report")
                    break

            # End the sequence
            end_code = "77"  # z_reports_end command
            end_cmd = f"{STX}{end_code}{ETX}"
            end_response = self._send_to_serial(end_cmd)

            if self._is_success_response(end_response):
                logger.info("Combined Z reports completed")

            if reports_count > 0:
                message = f"Printed {reports_count} Z report(s) from {start_date_str} to {end_date_str}"
                logger.info(message)
                return {
                    "success": True,
                    "message": message,
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "reports_count": reports_count
                }
            else:
                logger.warning(f"No Z reports found for date range {start_date_str} - {end_date_str}")
                return {
                    "success": False,
                    "error": f"No Z reports found for date range {start_date_str} - {end_date_str}"
                }

        except Exception as e:
            logger.error(f"Error printing Z Reports by date: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report_by_number(self, report_number: int) -> Dict[str, Any]:
        """Print a single Z report by number.

        Args:
            report_number: Z report sequential number

        Returns:
            dict: {"success": bool, "error": str, "report_number": int}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            logger.info(f"Generating Z Report by number: {report_number}")

            number_hex = string_to_hex(str(report_number).zfill(4))

            code = "75"  # z_report_by_number command
            cmd = f"{STX}{code}{FS}{number_hex}{FS}{number_hex}{ETX}"
            response = self._send_to_serial(cmd)

            if not self._is_success_response(response):
                logger.error("Failed to initialize Z report by number")
                return {"success": False, "error": "Failed to initialize Z report by number"}

            # Get the report
            get_code = "76"  # get_next_z_report command
            get_cmd = f"{STX}{get_code}{ETX}"
            report_response = self._send_to_serial(get_cmd)

            # End the sequence
            end_code = "77"  # z_reports_end command
            end_cmd = f"{STX}{end_code}{ETX}"
            self._send_to_serial(end_cmd)

            if report_response and report_response.endswith(NAK):
                logger.warning(f"Z report #{report_number} not found")
                return {"success": False, "error": f"Z report #{report_number} not found"}

            if self._is_success_response(report_response):
                logger.info(f"Z report #{report_number} printed successfully")
                return {
                    "success": True,
                    "message": f"Z Report #{report_number} printed successfully",
                    "report_number": report_number
                }

            logger.error("Failed to print Z report by number")
            return {"success": False, "error": "Failed to print Z report by number"}

        except Exception as e:
            logger.error(f"Error printing Z Report by number: {e}")
            return {"success": False, "error": str(e)}

    def print_z_report_by_number_range(self, start: int, end: int) -> Dict[str, Any]:
        """Print Z reports by number range.

        This implementation prints each report individually since the printer
        may not support range queries reliably with command 0x75.

        Args:
            start: Start report number
            end: End report number

        Returns:
            dict: {"success": bool, "error": str, "reports_printed": int}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            logger.info(f"Generating Z Reports by number range: {start} to {end}")

            reports_printed = 0
            reports_failed = 0
            expected_count = end - start + 1

            # Print each report individually
            for report_num in range(start, end + 1):
                logger.debug(f"Printing Z report #{report_num}")

                number_hex = string_to_hex(str(report_num).zfill(4))

                # Initialize single report
                code = "75"  # z_report_by_number command
                cmd = f"{STX}{code}{FS}{number_hex}{FS}{number_hex}{ETX}"
                response = self._send_to_serial(cmd)

                if not self._is_success_response(response):
                    logger.warning(f"Failed to initialize Z report #{report_num}")
                    reports_failed += 1
                    continue

                # Get the report
                get_code = "76"  # get_next_z_report command
                get_cmd = f"{STX}{get_code}{ETX}"
                report_response = self._send_to_serial(get_cmd)

                # End the sequence
                end_code = "77"  # z_reports_end command
                end_cmd = f"{STX}{end_code}{ETX}"
                self._send_to_serial(end_cmd)

                if report_response and report_response.endswith(NAK):
                    logger.warning(f"Z report #{report_num} not found")
                    reports_failed += 1
                    continue

                if self._is_success_response(report_response):
                    reports_printed += 1
                    logger.info(f"Z report #{report_num} printed ({reports_printed}/{expected_count})")
                else:
                    logger.warning(f"Failed to print Z report #{report_num}")
                    reports_failed += 1

            if reports_printed > 0:
                message = f"{reports_printed} Z Report(s) printed successfully (#{start} to #{end})"
                if reports_failed > 0:
                    message += f" ({reports_failed} not found)"
                logger.info(message)
                return {
                    "success": True,
                    "message": message,
                    "start_number": start,
                    "end_number": end,
                    "reports_printed": reports_printed
                }
            else:
                logger.warning("No Z reports found in the specified range")
                return {"success": False, "error": "No Z reports found in the specified range"}

        except Exception as e:
            logger.error(f"Error printing Z Reports by range: {e}")
            return {"success": False, "error": str(e)}

    def reprint_document(self, document_number: str) -> Dict[str, Any]:
        """Reprint a document copy (NO SALE).

        Command 0xA8 (168 decimal) - Search document/Print Copy
        Mode='1' (Printed) to print a copy directly

        Args:
            document_number: Document number to reprint

        Returns:
            dict: {"success": bool, "error": str, "document_number": str, "document_type": str}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            doc_num_str = str(document_number)
            logger.info(f"Re-printing document number: {doc_num_str}")

            code = "A8"
            mode_hex = string_to_hex("1")  # '1' = Print copy
            doc_num_hex = string_to_hex(doc_num_str)

            # Try different document types
            # Document types from manual (Section 6.8):
            # 01 = Invoice Final Consumer
            # 02 = Invoice Fiscal Credit
            # 03-09 = Other invoice types
            # 10 = No Sale document
            for doc_type in ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]:
                doc_type_hex = string_to_hex(doc_type)
                cmd = f"{STX}{code}{FS}{mode_hex}{FS}{doc_type_hex}{FS}{doc_num_hex}{ETX}"

                logger.debug(f"Trying document type {doc_type}:")
                logger.debug(f"  Full command: {cmd}")

                response = self._send_to_serial(cmd)

                if response and not response.endswith(NAK):
                    if self._is_success_response(response):
                        logger.info(f"Document {doc_num_str} found with type {doc_type} and re-printed successfully")
                        return {
                            "success": True,
                            "message": f"Document {doc_num_str} re-printed successfully (NO SALE)",
                            "document_number": doc_num_str,
                            "document_type": doc_type
                        }

            # Not found with any document type
            logger.warning(f"Document {doc_num_str} not found (tried all document types 01-10)")
            return {
                "success": False,
                "error": f"Document {doc_num_str} not found (tried all document types)"
            }

        except Exception as e:
            logger.error(f"Error re-printing document: {e}")
            return {"success": False, "error": str(e)}

    def print_no_sale(self, reason="") -> Dict[str, Any]:
        """Open cash drawer (no sale).

        Uses proper NO SALE document protocol from manual (commands 0x60, 0x61, 0x62).
        These are non-fiscal documents that don't affect fiscal totals.

        Args:
            reason: Optional reason for NO SALE

        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            if not self.connected:
                return {"success": False, "error": "Not connected to printer"}

            logger.info(f"Printing No Sale document{f' - Reason: {reason}' if reason else ''}")

            # Step 1: Open No Sale Document (Command 0x60)
            code = "60"
            cmd = f"{STX}{code}{ETX}"
            logger.debug("Opening No Sale document...")
            response = self._send_to_serial(cmd)

            if not self._is_success_response(response):
                logger.error(f"Failed to open No Sale document, response: {response}")
                return {"success": False, "error": "Failed to open No Sale document"}

            logger.debug("No Sale document opened")

            # Step 2: Print No Sale Lines (Command 0x61)
            # Each line can be up to 48 characters (thermal printer)
            lines_to_print = [
                "=" * 48,
                " ",
                "          NO SALE          ",
                " "
            ]

            if reason:
                lines_to_print.append(f"Reason: {reason[:40]}")  # Max 48 chars per line
                lines_to_print.append(" ")

            lines_to_print.append("=" * 48)

            for line in lines_to_print:
                code = "61"
                text_hex = string_to_hex(line)
                cmd = f"{STX}{code}{FS}{text_hex}{ETX}"
                logger.debug(f"Printing No Sale line: {line}")
                response = self._send_to_serial(cmd)

                if not self._is_success_response(response):
                    logger.warning(f"Failed to print No Sale line, response: {response}")
                    # Continue anyway - non-critical

            # Step 3: Close No Sale Document (Command 0x62)
            code = "62"
            cmd = f"{STX}{code}{ETX}"
            logger.debug("Closing No Sale document...")
            response = self._send_to_serial(cmd)

            if self._is_success_response(response):
                # Extract document number from response
                doc_number = self._decode_document_number(response)
                if doc_number:
                    logger.info(f"No Sale document printed successfully: {doc_number}")
                else:
                    logger.info("No Sale document printed successfully")
                return {"success": True}
            else:
                logger.error(f"Failed to close No Sale document, response: {response}")
                return {"success": False, "error": "Failed to close No Sale document"}

        except Exception as e:
            logger.error(f"Exception during No Sale: {e}")
            return {"success": False, "error": str(e)}

    def print_check(self) -> Dict[str, Any]:
        """Print a test check/receipt to verify printer connectivity.

        Reprints document #127 as a test (minimal paper usage).

        Returns:
            dict: {"success": bool, "error": str}
        """
        logger.info("Printing test check (reprinting document #127)...")
        return self.reprint_document("127")
