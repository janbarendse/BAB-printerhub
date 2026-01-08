"""
Odoo software integration wrapper.

This module implements the BaseSoftware interface for Odoo POS integration.
It wraps the existing rpc_client.py polling logic and provides a standardized
interface for the BABPrinterHub bridge system.
"""

import json
import logging
import threading
import time
import xmlrpc.client
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from software.base_software import BaseSoftware
from core import config_manager
from software.odoo.credentials_handler import load_credentials
from software.odoo.odoo_parser import odoo_parse_transaction

logger = logging.getLogger(__name__)


class OdooIntegration(BaseSoftware):
    """
    Odoo POS integration implementation.

    This class wraps the Odoo XML-RPC polling functionality and implements
    the BaseSoftware interface for consistent integration with the bridge system.
    """

    def __init__(self, config: Dict[str, Any], printer, full_config: Dict[str, Any]):
        """
        Initialize Odoo integration.

        Args:
            config: Odoo-specific configuration (config['software']['odoo'])
            printer: Active printer instance implementing BasePrinter
            full_config: Complete configuration dictionary (for config_manager)
        """
        super().__init__(config, printer)
        self.full_config = full_config
        self.base_dir = config_manager.get_base_dir()

        # Polling configuration
        polling_config = full_config.get('polling', {})
        self.poll_interval = polling_config.get('odoo_retry_interval_seconds', 10)

        # Odoo connection details (will be loaded from credentials)
        self.url = None
        self.database = None
        self.username = None
        self.password = None
        self.pos_config_name = None
        self.pos_config_id = None

        # XML-RPC clients
        self.uid = None
        self.models = None

        # Status tracking
        self.last_poll_time = None
        self.errors = []
        self.max_errors = 10  # Keep last 10 errors

        # Debug mode (process all orders, not just new ones)
        self.debug_mode = config.get('debug_mode', False)

    def start(self) -> bool:
        """
        Start the Odoo polling thread.

        Returns:
            bool: True if started successfully, False otherwise
        """
        logger.info("[DEBUG] OdooIntegration.start() method called")
        logger.info(f"[DEBUG] self.base_dir = {self.base_dir}")
        logger.info(f"[DEBUG] self.running = {self.running}")

        if self.running:
            logger.warning("Odoo integration already running")
            return False

        try:
            # Load credentials
            logger.info("Loading Odoo credentials...")
            try:
                credentials = load_credentials(self.base_dir)
                self.url = credentials['url']
                self.database = credentials['database']
                self.username = credentials['username']
                self.password = credentials['password']
                self.pos_config_name = credentials['pos_config_name']
                logger.info(f"✓ Credentials loaded successfully")
                logger.debug(f"  URL: {self.url}")
                logger.debug(f"  Database: {self.database}")
                logger.debug(f"  Username: {self.username}")
                logger.debug(f"  POS Config: {self.pos_config_name}")
            except FileNotFoundError as e:
                logger.error(f"✗ Credentials file not found: {e}")
                logger.error(f"  Expected location: {self.base_dir}")
                logger.error(f"  Please ensure 'odoo_credentials_encrypted.json' exists in the base directory")
                self._add_error(f"Credentials file not found: {e}")
                return False
            except json.JSONDecodeError as e:
                logger.error(f"✗ Invalid credentials file format: {e}")
                logger.error(f"  The credentials file may be corrupted or not valid JSON")
                self._add_error(f"Invalid credentials format: {e}")
                return False
            except Exception as e:
                logger.error(f"✗ Failed to decrypt credentials: {e}")
                logger.error(f"  The encryption key may be incorrect or the file may be corrupted")
                logger.error(f"  Error type: {type(e).__name__}")
                self._add_error(f"Credential decryption failed: {e}")
                return False

            # Test authentication
            logger.info("Authenticating with Odoo server...")
            if not self._authenticate():
                logger.error("✗ Failed to authenticate with Odoo")
                logger.error(f"  URL: {self.url}")
                logger.error(f"  Database: {self.database}")
                logger.error(f"  Username: {self.username}")
                logger.error(f"  Check that the credentials are correct and the server is accessible")
                return False

            # Fetch POS config ID
            logger.info(f"Fetching POS configuration '{self.pos_config_name}'...")
            if not self._fetch_pos_config_id():
                logger.error(f"✗ Failed to find POS config: {self.pos_config_name}")
                logger.error(f"  Please verify the POS configuration name exists in your Odoo instance")
                return False

            # Start polling thread
            self.running = True
            self.thread = threading.Thread(target=self._polling_loop, daemon=True)
            self.thread.start()

            logger.info(f"✓ Odoo integration started (polling interval: {self.poll_interval}s)")
            return True

        except Exception as e:
            logger.error(f"✗ Unexpected error starting Odoo integration: {e}")
            logger.error(f"  Error type: {type(e).__name__}")
            import traceback
            logger.debug(f"  Traceback: {traceback.format_exc()}")
            self._add_error(str(e))
            return False

    def stop(self) -> bool:
        """
        Stop the Odoo polling thread gracefully.

        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.running:
            logger.warning("Odoo integration not running")
            return False

        try:
            self.running = False

            # Wait for thread to finish (with timeout)
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=self.poll_interval + 5)
                if self.thread.is_alive():
                    logger.warning("Polling thread did not stop gracefully")
                    return False

            logger.info("Odoo integration stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping Odoo integration: {e}")
            self._add_error(str(e))
            return False

    def get_last_order_id(self) -> int:
        """
        Get the last processed order ID from configuration.

        Returns:
            int: Last order ID processed (0 if none)
        """
        return config_manager.get_last_order_id(self.full_config, 'odoo')

    def set_last_order_id(self, order_id: int) -> bool:
        """
        Update the last processed order ID in configuration.

        Args:
            order_id: New last order ID

        Returns:
            bool: True if saved successfully
        """
        return config_manager.set_last_order_id(self.full_config, order_id, 'odoo', save=True)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the Odoo integration.

        Returns:
            dict: Status information including:
                - running: bool (is integration active?)
                - last_poll_time: datetime (when last checked for orders)
                - last_order_id: int (last processed order)
                - errors: list (recent errors if any)
                - url: str (Odoo server URL)
                - database: str (database name)
                - pos_config_name: str (POS configuration name)
                - poll_interval: int (seconds between polls)
        """
        return {
            'running': self.running,
            'last_poll_time': self.last_poll_time,
            'last_order_id': self.get_last_order_id(),
            'errors': self.errors.copy(),
            'url': self.url,
            'database': self.database,
            'pos_config_name': self.pos_config_name,
            'poll_interval': self.poll_interval,
            'debug_mode': self.debug_mode
        }

    def parse_transaction(self, raw_data: Any) -> Optional[Dict[str, Any]]:
        """
        Parse raw Odoo order data into standardized format.

        Args:
            raw_data: Odoo order dictionary

        Returns:
            dict: Standardized transaction dict, or None if parse fails
        """
        try:
            result = odoo_parse_transaction(raw_data)

            # odoo_parse_transaction returns a tuple
            items, payments, service_charge, tips, discount, surcharge, is_refund, general_comment, customer_name, customer_crib = result

            if items is None or payments is None:
                logger.error("Failed to parse Odoo transaction")
                return None

            return {
                'items': items,
                'payments': payments,
                'service_charge': service_charge,
                'tips': tips,
                'discount': discount,
                'surcharge': surcharge,
                'is_refund': is_refund,
                'general_comment': general_comment,
                'customer_name': customer_name,
                'customer_crib': customer_crib,
                'receipt_number': raw_data.get('receipt_number'),
                'sequential_order_id': raw_data.get('sequential_order_id'),
                'pos_name': raw_data.get('pos_name')
            }

        except Exception as e:
            logger.error(f"Error parsing Odoo transaction: {e}")
            self._add_error(f"Parse error: {e}")
            return None

    def get_name(self) -> str:
        """
        Get the software integration name.

        Returns:
            str: "odoo"
        """
        return "odoo"

    # ========== Private Methods ==========

    def _authenticate(self) -> bool:
        """Authenticate with Odoo server."""
        try:
            logger.debug(f"Connecting to Odoo XML-RPC endpoint: {self.url}/xmlrpc/2/common")
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")

            logger.debug(f"Attempting authentication for database '{self.database}' with username '{self.username}'")
            self.uid = common.authenticate(self.database, self.username, self.password, {})

            if not self.uid:
                logger.error("✗ Authentication failed - server returned no user ID")
                logger.error("  Possible causes:")
                logger.error("  - Invalid username or password")
                logger.error("  - Database name is incorrect")
                logger.error("  - User account is disabled or does not exist")
                self._add_error("Authentication failed - invalid credentials")
                return False

            # Initialize models proxy
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

            logger.info(f"✓ Authenticated with Odoo as user ID {self.uid}")
            return True

        except xmlrpc.client.ProtocolError as e:
            logger.error(f"✗ XML-RPC protocol error during authentication: {e}")
            logger.error(f"  URL: {e.url}")
            logger.error(f"  HTTP Status: {e.errcode}")
            logger.error(f"  Message: {e.errmsg}")
            logger.error(f"  This usually means the server is unreachable or the URL is incorrect")
            self._add_error(f"Protocol error: {e.errcode} {e.errmsg}")
            return False
        except ConnectionRefusedError as e:
            logger.error(f"✗ Connection refused by Odoo server: {e}")
            logger.error(f"  URL: {self.url}")
            logger.error(f"  Check that the Odoo server is running and the URL is correct")
            self._add_error(f"Connection refused: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected authentication error: {e}")
            logger.error(f"  Error type: {type(e).__name__}")
            logger.error(f"  URL: {self.url}")
            logger.error(f"  Database: {self.database}")
            import traceback
            logger.debug(f"  Traceback: {traceback.format_exc()}")
            self._add_error(f"Auth error: {e}")
            return False

    def _fetch_pos_config_id(self) -> bool:
        """Fetch the POS configuration ID by name."""
        try:
            logger.debug(f"Searching for POS config with name: '{self.pos_config_name}'")
            pos_config_ids = self.models.execute_kw(
                self.database, self.uid, self.password,
                'pos.config', 'search',
                [[('name', '=', self.pos_config_name)]]
            )

            if not pos_config_ids:
                logger.error(f"✗ POS Config '{self.pos_config_name}' not found in Odoo")
                logger.error(f"  Please verify that:")
                logger.error(f"  1. The POS configuration exists in your Odoo instance")
                logger.error(f"  2. The name matches exactly (case-sensitive)")
                logger.error(f"  3. Your user has access to view POS configurations")

                # Try to list available POS configs for debugging
                try:
                    logger.info("  Attempting to list all available POS configurations...")
                    all_configs = self.models.execute_kw(
                        self.database, self.uid, self.password,
                        'pos.config', 'search_read',
                        [[]],
                        {'fields': ['name'], 'limit': 10}
                    )
                    if all_configs:
                        logger.info(f"  Found {len(all_configs)} POS configuration(s):")
                        for config in all_configs:
                            logger.info(f"    - {config['name']}")
                    else:
                        logger.warning("  No POS configurations found (user may not have access)")
                except Exception as list_err:
                    logger.debug(f"  Could not list POS configs: {list_err}")

                self._add_error(f"POS config '{self.pos_config_name}' not found")
                return False

            self.pos_config_id = pos_config_ids[0]
            logger.info(f"✓ Found POS Config ID {self.pos_config_id} for '{self.pos_config_name}'")
            return True

        except Exception as e:
            logger.error(f"✗ Error fetching POS config: {e}")
            logger.error(f"  Error type: {type(e).__name__}")
            import traceback
            logger.debug(f"  Traceback: {traceback.format_exc()}")
            self._add_error(f"POS config error: {e}")
            return False

    def _polling_loop(self):
        """Main polling loop (runs in background thread)."""
        logger.info("Odoo polling loop started")

        while self.running:
            try:
                self._poll_orders()
                self.last_poll_time = datetime.now()

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                self._add_error(f"Poll error: {e}")

            # Sleep for poll interval
            time.sleep(self.poll_interval)

        logger.info("Odoo polling loop stopped")

    def _poll_orders(self):
        """Poll for new orders and process them."""
        try:
            # Get last 24 hours of orders
            now = datetime.now()
            time_24_hours_ago = now - timedelta(hours=24)
            time_24_hours_ago_str = time_24_hours_ago.strftime('%Y-%m-%d %H:%M:%S')

            # Fetch orders
            pos_order_ids = self.models.execute_kw(
                self.database, self.uid, self.password,
                'pos.order', 'search',
                [[('date_order', '>=', time_24_hours_ago_str), ('config_id', '=', self.pos_config_id)]]
            )

            if not pos_order_ids:
                logger.debug("No POS orders found in the last 24 hours")
                return

            # Fetch order details
            pos_orders = self.models.execute_kw(
                self.database, self.uid, self.password,
                'pos.order', 'read',
                [pos_order_ids],
                {
                    'fields': ['id', 'name', 'partner_id', 'amount_total', 'date_order',
                              'state', 'config_id', 'payment_ids', 'lines', 'pos_reference', 'general_note']
                }
            )

            # Get last processed order ID
            last_order_id = self.get_last_order_id()

            # Process orders (oldest first)
            for order in reversed(pos_orders):
                # Skip already processed orders (unless in debug mode)
                if last_order_id and order['id'] <= last_order_id:
                    if not self.debug_mode:
                        logger.debug(f"Skipping order ID {order['id']} (already processed)")
                        continue

                # Process this order
                if self._process_order(order):
                    # Update last order ID (unless in debug mode)
                    if not self.debug_mode:
                        self.set_last_order_id(order['id'])
                else:
                    logger.error(f"Failed to process order ID {order['id']}")

        except Exception as e:
            logger.error(f"Error polling orders: {e}")
            self._add_error(f"Order poll error: {e}")

    def _process_order(self, order: Dict[str, Any]) -> bool:
        """
        Process a single Odoo order.

        Args:
            order: Odoo order dictionary

        Returns:
            bool: True if processed successfully
        """
        try:
            order_id = order['id']
            logger.info(f"Processing order ID {order_id}")
            logger.debug(f"Order Number: {order['name']}")
            logger.debug(f"POS Reference: {order['pos_reference']}")
            logger.debug(f"Customer: {order['partner_id'][1] if order['partner_id'] else 'Guest'}")
            logger.debug(f"Total Amount: €{order['amount_total']:.2f}")
            logger.debug(f"Date Ordered: {order['date_order']}")
            logger.debug(f"State: {order['state'].capitalize()}")

            # Build order data structure
            order_data = self._build_order_data(order)

            if not order_data:
                logger.error(f"Failed to build order data for order {order_id}")
                return False

            # Parse transaction using odoo_parser
            parsed_data = self.parse_transaction(order_data)

            if not parsed_data:
                logger.error(f"Failed to parse order {order_id}")
                return False

            # Send to printer
            if not self._print_order(parsed_data, order_data):
                logger.error(f"Failed to print order {order_id}")
                return False

            logger.info(f"Successfully processed order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Error processing order: {e}")
            self._add_error(f"Process error: {e}")
            return False

    def _build_order_data(self, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build standardized order data structure from Odoo order."""
        try:
            # Extract order note
            order_note = order.get('general_note', '') or ''

            # Initialize collections
            articles = []
            payments = []
            tip = 0.0
            service_charge = 0.0

            # NOTE: Order-level discounts in Odoo are typically implemented as line items with negative amounts
            # or special discount product codes, not as order-level fields. These are already handled
            # in the parser when processing line items with "[DISC]" or "Discount" in description.

            # Process order lines (items)
            if order['lines']:
                order_lines = self._fetch_order_lines(order['lines'])

                for line in order_lines:
                    product_name = line['product_id'][1] if line['product_id'] else "Unknown Product"
                    quantity = line['qty']
                    price_unit = line['price_unit']
                    vat_percent = "0"

                    # Extract item notes
                    item_note = line.get('note', '') or ''
                    customer_note = line.get('customer_note', '') or ''

                    # BUGFIX #1: Prevent order-level notes from appearing under products
                    # If customer_note matches order_note, clear it (it will print in footer instead)
                    if customer_note and order_note and customer_note.strip() == order_note.strip():
                        logger.debug(f"Skipping duplicate customer_note that matches order_note: {customer_note[:50]}")
                        customer_note = ''

                    item_full_name = line.get('full_product_name', '') or ''

                    # Extract discounts and surcharges
                    discount_percent = line.get('discount', 0.0) or 0.0
                    price_extra = line.get('price_extra', 0.0) or 0.0

                    # Build item notes list
                    item_notes = []
                    if item_note:
                        item_notes.append(f"Note: {item_note}")
                    if customer_note:
                        item_notes.append(f"Note: {customer_note}")

                    # Check if this is a tip
                    if product_name.startswith("[TIPS] Tips"):
                        tip += price_unit * quantity
                    else:
                        # Use price_unit (base price) - printer calculates VAT separately
                        # Format price correctly: ensure 2 decimals, then remove decimal point
                        # Example: 100.00 -> "100.00" -> "10000" (printer displays as 100.00)
                        price_str = f"{price_unit:.2f}"
                        price_formatted = price_str.replace(".", "")

                        logger.debug(f"Item '{product_name}': price_unit={price_unit}, qty={quantity}, formatted={price_formatted}")

                        # Get tax information and extract service charge
                        if line['tax_ids']:
                            taxes = self._fetch_taxes(line['tax_ids'])
                            for tax in taxes:
                                if "Service Charge" in tax['name']:
                                    # Extract service charge percentage (apply at order level)
                                    service_charge = tax['amount']
                                else:
                                    # Use non-service-charge taxes for VAT
                                    vat_percent = str(tax['amount'])

                        # Add article with base price (service charge applied at order level)
                        article = {
                            "void": False,
                            "vat_percent": vat_percent,
                            "discount_percent": str(discount_percent),
                            "surcharge_amount": str(price_extra),
                            "item_price": price_formatted,
                            "item_quantity": str(int(quantity)),
                            "item_unit": "Units",
                            "item_code": line['product_id'][0] if line['product_id'] else "ITEMCODE",
                            "item_description": product_name,
                            "item_notes": item_notes,
                            "customer_note": customer_note
                        }
                        articles.append(article)

            # Process payments
            if order['payment_ids']:
                payments_data = self._fetch_payments(order['payment_ids'])

                for payment in payments_data:
                    method_name = payment['payment_method_id'][1] if payment['payment_method_id'] else "Unknown Method"
                    amount = payment['amount']

                    payment_info = {
                        "method": method_name,
                        "amount": str(amount)
                    }
                    payments.append(payment_info)

            # Extract customer information
            customer_name = None
            customer_crib = None
            if order['partner_id']:
                customer_name = order['partner_id'][1]
                try:
                    partner_data = self.models.execute_kw(
                        self.database, self.uid, self.password,
                        'res.partner', 'read',
                        [[order['partner_id'][0]]],
                        {'fields': ['vat', 'id', 'name']}
                    )
                    if partner_data:
                        customer_crib = partner_data[0].get('vat') or str(partner_data[0]['id'])
                except Exception as e:
                    logger.warning(f"Could not fetch customer CRIB: {e}")
                    customer_crib = str(order['partner_id'][0])

            # Build final order data structure
            order_data = {
                "articles": articles,
                "payments": payments,
                "service_charge_percent": str(service_charge),  # Service charge applied at order level
                "tips": [],
                "order_id": str(order['id']),
                "receipt_number": order['pos_reference'],
                "sequential_order_id": str(order['id']),  # Sequential order ID from config (last_order_id)
                "pos_id": order['config_id'][0] if order['config_id'] else None,
                "pos_name": order['config_id'][1] if order['config_id'] else "Unknown POS",
                "order_note": order_note,
                "customer_name": customer_name,
                "customer_crib": customer_crib
            }

            # Add tips if present
            if tip > 0:
                order_data['tips'] = [{
                    "amount": str(float(tip))
                }]

            return order_data

        except Exception as e:
            logger.error(f"Error building order data: {e}")
            self._add_error(f"Build order error: {e}")
            return None

    def _fetch_order_lines(self, order_line_ids):
        """Fetch order line details from Odoo."""
        return self.models.execute_kw(
            self.database, self.uid, self.password,
            'pos.order.line', 'read',
            [order_line_ids],
            {
                'fields': ['product_id', 'qty', 'price_unit', 'price_subtotal_incl', 'tax_ids', 'note',
                          'customer_note', 'full_product_name', 'discount', 'price_extra', 'price_type']
            }
        )

    def _fetch_taxes(self, tax_ids):
        """Fetch tax details from Odoo."""
        return self.models.execute_kw(
            self.database, self.uid, self.password,
            'account.tax', 'read',
            [tax_ids],
            {'fields': ['name', 'amount']}
        )

    def _fetch_payments(self, payment_ids):
        """Fetch payment details from Odoo."""
        return self.models.execute_kw(
            self.database, self.uid, self.password,
            'pos.payment', 'read',
            [payment_ids],
            {'fields': ['payment_method_id', 'amount']}
        )

    def _print_order(self, parsed_data: Dict[str, Any], raw_order_data: Dict[str, Any]) -> bool:
        """
        Send order to printer.

        Args:
            parsed_data: Parsed transaction data
            raw_order_data: Raw order data (for storage)

        Returns:
            bool: True if printed successfully
        """
        try:
            # Send to printer
            result = self.printer.print_document(
                items=parsed_data['items'],
                payments=parsed_data['payments'],
                service_charge=parsed_data.get('service_charge'),
                tips=parsed_data.get('tips'),
                discount=parsed_data.get('discount'),
                surcharge=parsed_data.get('surcharge'),
                general_comment=parsed_data.get('general_comment', ''),
                is_refund=parsed_data.get('is_refund', False),
                receipt_number=parsed_data.get('receipt_number'),
                sequential_order_id=parsed_data.get('sequential_order_id'),
                pos_name=parsed_data.get('pos_name'),
                customer_name=parsed_data.get('customer_name'),
                customer_crib=parsed_data.get('customer_crib')
            )

            if result:
                # Store transaction (optional - implement if needed)
                # self._store_transaction(raw_order_data)
                return True
            else:
                logger.error("Printer returned False")
                return False

        except Exception as e:
            logger.error(f"Error printing order: {e}")
            self._add_error(f"Print error: {e}")
            return False

    def _add_error(self, error: str):
        """Add error to error list (keep last N errors)."""
        self.errors.append({
            'timestamp': datetime.now(),
            'error': error
        })
        # Keep only last N errors
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]
