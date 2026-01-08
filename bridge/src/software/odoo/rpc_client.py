import sys
import time
from logger_module import logger
import xmlrpc.client
import json
from datetime import datetime, timedelta
import os
from .credentials_handler import load_credentials


def _is_compiled():
    """Check if running as compiled executable (Nuitka or PyInstaller)."""
    # PyInstaller sets sys.frozen
    if getattr(sys, "frozen", False):
        return True
    # Nuitka sets __compiled__ at module level
    if "__compiled__" in globals():
        return True
    # Check if executable ends with .exe and is not python.exe/pythonw.exe
    if sys.executable.lower().endswith('.exe'):
        exe_name = os.path.basename(sys.executable).lower()
        if exe_name not in ('python.exe', 'pythonw.exe', 'python3.exe', 'python313.exe'):
            return True
    return False


def _resolve_base_dir():
    """
    Resolve base directory with proper priority for compiled executables.
    Priority: compiled executable > environment variable > source location
    """
    if _is_compiled():
        # Running as compiled executable - ALWAYS use exe directory (ignore BAB_UI_BASE)
        return os.path.dirname(sys.executable)

    # Running from source - check for environment variable override
    env_base = os.environ.get("BAB_UI_BASE")
    if env_base:
        return env_base

    if __file__:
        return os.path.dirname(os.path.abspath(__file__))

    return os.getcwd()


base_dir = _resolve_base_dir()


def load_config():
    with open(os.path.join(base_dir, 'config.json')) as json_file:
        return json.load(json_file)


LAST_ORDER_ID_FILE = 'last_order_id.txt'
DEBUG = False

# Load polling configuration
config = load_config()
polling_config = config.get('polling', {
    'printer_retry_interval_seconds': 5,
    'odoo_retry_interval_seconds': 10
})
ODOO_POLL_INTERVAL = polling_config.get('odoo_retry_interval_seconds', 10)

def authenticate(url, database, username, password):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(database, username, password, {})
    if not uid:
        raise ValueError("Authentication failed! Please check your credentials.")
    return uid

def fetch_pos_config_id(models, database, uid, password, pos_config_name):
    pos_config_ids = models.execute_kw(database, uid, password, 'pos.config', 'search', [
        [('name', '=', pos_config_name)]
    ])
    if not pos_config_ids:
        raise ValueError(f"POS Config with name '{pos_config_name}' not found.")
    return pos_config_ids[0]

def fetch_pos_orders(models, database, uid, password, time_24_hours_ago_str, pos_config_id):
    pos_order_ids = models.execute_kw(database, uid, password, 'pos.order', 'search', [
        [('date_order', '>=', time_24_hours_ago_str), ('config_id', '=', pos_config_id)]
    ])
    if not pos_order_ids:
        logger.debug("No POS orders found in the last 24 hours.")
        exit()
    return models.execute_kw(database, uid, password, 'pos.order', 'read', [pos_order_ids], {
        'fields': ['id', 'name', 'partner_id', 'amount_total', 'date_order', 'state', 'config_id', 'payment_ids', 'lines', 'pos_reference', 'general_note']
    })

def fetch_order_lines(models, database, uid, password, order_line_ids):
    return models.execute_kw(database, uid, password, 'pos.order.line', 'read', [order_line_ids], {
        'fields': ['product_id', 'qty', 'price_unit', 'tax_ids', 'note', 'customer_note', 'full_product_name', 'discount', 'price_extra', 'price_type']
    })

def fetch_taxes(models, database, uid, password, tax_ids):
    return models.execute_kw(database, uid, password, 'account.tax', 'read', [tax_ids], {
        'fields': ['name', 'amount']
    })

def fetch_payments(models, database, uid, password, payment_ids):
    return models.execute_kw(database, uid, password, 'pos.payment', 'read', [payment_ids], {
        'fields': ['payment_method_id', 'amount']
    })

def format_amount(amount):
    return f"{int(round(float(amount) * 100))}"

def get_last_order_id():
    if os.path.exists(LAST_ORDER_ID_FILE):
        with open(LAST_ORDER_ID_FILE, 'r') as file:
            return int(file.read().strip())
    return None

def save_last_order_id(order_id):
    with open(LAST_ORDER_ID_FILE, 'w') as file:
        file.write(str(order_id))

def main():
    while 1:
        try:
            credentials = load_credentials(base_dir, 'odoo_credentials_encrypted.json')
            url = credentials['url']
            database = credentials['database']
            username = credentials['username']
            password = credentials['password']
            pos_config_name = credentials['pos_config_name']

            uid = authenticate(url, database, username, password)
            models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

            pos_config_id = fetch_pos_config_id(models, database, uid, password, pos_config_name)

            now = datetime.now()
            time_24_hours_ago = now - timedelta(hours=24)
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')
            time_24_hours_ago_str = time_24_hours_ago.strftime('%Y-%m-%d %H:%M:%S')

            last_order_id = get_last_order_id()
            pos_orders = fetch_pos_orders(models, database, uid, password, time_24_hours_ago_str, pos_config_id)

            final_data = []

            logger.debug("\n===== POS Orders from Last 24 Hours =====\n")

            # reverse to process the oldest orders first
            for order in reversed(pos_orders):
                # for order in pos_orders:
                if last_order_id and order['id'] <= last_order_id:
                    if not DEBUG:
                        logger.debug(f"Skipping order ID {order['id']} as it has already been processed.")
                        continue  # Skip already processed orders
                    elif 1:  # In DEBUG mode, process all orders
                        continue
                    # else:
                    #     # logger.debug(f"Processing order ID {order['id']} again in DEBUG MODE.")

                logger.debug(f"Order ID      : {order['id']}")
                logger.debug(f"Order Number  : {order['name']}")
                logger.debug(f"POS Reference : {order['pos_reference']}")
                logger.debug(f"POS Config    : {order['config_id'][0] if order['config_id'] else 'N/A'}")
                logger.debug(f"POS Name      : {order['config_id'][1] if order['config_id'] else 'POS'}")
                logger.debug(f"Customer      : {order['partner_id'][1] if order['partner_id'] else 'Guest'}")
                logger.debug(f"Total Amount  : €{order['amount_total']:.2f}")
                logger.debug(f"Date Ordered  : {order['date_order']}")
                logger.debug(f"State         : {order['state'].capitalize()}")
                logger.debug(f"POS Config ID : {order['config_id'][1] if order['config_id'] else 'N/A'}")
                logger.debug(f"Payment IDs   : {', '.join(map(str, order['payment_ids'])) if order['payment_ids'] else 'None'}")

                # Capturar nota general de la orden
                order_note = order.get('general_note', '') or ''
                if order_note:
                    logger.debug(f"Order Note    : {order_note}")

                tip = 0.0  # Initialize tip variable
                service_charge = 0.0  # Initialize service charge variable
                articles = []  # Initialize articles list
                payments = []  # Initialize payments list

                order_line_ids = order['lines']
                if order_line_ids:
                    order_lines = fetch_order_lines(models, database, uid, password, order_line_ids)
                    logger.debug("\n   Purchased Products:")
                    for line in order_lines:
                        product_name = line['product_id'][1] if line['product_id'] else "Unknown Product"
                        quantity = line['qty']
                        price = line['price_unit']
                        vat_percent = "0"

                        # Capturar notas del item
                        item_note = line.get('note', '') or ''
                        customer_note = line.get('customer_note', '') or ''
                        item_full_name = line.get('full_product_name', '') or ''

                        # Capturar descuentos y recargos
                        discount_percent = line.get('discount', 0.0) or 0.0
                        price_extra = line.get('price_extra', 0.0) or 0.0
                        price_type = line.get('price_type', '') or ''

                        # Los descuentos en Odoo están siempre como porcentaje
                        # Los recargos (price_extra) están como valor fijo                        # Si existe full_product_name y es diferente al product_name, puede contener notas
                        item_notes = []
                        if item_note:
                            item_notes.append(f"Note: {item_note}")

                        if customer_note:
                            item_notes.append(f"Note: {customer_note}")

                        if 0:
                            if item_full_name and item_full_name != product_name:
                                item_notes.append(f"Full name: {item_full_name}")

                        if product_name.startswith("[TIPS] Tips"):
                            tip += price * quantity
                        else:
                            if line['tax_ids']:
                                taxes = fetch_taxes(models, database, uid, password, line['tax_ids'])
                                filtered_taxes = []
                                for tax in taxes:
                                    if "Service Charge" in tax['name']:
                                        service_charge = tax['amount']
                                    else:
                                        vat_percent = str(tax['amount'])
                                        filtered_taxes.append(tax)
                                for tax in filtered_taxes:
                                    logger.debug(f"      Tax: {tax['name']} @ {tax['amount']}%")
                            else:
                                logger.debug("      No taxes applied.")

                            article = {
                                "void": False,
                                "vat_percent": vat_percent,
                                "discount_percent": str(discount_percent),  # Porcentaje de descuento
                                "surcharge_amount": str(price_extra),  # Recargo/extra (valor fijo)
                                # "item_price": format_amount(price),
                                "item_price": str(price),
                                "item_quantity": str(int(quantity)),
                                "item_unit": "Units",
                                "item_code": line['product_id'][0] if line['product_id'] else "ITEMCODE",
                                "item_description": product_name,
                                "item_notes": item_notes  # Agregar notas del item
                            }
                            articles.append(article)
                            logger.debug(f"   - {product_name} x {quantity} @ €{price:.2f} each")

                            # Mostrar descuentos y recargos si existen
                            if discount_percent > 0:
                                logger.debug(f"     Discount: {discount_percent}%")
                            if price_extra > 0:
                                logger.debug(f"     Surcharge: €{price_extra:.2f}")

                            # Mostrar notas del item si existen
                            if item_notes:
                                logger.debug(f"     Notes: {'; '.join(item_notes)}")
                else:
                    logger.debug("\n   No products found for this order.")

                if order['payment_ids']:
                    payments_data = fetch_payments(models, database, uid, password, order['payment_ids'])
                    logger.debug("\n   Payments:")
                    for payment in payments_data:
                        method_name = payment['payment_method_id'][1] if payment['payment_method_id'] else "Unknown Method"
                        amount = payment['amount']

                        if 0:
                            if float(amount) < 0:
                                continue # Skip negative payments, odoo sends them for changes

                        payment_info = {
                            "method": method_name,
                            "amount": str(amount)
                        }
                        payments.append(payment_info)
                        logger.debug(f"   - Method: {method_name}, Amount: €{amount:.2f}")

                # Extract customer information from Odoo order
                customer_name = None
                customer_crib = None
                if order['partner_id']:
                    customer_name = order['partner_id'][1]  # Partner name
                    # Fetch partner details to get CRIB (vat or id)
                    try:
                        partner_data = models.execute_kw(database, uid, password, 'res.partner', 'read', [[order['partner_id'][0]]], {
                            'fields': ['vat', 'id', 'name']
                        })
                        if partner_data:
                            customer_crib = partner_data[0].get('vat') or str(partner_data[0]['id'])
                            logger.debug(f"   Customer CRIB: {customer_crib}")
                    except Exception as e:
                        logger.warning(f"Could not fetch customer CRIB: {e}")
                        customer_crib = str(order['partner_id'][0])  # Fallback to partner ID

                order_data = {
                    "articles": articles,
                    "payments": payments,
                    "service_charge_percent": str(service_charge),
                    "tips": [],
                    "order_id": str(order['id']),
                    "receipt_number": order['pos_reference'],  # Receipt number
                    "pos_id": order['config_id'][0] if order['config_id'] else None,  # POS ID
                    "pos_name": order['config_id'][1] if order['config_id'] else "Unknown POS",  # POS name
                    "order_note": order_note,  # Nota general de la orden
                    "customer_name": customer_name,  # Customer name from partner
                    "customer_crib": customer_crib  # Customer CRIB (vat or ID)
                }

                final_data.append(order_data)

                if tip > 0:
                    logger.debug(f"\n   Tip Amount: €{tip:.2f}")
                    order_data['tips'] = [{
                        "amount": str(float(tip))
                    }]

                if service_charge > 0:
                    logger.debug(f"\n   Service Charge: {service_charge}%")

                if order_note:
                    logger.debug(f"\n   Order General Note: {order_note}")

                logger.debug("-" * 50)

            # logger.debug final data
            logger.debug("\n===== Final Data =====\n")
            logger.debug(json.dumps(final_data, indent=4))

            if 0:
                # Save final data to a JSON file
                file_name = "pos_orders.json"
                with open(file_name, "w", encoding="utf-8") as json_file:
                    json.dump(final_data, json_file, indent=4)

                logger.debug(f"POS order data saved to {file_name}")

            # Save the last processed order ID
            from odoo_parser import main as odoo_parse_order

            for order in final_data:
                print(order)
                result = odoo_parse_order(order)
                result = True

                if result:
                    if pos_orders and not DEBUG:
                        # if 1:
                        save_last_order_id(order['order_id'])
                    else:
                        logger.debug(f"Skipping saving last order ID in DEBUG mode.")
                else:
                    logger.error(f"Error processing order ID {order['order_id']}.")

        except Exception as e:
            logger.error("Error: " + str(e))
        # exit()
        time.sleep(ODOO_POLL_INTERVAL)  # Poll interval from config
        if DEBUG:
            break

if __name__ == "__main__":
    main()