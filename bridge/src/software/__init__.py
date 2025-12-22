"""
POS software integration modules.

This package contains integrations for various POS systems:
- odoo: Odoo POS integration (XML-RPC polling)
- tcpos: TCPOS integration (file-based watchdog)
- simphony: Simphony integration (placeholder)
- quickbooks: QuickBooks POS integration (placeholder)
"""

from .base_software import BaseSoftware


def create_software(config, printer):
    """
    Factory function to create software integration instance.

    Args:
        config: Full config dict from config.json
        printer: Active printer instance

    Returns:
        BaseSoftware: Instance of the active software integration

    Raises:
        ValueError: If software not found or not supported
    """
    software_name = config['software']['active']
    software_config = config['software'][software_name]

    if software_name == 'odoo':
        from .odoo.odoo_integration import OdooIntegration
        return OdooIntegration(software_config, printer, config)
    elif software_name == 'tcpos':
        from .tcpos.tcpos_integration import TCPOSIntegration
        return TCPOSIntegration(software_config, printer, config)
    elif software_name == 'simphony':
        from .simphony.simphony_integration import SimphonyIntegration
        return SimphonyIntegration(software_config, printer, config)
    elif software_name == 'quickbooks':
        from .quickbooks.quickbooks_integration import QuickBooksIntegration
        return QuickBooksIntegration(software_config, printer, config)
    else:
        raise ValueError(f"Unknown software: {software_name}")


__all__ = ['BaseSoftware', 'create_software']
