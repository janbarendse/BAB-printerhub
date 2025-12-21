"""
Citizen Fiscal Printer Driver Package

This package provides a complete implementation of the Citizen fiscal printer
driver, which uses the MHI fiscal protocol (same as CTS310ii).

Example usage:
    >>> from bridge.printers.citizen import CitizenDriver
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
    >>> driver = CitizenDriver(config)
    >>> driver.connect()
    True
    >>> status = driver.get_status()
    >>> print(status)
"""

from .citizen_driver import CitizenDriver
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
    'CitizenDriver',
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
__description__ = 'Citizen Fiscal Printer Driver - Uses MHI protocol (same as CTS310ii)'
