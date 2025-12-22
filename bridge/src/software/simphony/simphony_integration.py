"""
Simphony POS integration (Oracle Simphony).

This is a placeholder implementation for future development.
Simphony integration is planned for Q2 2026.
"""

from typing import Dict, Any, Optional
from ..base_software import BaseSoftware


class SimphonyIntegration(BaseSoftware):
    """
    Placeholder for Oracle Simphony POS integration.

    Simphony is Oracle's enterprise-grade POS system used in hospitality.
    Integration will require either:
    - Database polling (SimphonyPOS database)
    - API integration (if available)
    - File export monitoring

    See simphony/README.md for planned implementation approach.
    """

    def __init__(self, config: Dict[str, Any], printer, full_config: Dict[str, Any]):
        """Initialize Simphony integration (placeholder)."""
        super().__init__(config, printer)
        self.full_config = full_config

    def start(self) -> bool:
        """Start the integration."""
        raise NotImplementedError(
            "Simphony integration not yet implemented. "
            "This feature is planned for Q2 2026. "
            "See bridge/software/simphony/README.md for implementation roadmap."
        )

    def stop(self) -> bool:
        """Stop the integration."""
        raise NotImplementedError(
            "Simphony integration not yet implemented."
        )

    def get_last_order_id(self) -> int:
        """Get last processed order ID."""
        return 0

    def set_last_order_id(self, order_id: int) -> bool:
        """Update last processed order ID."""
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        return {
            "running": False,
            "implemented": False,
            "planned_release": "Q2 2026",
            "status": "Not implemented - placeholder only"
        }

    def parse_transaction(self, raw_data: Any) -> Optional[Dict[str, Any]]:
        """Parse Simphony transaction."""
        raise NotImplementedError(
            "Simphony transaction parsing not yet implemented."
        )

    def get_name(self) -> str:
        """Get software name."""
        return "simphony"
