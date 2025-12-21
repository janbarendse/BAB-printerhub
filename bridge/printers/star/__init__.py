"""
Star Fiscal Printer Driver Package

This package provides a complete implementation of the Star fiscal printer
driver, using the MHI fiscal protocol (same as CTS310ii).

Note: Star printers use the same MHI fiscal protocol as CTS310ii printers.

Example usage:
    >>> from bridge.printers.star import StarDriver
    >>> config = {
    ...     'baud_rate': 9600,
    ...     'serial_timeout': 5,
    ...     'debug': False,
    ...     'client': {'NKF': '1234567890123456789'},
    ...     'miscellaneous': {
    ...         'default_client_name': 'Regular client',
    ...         'default_client_crib': '1000000000'
    ...     }
    ... }
    >>> driver = StarDriver(config)
    >>> driver.connect()
    True
    >>> status = driver.get_status()
    >>> print(status)
"""

from .star_driver import StarDriver
from .protocol import (
    STX, ETX, ACK, NAK, BEL, FS,
    tax_ids,
    payment_types,
    payment_methods,
    discount_surcharge_types,
    response_codes,
    states_codes,
    DEFAULT_BAUD_RATE,
    DEFAULT_SERIAL_TIMEOUT
)

__all__ = [
    'StarDriver',
    'STX',
    'ETX',
    'ACK',
    'NAK',
    'BEL',
    'FS',
    'tax_ids',
    'payment_types',
    'payment_methods',
    'discount_surcharge_types',
    'response_codes',
    'states_codes',
    'DEFAULT_BAUD_RATE',
    'DEFAULT_SERIAL_TIMEOUT'
]

__version__ = '1.0.0'
__author__ = 'BAB Printhub Team'
__description__ = 'Star Fiscal Printer Driver - Uses MHI protocol (same as CTS310ii)'
