"""
Epson Fiscal Printer Driver Package (STUB)

This package provides a stub implementation for the Epson fiscal printer driver.
Epson printers use the ESC/POS protocol, which is different from the MHI protocol
used by CTS310ii, Star, and Citizen printers.

All methods raise NotImplementedError until the driver is fully implemented.
Implementation is planned for Q2 2026.

Example usage (when implemented):
    >>> from bridge.printers.epson import EpsonDriver
    >>> config = {
    ...     'baud_rate': 9600,
    ...     'serial_timeout': 5,
    ...     'debug': False
    ... }
    >>> driver = EpsonDriver(config)
    >>> # driver.connect()  # Will raise NotImplementedError
"""

from .epson_driver import EpsonDriver

__all__ = [
    'EpsonDriver'
]

__version__ = '0.1.0'
__author__ = 'BAB Printhub Team'
__description__ = 'Epson Fiscal Printer Driver (STUB) - ESC/POS protocol - Planned for Q2 2026'
