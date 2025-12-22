"""
Fiscal printer driver modules.

This package contains drivers for various fiscal printers:
- cts310ii: CTS310II fiscal printer (MHI protocol)
- star: Star fiscal printer (placeholder, same protocol as CTS310ii)
- citizen: Citizen fiscal printer (placeholder, same protocol as CTS310ii)
- epson: Epson fiscal printer (placeholder, different protocol)
"""

from .base_printer import BasePrinter


def create_printer(config):
    """
    Factory function to create printer driver instance.

    Args:
        config: Full config dict from config.json

    Returns:
        BasePrinter: Instance of the active printer driver

    Raises:
        ValueError: If printer not found or not supported
    """
    printer_name = config['printer']['active']

    # Merge printer-specific config with global config sections
    printer_config = config['printer'][printer_name].copy()
    printer_config['client'] = config.get('client', {})
    printer_config['miscellaneous'] = config.get('miscellaneous', {})

    if printer_name == 'cts310ii':
        from .cts310ii.cts310ii_driver import CTS310iiDriver
        return CTS310iiDriver(printer_config)
    elif printer_name == 'star':
        from .star.star_driver import StarDriver
        return StarDriver(printer_config)
    elif printer_name == 'citizen':
        from .citizen.citizen_driver import CitizenDriver
        return CitizenDriver(printer_config)
    elif printer_name == 'epson':
        from .epson.epson_driver import EpsonDriver
        return EpsonDriver(printer_config)
    else:
        raise ValueError(f"Unknown printer: {printer_name}")


__all__ = ['BasePrinter', 'create_printer']
