import datetime
import traceback
import threading
import time
import json
import os
import sys
from logger_module import logger
from core.text_utils import wrap_text_to_lines, distribute_text_bottom_up


if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
elif __file__:
    # Go up 4 levels from bridge/src/software/odoo/ to bridge/
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_config():
    with open(os.path.join(base_dir, 'config.json')) as json_file:
        return json.load(json_file)


config = load_config()


tax_ids = {
    "6.0": "1",  # tax percent : printer tax id
    "7.0": "2",
    "9.0": "3"
}

def get_payment_methods():
    """Load payment methods from config (not cached at module level)"""
    config = load_config()
    # Load from software.odoo.payment_methods for the unified config structure
    return config.get('software', {}).get('odoo', {}).get('payment_methods', {
        "Cash": "00",
        "Cheque": "01",
        "Credit Card": "02",
        "Debit Card": "03",
        "Credit note": "04",
        "Voucher": "05",
        "Customer Account": "06",
        "other_2": "07",
        "other_3": "08",
        "other_4": "09",
        "donations": "10",
    })

# payment methods: Cash, Cheque, CreditCard, DebitCard, credit_note, Voucher, other_1, other_2, other_3, other_4, donations

def encode_float_number(number, decimal_places):
    # 2.000
    # check if there is a dot
    if '.' in number:
        # make sure it has three decimal places
        if not len(number.split('.')[1]) == decimal_places:
            # add zeroes
            number += '0' * (decimal_places - len(number.split('.')[1]))

        # remove the dot
        number = number.replace('.', '')

    else:
        number += '0' * decimal_places

    return number


def encode_measurement_unit(measurement_unit):
    # Units Kilos Grams Pounds Boxes
    if measurement_unit == 'Units':
        return "Units"
    elif measurement_unit == 'Kilos':
        return "Kilos"
    elif measurement_unit == 'Grams':
        return "Grams"
    elif measurement_unit == 'Pounds':
        return "Pounds"
    elif measurement_unit == 'Boxes':
        return "Boxes"
    else:
        raise Exception(f"Unsupported measurement unit: {measurement_unit}")


def format_printer_descriptions(item_description, customer_note, item_notes):
    """
    Format 3-line printer descriptions based on customer note presence.

    Logic:
    - If customer_note exists:
        - Line 1: item_description (truncated to 48 chars if needed)
        - Lines 2-3: customer_note wrapped (line 3 mandatory)
    - If NO customer_note:
        - Lines 1-3: item_description wrapped bottom-up (line 3 mandatory)
        - Item notes ignored (or could append, see future enhancement)

    Args:
        item_description (str): Product name/title
        customer_note (str): Customer-specific note
        item_notes (list[str]): Array of formatted item notes (currently unused)

    Returns:
        tuple: (line1, line2, line3) where line3 is always non-empty
    """
    # Strip and validate customer note
    customer_note_clean = (customer_note or '').strip()

    if customer_note_clean:
        # MODE 1: Customer note exists
        # Line 1: Product title (truncated if >48 chars)
        line1 = item_description[:48] if len(item_description) > 48 else item_description

        # Lines 2-3: Wrap customer note
        wrapped_note = wrap_text_to_lines(customer_note_clean, max_chars=48, max_lines=2)

        if len(wrapped_note) == 0:
            # Customer note was only whitespace after cleaning
            # Fall back to product title mode
            lines = distribute_text_bottom_up(item_description, num_lines=3, max_chars=48)
            return lines[0], lines[1], lines[2]

        elif len(wrapped_note) == 1:
            # Customer note fits on 1 line → line 3
            # Product title goes on line 2 (not line 1) to avoid empty L2
            line1 = ''
            line2 = item_description[:48] if len(item_description) > 48 else item_description
            line3 = wrapped_note[0]

        else:  # len(wrapped_note) >= 2
            # Customer note spans 2+ lines → lines 2 and 3
            # Product title on line 1
            line2 = wrapped_note[0]
            line3 = wrapped_note[1]

        return line1, line2, line3

    else:
        # MODE 2: No customer note - fill from bottom with product title
        lines = distribute_text_bottom_up(item_description, num_lines=3, max_chars=48)
        return lines[0], lines[1], lines[2]


def process_discount_surcharge(item, op_type):
    if op_type == "discount":
        try:
            if item['item_price'] == "0.00":
                return None

            return {
                "type": "0",  # Discount type
                "description": "Discount",
                "amount": encode_float_number(str(item['item_price']), 2),  # Total discount amount including tax
                "percent": "000",  # No percentage for total discount
            }
        except Exception:
            return None

    elif op_type == "surcharge":
        try:
            if item['item_price'] == "0.00":
                return None

            return {
                "type": "1",  # Surcharge type
                "description": "Surcharge",
                "amount": encode_float_number(str(item['item_price']), 2),  # Total surcharge amount including tax
                "percent": "000",  # No percentage for total surcharge
            }
        except Exception:
            return None

def get_sub_items(data):
    try:
        """
        {
                    "type": "00",  # 0 = normal item, 1 = void item
                    "extra_description_1": "",
                    "extra_description_2": "",
                    "item_description": "a",
                    "product_code": "123",
                    "quantity": "2000",  # 2.000
                    "unit_price": "155",  # 1.55
                    "unit": "Units",  # Units Kilos Grams Pounds Boxes
                    "tax": "1",  # tax id
                    "discount_type": "0",
                    "discount_amount": "000",
                    "discount_percent": "000",  # 10.50%
                }

        """
        logger.debug("Getting sub items...")
        sub_items = []
        discount_or_surcharge = None
        discount_total_amount = 0
        surcharge_total_amount = 0
        has_negative_quantity = False  # Track if any item has negative quantity (refund)

        for item in data:
            void_item = item['void']
            tax_exempt = False

            if float(item['vat_percent']) == 0:
                tax_exempt = True

            if "[DISC]" in item['item_description'] or "Discount" in item['item_description']:
                print(f"Discount item")
                # calculate discount amount with the tax
                item_price = item['item_price'].replace("-", "")
                logger.debug(f"Discount price: {item_price}")  # item_price)
                discount_amount = float(item_price) * int(item['item_quantity'])
                discount_total_amount += discount_amount
                continue

            if "surcharge" in item['item_description'].lower():
                print(f"Surcharge item")
                # calculate discount amount with the tax
                item_price = item['item_price'].replace("-", "")
                logger.debug(f"Surcharge price: {item_price}")  # item_price)
                surcharge_amount = float(item_price) * int(item['item_quantity'])
                surcharge_total_amount += surcharge_amount
                continue

            if "-" in item['item_quantity']:
                # Negative quantity indicates a refund
                has_negative_quantity = True
                # convert to positive
                item['item_quantity'] = item['item_quantity'].replace("-", "")

            # Extract customer note (with fallback for backward compatibility)
            customer_note = item.get('customer_note', '')
            item_notes = item.get('item_notes', [])

            # Format 3-line descriptions
            line1, line2, line3 = format_printer_descriptions(
                item_description=item['item_description'],
                customer_note=customer_note,
                item_notes=item_notes
            )

            # Debug logging
            logger.debug(f"Formatted descriptions - L1: '{line1}', L2: '{line2}', L3: '{line3}'")

            sub_items.append({
                "type": "02" if void_item else "01",
                "item_description": line1,      # Line 1
                "extra_description_1": line2,   # Line 2
                "extra_description_2": line3,   # Line 3 (MANDATORY - always has content)
                "product_code": " ",  # Space character to hide from receipt but avoid crash
                "quantity": encode_float_number(item['item_quantity'], 3),  # 2.000
                # item_price is already formatted correctly from odoo_integration.py - don't re-encode
                "unit_price": item['item_price'],  # Already formatted as "10000" for 100.00
                "unit": encode_measurement_unit(item['item_unit']),  # Units Kilos Grams Pounds Boxes
                "tax": tax_ids[item['vat_percent']] if not tax_exempt else "0",  # tax id
                "discount_type": "0",
                "discount_amount": "000",
                "discount_percent": "000",  # 10.50%
            })

        # convert amount to float 2 decimal places
        discount_total_amount = "{:.2f}".format(float(discount_total_amount))
        surcharge_total_amount = "{:.2f}".format(float(surcharge_total_amount))
        discount_data = {
            "item_price": str(discount_total_amount),
        }
        discount = process_discount_surcharge(discount_data, "discount")

        surcharge_data = {
            "item_price": str(surcharge_total_amount),
        }

        surcharge = process_discount_surcharge(surcharge_data, "surcharge")

        logger.debug("Sub items:")
        logger.debug(json.dumps(sub_items, indent=4))

        logger.debug("Discount or surcharge:")
        logger.debug(json.dumps(discount_or_surcharge, indent=4))

        if has_negative_quantity:
            logger.debug("Refund detected: items have negative quantities")

        return sub_items, discount, surcharge, has_negative_quantity

    except Exception as e:
        logger.error("Error while getting sub items: " + str(e))
        logger.error(traceback.format_exc())

        return None, None, None, False


def get_service_charge(percent):
    logger.debug("Getting service charge...")
    logger.debug(f"Service charge percent: {percent}")
    # check if there is any service
    if float(percent) > 0:
        service = {
            "type": "2",
            "description": "Service charge",
            "amount": "000",
            "percent": encode_float_number(percent, 2),
        }

        logger.debug("Service charge:")
        logger.debug(json.dumps(service, indent=4))

        return service
    logger.debug("No service charge.")
    return None


def get_payment_details(data):
    logger.debug("Getting payment details...")

    is_refund = False
    try:
        payment_methods = get_payment_methods()  # Load from config
        payment_details = []

        # if length of data is 1 then it could be a refund
        logger.debug(f"Payment data: {data}")
        if len(data) == 1:
            if "-" in data[0]['amount']:
                # it is a refund
                data[0]['amount'] = data[0]['amount'].replace("-", "")
                payment_details.append({
                    "type": "1",
                    "method": payment_methods[data[0]['method']],
                    "description": " ",  # Empty description to avoid duplicate payment name
                    "amount": encode_float_number(data[0]['amount'], 2),
                })

                is_refund = True

            else:
                payment_details.append({
                    "type": "1",
                    "method": payment_methods[data[0]['method']],
                    "description": " ",  # Empty description to avoid duplicate payment name
                    "amount": encode_float_number(data[0]['amount'], 2),
                })

        else:
            for payment in data:
                # ignore negative amounts as odoo send them as changes
                if "-" not in payment['amount']:
                    payment_details.append({
                        "type": "1",
                        "method": payment_methods[payment['method']],
                        "description": " ",  # Empty description to avoid duplicate payment name
                        "amount": encode_float_number(payment['amount'], 2),
                    })


        logger.debug("Payment details:")
        logger.debug(json.dumps(payment_details, indent=4))
        return payment_details, is_refund

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("Error: " + str(e))

    return None, None


def get_tips(data):
    logger.debug("Getting tips...")
    try:
        tips = []

        for tip in data:
            tips.append({
                "type": "1",
                "method": "10",
                "description": "Tip",
                "amount": encode_float_number(tip['amount'], 2),
            })


        logger.debug("Tips:")
        logger.debug(json.dumps(tips, indent=4))
        return tips

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("Error: " + str(e))

    return None


def odoo_parse_transaction(data):
    try:
        items, discount, surcharge, has_negative_quantity = get_sub_items(data['articles'])
        payments, is_refund_from_payment = get_payment_details(data['payments'])
        service_charge = get_service_charge(data['service_charge_percent'])
        general_comment = data['order_note'] if data['order_note'] else ""
        tips = get_tips(data['tips'])

        # Detect refund from either negative quantities or negative payment amounts
        is_refund = is_refund_from_payment or has_negative_quantity

        if is_refund:
            logger.debug("This is a REFUND transaction")

        # Extract customer information from Odoo order
        customer_name = data.get('customer_name', None)
        customer_crib = data.get('customer_crib', None)

        # Clean up customer data
        if customer_name:
            customer_name = customer_name.strip()
            if not customer_name or customer_name.lower() == 'none':
                customer_name = None

        if customer_crib:
            customer_crib = str(customer_crib).strip()
            if not customer_crib or customer_crib.lower() == 'none':
                customer_crib = None

        logger.debug(f"Extracted customer info - Name: {customer_name}, CRIB: {customer_crib}")

        return items, payments, service_charge, tips, discount, surcharge, is_refund, general_comment, customer_name, customer_crib

    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error("Error 1: " + str(e))

    return None, None, None, None, None, None, None, None, None, None


def get_next_index_for_stored_transactions():
    # loop through files in transactions folder
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    max_index = 0
    for root, dirs, files in os.walk(os.path.join(base_dir, 'transactions')):
        # take files starting with the current date
        if len(files) > 0:
            for file in files:
                if file.startswith(current_date):
                    file_index = int(file.split('.')[0].split('_')[-1])
                    if file_index > max_index:
                        max_index = file_index
    return max_index + 1


def main(data):
    try:
        config = json.load(open('config.json'))
        if 1:
            from cts310ii import print_document
            # import cts310ii
            # cts310ii.COM_PORT = "COM7"

            receipt_number = data.get('receipt_number', None)
            pos_name = data.get('pos_name', None)
            items, payments, service_charge, tips, discount, surcharge, is_refund, general_comment, customer_name, customer_crib = odoo_parse_transaction(data)

            # Allow refunds to print without payments (they're returns)
            if items and (payments or is_refund):

                print_document(
                    items,
                    payments,
                    service_charge,
                    tips,
                    discount,
                    surcharge,
                    general_comment,
                    is_refund,
                    receipt_number,
                    pos_name,
                    customer_name,
                    customer_crib
                )

                filename = f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{get_next_index_for_stored_transactions()}.json"
                # save data to file
                with open(os.path.join(base_dir, 'transactions', filename), 'w') as outfile:
                    json.dump(data, outfile, indent=4)

                return True

    except Exception as e:
        logger.error("Error: " + str(e))

    return False

if __name__ == "__main__":
    tr1 = {
        "articles": [
            {
                "void": False,
                "vat_percent": "9",
                "tip_percent": "10",
                "discount_amount": "10",
                "item_price": "100",
                "item_quantity": "1",
                "item_unit": "Units",
                "item_code": "ITEMCODE",
                "item_description": "Coca Cola"
            }
        ],
        "payments": [
            {
                "method": "Cash",
                "amount": "100"
            }
        ],
        "service_charge_percent": "10",
        "tips": [
            {
                "amount": "10"
            }
        ]
    }

    # a = get_next_index_for_stored_transactions()
    main(tr1)
