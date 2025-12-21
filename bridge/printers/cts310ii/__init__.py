"""
CTS310ii Fiscal Printer Driver Package

This package provides a complete implementation of the CTS310ii fiscal printer
driver, including protocol constants and the main driver class.

Example usage:
    >>> from bridge.printers.cts310ii import CTS310iiDriver
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
    >>> driver = CTS310iiDriver(config)
    >>> driver.connect()
    True
    >>> status = driver.get_status()
    >>> print(status)
"""

from .cts310ii_driver import CTS310iiDriver
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
    'CTS310iiDriver',
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

__version__ = '2.0.0'
__author__ = 'BAB Printhub Team'
__description__ = 'CTS310ii Fiscal Printer Driver - Merged from Odoo and TCPOS versions'
