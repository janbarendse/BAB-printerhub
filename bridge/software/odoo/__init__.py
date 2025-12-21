"""
Odoo POS integration module.

This module provides integration with Odoo POS systems via XML-RPC.
It implements the BaseSoftware interface for the BABPrinterHub bridge system.
"""

from .odoo_integration import OdooIntegration

__all__ = ['OdooIntegration']
