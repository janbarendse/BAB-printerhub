from packaging.version import Version
import traceback
import threading
import time
import xml.etree.ElementTree as ET
import json
import xmltodict
import os
import sys
import logging

# Set up logger
logger = logging.getLogger(__name__)


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


transaction_uuid = None
supported_version = "8.0"

tax_ids = {
    "6": "1",  # tax percent : printer tax id
    "7": "2",
    "9": "3"
}

payment_methods = {
    "Cash": "00",
    "Cheque": "01",
    "CreditCard": "02",
    "DebitCard": "03",
    "credit_note": "04",
    "Voucher": "05",
    "other_1": "06",
    "other_2": "07",
    "other_3": "08",
    "other_4": "09",
    "donations": "10",
}


def get_transaction_uuid(xml_json_object):
    logger.debug("Getting transaction uuid...")
    # loop through keys values
    for key, value in xml_json_object.items():
        return key


def get_vat_information(xml_json_object):
    """
    returns a dictionary with vat IDs and percents
    """

    vat_information = {}
    for vat in xml_json_object[transaction_uuid]['data']['VatDetails']['TCPOS.FrontEnd.BusinessLogic.VatDetail']:
        vat_information[vat['Data']['@ID']] = vat['Data']['@Percent']

    # logger.debug(json.dumps(vat_information, indent=4))
    return vat_information


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
    if measurement_unit == 'pcs':
        return "Units"

    else:
        return "Units"


def split_printout_notes(printout_notes, max_chars=48):
    """
    Split printout notes into chunks of max_chars.
    Returns tuple: (line1, line2) where each line is max 48 chars
    Line 1 is the first part, Line 2 is the continuation
    """
    if not printout_notes:
        return ("", "")

    # Split into words to avoid breaking mid-word
    words = printout_notes.split()
    line1 = ""
    line2 = ""

    # Build line 1
    for word in words:
        if len(line1) + len(word) + (1 if line1 else 0) <= max_chars:
            line1 += (" " if line1 else "") + word
        else:
            # Start filling line 2
            if len(line2) + len(word) + (1 if line2 else 0) <= max_chars:
                line2 += (" " if line2 else "") + word
            else:
                # Can't fit more, truncate
                break

    return (line1, line2)


def check_file_version(xml_json_object):
    version = xml_json_object[transaction_uuid]['data']["@SoftwareVersion"]

    if Version(version) < Version(supported_version):
        raise Exception(f"Unsupported version: {xml_json_object[transaction_uuid]['@_version']}")
        # print(f"Unsupported version: {version}")


def process_discount_surcharge(item):
    """
    Extract item-level discount or surcharge from DiscountValues and subItems.
    Returns dict with type, amount, percent for printer command 41.
    Negative amount = discount, positive = surcharge.
    """
    if "DiscountValues" not in item:
        return None

    # Find the DiscountValue key
    target_key = ""
    for key, value in item['DiscountValues'].items():
        if key.startswith('DiscountValue-'):
            target_key = key
            break

    if target_key == "":
        return None

    discount_value = item['DiscountValues'][target_key]
    amount_str = discount_value.get("@Amount", "0")

    # Determine if discount (negative) or surcharge (positive)
    is_discount = amount_str.startswith('-')

    # Strip the sign for encoding
    amount_abs = amount_str[1:] if is_discount else amount_str

    # Check if amount is zero
    if float(amount_abs) == 0:
        return None

    # Try to extract percentage and type from subItems -> TransDiscount
    percent_value = "00000"
    is_percent_discount = False

    if "subItems" in item:
        sub_items = item["subItems"]
        # Handle both dict and list formats
        if isinstance(sub_items, dict):
            for key, value in sub_items.items():
                if "TransDiscount" in key and isinstance(value, dict):
                    # Check the discount type
                    if "Data" in value:
                        discount_type = value["Data"].get("@Type", "")
                        is_percent_discount = discount_type in ["PercentDiscount", "PercentSupplement"]

                    if "AppliedThresholds" in value:
                        thresholds = value["AppliedThresholds"]
                        # Get the first threshold item
                        for t_key, t_value in thresholds.items():
                            if "AppliedThresholdItem" in t_key:
                                discount_percent = t_value.get("@DiscountPercent", "")
                                if discount_percent:
                                    # Percent field is 5 digits: percentage * 100, e.g., 10.50% = "01050"
                                    percent_value = encode_float_number(discount_percent, 2).zfill(5)
                                break
                        break

    # Use amount only - printer doesn't accept both amount and percent together
    # Include percentage in description for percentage discounts (e.g., "Discount 33%")
    description = "Item Discount" if is_discount else "Item Surcharge"
    if is_percent_discount and percent_value != "00000":
        # Extract percentage value and add to description
        percent_display = float(percent_value) / 100  # e.g., 03300 -> 33.00
        description = f"{'Discount' if is_discount else 'Surcharge'} {percent_display:.0f}%"

    return {
        "type": "1" if is_discount else "2",  # "1" = Discount, "2" = Surcharge
        "description": description,
        "amount": encode_float_number(amount_abs, 2),
        "percent": "00000",  # Always "00000" for printer (uses amount only)
        "percent_display": percent_value if is_percent_discount else "00000",  # For display purposes only
    }


def get_sub_items(xml_json_object):
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
                    "discount_percent": "00000",  # e.g., 10.50% = "01050"
                }

        """
        logger.debug("Getting sub items...")
        sub_items = []
        tips = []
        # Dictionary to consolidate items by product code (for handling complimentary items)
        items_by_code = {}

        # Check if transaction has tax exoneration - extract original VAT index
        transaction_data = xml_json_object[transaction_uuid]['data']
        original_vat_index = transaction_data.get('@_x003C_RecalcOriginalVATIndex_x003E_k__BackingField', None)

        # BUGFIX #6: Check if there's a transaction-level discount/surcharge
        # If yes, skip item-level discounts/surcharges to avoid double deduction
        # TCPOS stores both discounts AND surcharges in TransDiscount element (Type field distinguishes them)
        # TCPOS distributes transaction discounts/surcharges across items, so item DiscountValues
        # are just a distribution of the TransDiscount and should be ignored
        skip_item_discounts = False
        if "TCPOS.FrontEnd.BusinessLogic.TransDiscount" in transaction_data.get('subItems', {}):
            skip_item_discounts = True
            logger.info("Transaction-level discount/surcharge detected - skipping item-level discounts/surcharges to avoid double deduction")

        # BUGFIX #5: Detect credit notes early to handle negative quantities correctly
        is_credit_note = False
        total_str = transaction_data.get('@total', '0')
        try:
            total_amount = float(total_str)
            if total_amount < 0:
                is_credit_note = True
                logger.info(f"Credit note detected in get_sub_items: total={total_amount}")
        except (ValueError, TypeError):
            pass

        # Get original VAT rate for net price calculation (vatIndex "1" = 9% tax)
        original_vat_rate = 0.09 if original_vat_index == "1" else 0.0
        # Process list of TransArticle items
        if type(xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransArticle']) is list:
            for item in xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransArticle']:
                void_item = False
                tax_exempt = False

                # check if item was deleted
                if "@deleteOperatorID" in item:
                    void_item = True

                if "@_vatPercent" not in item:
                    tax_exempt = True

                # Handle tips separately
                if "@shortDescription" in item['Data']:
                    if item['Data']['@shortDescription'] == "Tip" or item['Data']['@shortDescription'] == "Tip %":
                        tips.append({
                            "type": "1",
                            "method": "10",
                            "description": "Tip",
                            "amount": encode_float_number(item['@_enteredPrice'], 2),
                        })
                        continue

                # Don't apply discount at item level - it will be applied at subtotal level
                discount_or_surcharge = None

                if "@_enteredPrice" not in item:
                    price = item['prices']['index_0']['@Price']
                else:
                    price = item['@_enteredPrice']

                # Extract product info
                product_code = item['Data']['@Code']
                product_title = item['Data']['@Description']
                printout_notes = item['Data'].get('@PrintoutNotes', '')

                # Get quantity with sign (check for negative quantities in complimentary items)
                # Use ValueOfRevertableQuantity if available (has the sign), otherwise quantityWithPrecision
                if '@ValueOfRevertableQuantity' in item:
                    quantity = float(item['@ValueOfRevertableQuantity'])
                elif '@quantity' in item:
                    quantity = float(item['@quantity'])
                else:
                    quantity = float(item['@quantityWithPrecision'])

                # If item was voided (has deleteOperatorID), make quantity negative
                if void_item:
                    quantity = -abs(quantity)

                unit_price = float(price)
                total_amount = quantity * unit_price

                # Extract item-level discount/surcharge
                # BUGFIX #6: Skip if transaction has order-level discount to avoid double deduction
                if skip_item_discounts:
                    item_discount_surcharge = None
                else:
                    item_discount_surcharge = process_discount_surcharge(item)

                # Store item data for consolidation by product code
                if product_code not in items_by_code:
                    items_by_code[product_code] = {
                        'product_code': product_code,
                        'product_title': product_title,
                        'printout_notes': printout_notes,
                        'void_item': void_item,
                        'tax_exempt': tax_exempt,
                        'tax_id': "0" if (tax_exempt or item['@_vatPercent'] == '0') else tax_ids[item['@_vatPercent']],
                        'unit': encode_measurement_unit(item['measureUnit']['@Code']),
                        'quantities': [],
                        'amounts': [],
                        'discounts_surcharges': [],  # Track item-level discounts/surcharges
                    }

                # Add this instance to the consolidation tracking
                items_by_code[product_code]['quantities'].append(quantity)
                items_by_code[product_code]['amounts'].append(total_amount)
                items_by_code[product_code]['discounts_surcharges'].append(item_discount_surcharge)

        # Process single TransArticle item
        elif type(xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransArticle']) is dict:
            item = xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransArticle']

            void_item = False
            tax_exempt = False

            # check if item was deleted
            if "@deleteOperatorID" in item:
                void_item = True

            if "@_vatPercent" not in item:
                tax_exempt = True

            # Handle tips separately
            if "@shortDescription" in item['Data']:
                if item['Data']['@shortDescription'] == "Tip" or item['Data']['@shortDescription'] == "Tip %":
                    tips.append({
                        "type": "1",
                        "method": "10",
                        "description": "Tip",
                        "amount": encode_float_number(item['@_enteredPrice'], 2),
                    })
            else:
                # Extract product info
                product_code = item['Data']['@Code']
                product_title = item['Data']['@Description']
                printout_notes = item['Data'].get('@PrintoutNotes', '')

                # Get quantity with sign (check for negative quantities in complimentary items)
                # Use ValueOfRevertableQuantity if available (has the sign), otherwise quantityWithPrecision
                if '@ValueOfRevertableQuantity' in item:
                    quantity = float(item['@ValueOfRevertableQuantity'])
                elif '@quantity' in item:
                    quantity = float(item['@quantity'])
                else:
                    quantity = float(item['@quantityWithPrecision'])

                # If item was voided (has deleteOperatorID), make quantity negative
                if void_item:
                    quantity = -abs(quantity)

                unit_price = float(item['prices']['index_0']['@Price'])
                total_amount = quantity * unit_price

                # Extract item-level discount/surcharge
                # BUGFIX #6: Skip if transaction has order-level discount to avoid double deduction
                if skip_item_discounts:
                    item_discount_surcharge = None
                else:
                    item_discount_surcharge = process_discount_surcharge(item)

                # Store item data for consolidation by product code
                if product_code not in items_by_code:
                    items_by_code[product_code] = {
                        'product_code': product_code,
                        'product_title': product_title,
                        'printout_notes': printout_notes,
                        'void_item': void_item,
                        'tax_exempt': tax_exempt,
                        'tax_id': "0" if (tax_exempt or item['@_vatPercent'] == '0') else tax_ids[item['@_vatPercent']],
                        'unit': encode_measurement_unit(item['measureUnit']['@Code']),
                        'quantities': [],
                        'amounts': [],
                        'discounts_surcharges': [],  # Track item-level discounts/surcharges
                    }

                # Add this instance to the consolidation tracking
                items_by_code[product_code]['quantities'].append(quantity)
                items_by_code[product_code]['amounts'].append(total_amount)
                items_by_code[product_code]['discounts_surcharges'].append(item_discount_surcharge)

        # Process items by product code (separate paid and voided items)
        for product_code, item_data in items_by_code.items():
            # BUGFIX #5: For credit notes, treat ALL items as "paid" with absolute values
            if is_credit_note:
                # For credit notes: convert all negative quantities to positive
                positive_quantities = [abs(q) for q in item_data['quantities']]
                negative_quantities = []  # No voided items for credit notes
                positive_amounts = [abs(item_data['amounts'][i]) for i in range(len(item_data['quantities']))]
            else:
                # For normal transactions: separate positive (paid) and negative (voided) quantities
                positive_quantities = [q for q in item_data['quantities'] if q > 0]
                negative_quantities = [q for q in item_data['quantities'] if q < 0]
                positive_amounts = [item_data['amounts'][i] for i, q in enumerate(item_data['quantities']) if q > 0]

            product_title = item_data['product_title']
            printout_notes = item_data['printout_notes']

            # Format description lines
            if not printout_notes:
                line1 = ""
                line2 = ""
                line3 = product_title
            elif len(printout_notes) <= 48:
                line1 = ""
                line2 = product_title
                line3 = printout_notes
            else:
                notes_line1, notes_line2 = split_printout_notes(printout_notes)
                if notes_line2:
                    line1 = product_title
                    line2 = notes_line1
                    line3 = notes_line2
                else:
                    line1 = ""
                    line2 = product_title
                    line3 = notes_line1

            # Add paid items (positive quantities) with actual price
            if positive_quantities:
                paid_quantity = sum(positive_quantities)
                paid_amount = sum(positive_amounts)
                paid_unit_price = paid_amount / paid_quantity

                # Convert gross to net price for tax-exempt items
                if item_data['tax_id'] == "0" and original_vat_rate > 0:
                    paid_unit_price = round(paid_unit_price / (1 + original_vat_rate), 2)
                    logger.info(f"Tax-exempt item: converted gross price to net (÷ {1 + original_vat_rate:.2f}), new price: {paid_unit_price}")

                # Get item-level discount/surcharge (if any positive quantity item has one)
                # BUGFIX #6: Item discounts are already skipped if TransDiscount exists (set to None above)
                item_discount = None
                for i, q in enumerate(item_data['quantities']):
                    if q > 0 and item_data['discounts_surcharges'][i] is not None:
                        item_discount = item_data['discounts_surcharges'][i]
                        break

                # Add discount percentage to description if present (only for discounts, not surcharges)
                if item_discount and item_discount.get('percent_display', "00000") != "00000" and item_discount.get('type') == "1":
                    # Extract percentage value (e.g., "03300" -> 33.00%)
                    percent_value = float(item_discount['percent_display']) / 100
                    discount_text = f"w/ {percent_value:.0f}% disc."

                    # Append to the last non-empty line, truncate if needed to fit in 48 chars
                    if line3:
                        combined = f"{line3} {discount_text}"
                        if len(combined) <= 48:
                            line3 = combined
                        else:
                            # Truncate product name to fit discount text
                            available_space = 48 - len(discount_text) - 1  # -1 for space
                            line3 = f"{line3[:available_space]} {discount_text}"
                    elif line2:
                        combined = f"{line2} {discount_text}"
                        if len(combined) <= 48:
                            line2 = combined
                        else:
                            available_space = 48 - len(discount_text) - 1
                            line2 = f"{line2[:available_space]} {discount_text}"
                    elif line1:
                        combined = f"{line1} {discount_text}"
                        if len(combined) <= 48:
                            line1 = combined
                        else:
                            available_space = 48 - len(discount_text) - 1
                            line1 = f"{line1[:available_space]} {discount_text}"

                # Build item with discount/surcharge included in the item command itself
                # For command 41: discount_type "0" = none, "1" = discount, "2" = surcharge
                item_dict = {
                    "type": "02" if item_data['void_item'] else "01",
                    "extra_description_2": line1,
                    "extra_description_1": line2,
                    "item_description": line3,
                    "product_code": product_code,
                    "quantity": encode_float_number(str(paid_quantity), 3),
                    "unit_price": encode_float_number(str(paid_unit_price), 2),
                    "unit": item_data['unit'],
                    "tax": item_data['tax_id'],
                    "discount_type": item_discount["type"] if item_discount else "0",
                    "discount_amount": item_discount["amount"] if item_discount else "000",
                    "discount_percent": item_discount["percent"] if item_discount else "00000",
                }

                if item_discount:
                    logger.info(f"Item {product_code} has {'discount' if item_discount['type'] == '1' else 'surcharge'} - type: {item_discount['type']}, amount: {item_discount['amount']}, percent: {item_discount['percent']}")

                sub_items.append(item_dict)
                logger.info(f"Item {product_code} ({product_title}) - Paid: {paid_quantity}x @ {paid_unit_price}, tax_id: {item_dict['tax']}")

            # Add voided items (negative quantities) as separate line with price 0
            if negative_quantities:
                voided_quantity = abs(sum(negative_quantities))  # Make positive for display

                sub_items.append({
                    "type": "02" if item_data['void_item'] else "01",
                    "extra_description_2": line1,
                    "extra_description_1": line2,
                    "item_description": line3,
                    "product_code": product_code,
                    "quantity": encode_float_number(str(voided_quantity), 3),
                    "unit_price": "000",  # Price 0.00 for voided items
                    "unit": item_data['unit'],
                    "tax": item_data['tax_id'],
                    "discount_type": "0",
                    "discount_amount": "000",
                    "discount_percent": "000",
                })
                logger.info(f"Item {product_code} ({product_title}) - Voided: {voided_quantity}x @ 0.00")

        # Process TransMenu (combo deals/menus)
        if "TCPOS.FrontEnd.BusinessLogic.TransMenu" in xml_json_object[transaction_uuid]['data']['subItems']:
            menus = xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransMenu']
            # Handle both single menu and list of menus
            if not isinstance(menus, list):
                menus = [menus]

            for menu in menus:
                # Get menu description and price
                menu_description = menu['Data']['@Description']
                menu_price = menu['prices']['index_0']['@Price']
                menu_quantity = menu.get('@quantity', '1')
                print_details = menu['Data'].get('@PrintDetails', 'false') == 'true'

                # Extract sub-item names if PrintDetails is true
                sub_item_names = []
                if print_details and 'subItems' in menu:
                    menu_items = menu['subItems']['TCPOS.FrontEnd.BusinessLogic.TransMenuItem']
                    if not isinstance(menu_items, list):
                        menu_items = [menu_items]

                    for menu_item in menu_items:
                        if 'subItems' in menu_item:
                            articles = menu_item['subItems']['TCPOS.FrontEnd.BusinessLogic.TransArticle']
                            if not isinstance(articles, list):
                                articles = [articles]
                            for article in articles:
                                sub_item_names.append(article['Data']['@Description'])

                # Build description lines (menu name on line 1, sub-items on lines 2 and 3)
                line1 = menu_description  # Menu name at the top
                line2 = ""
                line3 = ""  # Must have content (mandatory)

                if sub_item_names:
                    # Concatenate sub-items with ", "
                    items_text = ", ".join(sub_item_names)
                    # Split into two lines if needed (max 48 chars per line)
                    if len(items_text) <= 48:
                        # Fits on one line - put on line 3 (mandatory)
                        line3 = items_text
                    else:
                        # Split at comma boundary near 48 chars
                        words = items_text.split(", ")
                        line2_parts = []
                        line3_parts = []
                        current_line = 2
                        current_length = 0

                        for word in words:
                            word_with_comma = word if word == words[-1] else word + ", "
                            if current_line == 2:
                                if current_length + len(word_with_comma) <= 48:
                                    line2_parts.append(word)
                                    current_length += len(word_with_comma)
                                else:
                                    current_line = 3
                                    line3_parts.append(word)
                                    current_length = len(word_with_comma)
                            else:
                                if current_length + len(word_with_comma) <= 48:
                                    line3_parts.append(word)
                                    current_length += len(word_with_comma)
                                else:
                                    break  # No more space

                        line2 = ", ".join(line2_parts) if line2_parts else ""
                        line3 = ", ".join(line3_parts) if line3_parts else ""

                # Ensure line3 is never empty (mandatory field)
                if not line3:
                    line3 = " "  # Space character if no sub-items

                # Strip negative signs for credit notes
                menu_quantity_str = str(menu_quantity)
                if menu_quantity_str.startswith('-'):
                    menu_quantity_str = menu_quantity_str[1:]

                menu_price_str = str(menu_price)
                if menu_price_str.startswith('-'):
                    menu_price_str = menu_price_str[1:]

                # Add the menu as a single line item with sub-items as descriptions
                sub_items.append({
                    "type": "01",
                    "extra_description_2": line1,  # Line 1 (top) - first part of sub-items
                    "extra_description_1": line2,  # Line 2 (middle) - second part of sub-items
                    "item_description": line3,     # Line 3 (bottom, mandatory) - menu name
                    "product_code": menu['Data'].get('@Code', ''),
                    "quantity": encode_float_number(menu_quantity_str, 3),
                    "unit_price": encode_float_number(menu_price_str, 2),
                    "unit": "Units",
                    "tax": "1",  # Assuming tax ID 1 (9%)
                    "discount_type": "0",
                    "discount_amount": "000",
                    "discount_percent": "000",
                })

        logger.debug("Sub items:")
        logger.debug(json.dumps(sub_items, indent=4))
        logger.debug("Tips:")
        logger.debug(json.dumps(tips, indent=4))
        return sub_items, tips

    except Exception as e:
        logger.error("Error while getting sub items: " + str(e))
        logger.error(traceback.format_exc())

        return None, None


def get_service_charge(xml_json_object):
    logger.debug("Getting service charge...")
    # check if there is any service
    if "TCPOS.FrontEnd.BusinessLogic.TransServiceSupplement" in xml_json_object[transaction_uuid]['data']['subItems']:
        service = {
            "type": "2",
            "description": "Service charge",
            "amount": "000",
            "percent": encode_float_number(xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransServiceSupplement']['@servicePercent'], 2),
        }

        logger.debug("Service charge:")
        logger.debug(json.dumps(service, indent=4))

        return service

    return None


def get_customer_info(xml_json_object):
    """
    Extract customer information from TransCustomer element.
    Returns dict with customer name and code/CRIB, or None if no customer.
    """
    logger.debug("Getting customer information...")
    try:
        # Check if there is a customer in the transaction
        if "TCPOS.FrontEnd.BusinessLogic.TransCustomer" in xml_json_object[transaction_uuid]['data']['subItems']:
            customer_element = xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransCustomer']

            # Extract customer name fields
            customer_data = customer_element['Data']
            first_name = customer_data.get('@FirstName', '')
            description = customer_data.get('@Description', '')  # Usually last name or full name
            code = customer_data.get('@Code', '')  # Customer code/card number for CRIB

            # Combine first name and description
            if first_name and description:
                full_name = f"{first_name} {description}"
            elif description:
                full_name = description
            elif first_name:
                full_name = first_name
            else:
                return None

            logger.info(f"Customer found: {full_name}, Code: {code}")
            return {
                "name": full_name,
                "code": code
            }

    except Exception as e:
        logger.error(f"Error extracting customer info: {str(e)}")

    return None


def get_discount(xml_json_object):
    """
    Extract transaction-level discount from TransDiscount element.
    Returns discount object for subtotal-level application.
    """
    logger.debug("Getting transaction discount...")
    try:
        # Check if there is a transaction-level discount
        if "TCPOS.FrontEnd.BusinessLogic.TransDiscount" in xml_json_object[transaction_uuid]['data']['subItems']:
            discount_element = xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransDiscount']

            # Check if this is a surcharge or discount based on Type field
            discount_type_field = discount_element['Data'].get('@Type', '')
            is_surcharge = discount_type_field in ['AmountSupplement', 'PercentSupplement']
            is_percent = discount_type_field in ['PercentSupplement', 'PercentDiscount']

            if is_percent:
                # For percentage discounts/surcharges, extract the percentage value
                # The percentage is in AppliedThresholds/AppliedThresholdItem/@DiscountPercent
                try:
                    applied_threshold = discount_element['AppliedThresholds']['TCPOS.FrontEnd.BusinessLogic.TransDiscount_x002B_AppliedThresholdItem']
                    discount_percent = applied_threshold.get('@DiscountPercent', '0')

                    # Strip negative sign for encoding
                    if discount_percent.startswith('-'):
                        discount_percent = discount_percent[1:]

                    # Check if percent is zero
                    if float(discount_percent) == 0:
                        logger.debug("Discount/surcharge percentage is zero, skipping")
                        return None

                    discount = {
                        "type": "1" if is_surcharge else "0",  # "1" = Surcharge, "0" = Discount
                        "description": discount_element['Data'].get('@Description', 'Discount'),
                        "amount": "000",  # Not using amount for percentage
                        "percent": encode_float_number(discount_percent, 2),  # Use percentage
                    }
                except Exception as e:
                    logger.error(f"Error extracting percentage: {str(e)}")
                    return None
            else:
                # For fixed amount discounts/surcharges, extract the amount
                discount_amount = discount_element.get('@UnitDiscount', '0')

                # Strip negative sign for encoding
                if discount_amount.startswith('-'):
                    discount_amount = discount_amount[1:]

                # Check if amount is zero
                if float(discount_amount) == 0:
                    logger.debug("Discount/surcharge amount is zero, skipping")
                    return None

                discount = {
                    "type": "1" if is_surcharge else "0",  # "1" = Surcharge, "0" = Discount
                    "description": discount_element['Data'].get('@Description', 'Discount'),
                    "amount": encode_float_number(discount_amount, 2),
                    "percent": "000",  # Not using percent for fixed amount
                }

            logger.debug(f"Transaction {'surcharge' if is_surcharge else 'discount'}:")
            logger.debug(json.dumps(discount, indent=4))

            return discount

    except Exception as e:
        logger.error(f"Error extracting discount: {str(e)}")
        logger.error(traceback.format_exc())

    return None


def get_payment_details(xml_json_object):
    logger.debug("Getting payment details...")
    try:
        payment_details = []

        if type(xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransPayment']) is list:

            for payment in xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransPayment']:
                # For credit notes, payment amounts are negative - strip the minus sign
                amount_str = str(payment['@amount'])
                if amount_str.startswith('-'):
                    amount_str = amount_str[1:]  # Remove leading minus
                    logger.debug(f"Credit note payment: stripped negative sign from {payment['@amount']} -> {amount_str}")

                payment_details.append({
                    "type": "1",
                    "method": payment_methods[payment['Data']['@Type']],
                    "description": " ",
                    "amount": encode_float_number(amount_str, 2),
                })

        elif type(xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransPayment']) is dict:
            # For credit notes, payment amounts are negative - strip the minus sign
            amount_str = str(xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransPayment']['@amount'])
            if amount_str.startswith('-'):
                amount_str = amount_str[1:]  # Remove leading minus
                logger.debug(f"Credit note payment: stripped negative sign from {xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransPayment']['@amount']} -> {amount_str}")

            payment_details.append({
                "type": "1",
                "method": payment_methods[xml_json_object[transaction_uuid]['data']['subItems']['TCPOS.FrontEnd.BusinessLogic.TransPayment']['Data']['@Type']],
                "description": " ",
                "amount": encode_float_number(amount_str, 2),
            })

        logger.debug("Payment details:")
        logger.debug(json.dumps(payment_details, indent=4))
        return payment_details

    except Exception as e:
        logger.error("Error: " + str(e))

    return None


def tcpos_parse_transaction(filename):
    global transaction_uuid

    # filename = "TIP PERCENT-Trn 19-22-28 #37"
    # filename += ".xml"
    try:
        # Check if file exists and is not empty
        if not os.path.exists(filename):
            raise Exception(f"File does not exist: {filename}")

        file_size = os.path.getsize(filename)
        if file_size == 0:
            raise Exception(f"File is empty (0 bytes): {filename}")

        # Check if file is still being written to by trying to open it exclusively
        # Wait a bit to ensure TCPOS has finished writing
        time.sleep(0.5)

        with open(filename, 'r', encoding='utf-8') as xml_file:
            # Read content first to check if it's valid
            content = xml_file.read()
            if not content.strip():
                raise Exception(f"File contains no content: {filename}")

            # Reset file pointer to beginning
            xml_file.seek(0)

            try:
                xml_tree = ET.parse(xml_file)
            except ET.ParseError as parse_err:
                raise Exception(f"XML parse error in {filename}: {str(parse_err)}")

        xml_data = xml_tree.getroot()
        xmlstr = ET.tostring(xml_data, encoding='utf-8', method='xml')
        xml_json_object = xmltodict.parse(xmlstr)
        logger.info(f"File: {filename}")

        if 0:
            # save to file
            with open(os.path.join(base_dir, 'xmls', filename + '.json'), 'w') as outfile:
                json.dump(xml_json_object, outfile, indent=4)


        transaction_uuid = get_transaction_uuid(xml_json_object)
        logger.debug(f"Transaction UUID: {transaction_uuid}")
        # vat_information = get_vat_information(xml_json_object)
        # logger.debug(f"VAT information: {vat_information}")
        # check version
        version = xml_json_object[transaction_uuid]['data']["@SoftwareVersion"]

        if Version(version) < Version(supported_version):
            raise Exception(f"Unsupported version: {xml_json_object[transaction_uuid]['data']['@SoftwareVersion']}, file: {filename}")

        items, tips = get_sub_items(xml_json_object)
        payments = get_payment_details(xml_json_object)
        service_charge = get_service_charge(xml_json_object)
        service_charge = None
        discount = get_discount(xml_json_object)
        customer = get_customer_info(xml_json_object)

        # Check if this is a void/credit note transaction
        # A credit note has: negative total, OR StornoType="StornoChild", OR DeleteType with negative amounts
        is_credit_note = False

        # Method 1: Check for negative total (most reliable)
        total_str = xml_json_object[transaction_uuid]['data'].get('@total', '0')
        try:
            total_amount = float(total_str)
            if total_amount < 0:
                is_credit_note = True
                logger.info(f"Credit note detected via negative total: {total_amount}")
        except (ValueError, TypeError):
            pass

        # Method 2: Check for StornoChild (backup detection)
        if not is_credit_note:
            storno_details = xml_json_object[transaction_uuid]['data'].get('StornoDetails', {})
            if isinstance(storno_details, dict):
                storno_type = storno_details.get('@StornoType', '')
                if storno_type == 'StornoChild':
                    is_credit_note = True
                    logger.info(f"Credit note detected via StornoType: {storno_type}")

        # BUGFIX #4: Adjust payment amounts to include discount/surcharge
        # TCPOS XML contains payment amounts BEFORE discount/surcharge adjustments
        # This causes printer to cancel check due to payment mismatch
        # BUGFIX #5: Skip payment adjustment for credit notes (they have special handling)
        if discount and payments and not is_credit_note:
            try:
                # Calculate discount/surcharge adjustment amount
                adjustment = 0.0
                discount_type = discount.get('type', '0')
                discount_percent_encoded = discount.get('percent', '000')
                discount_amount_encoded = discount.get('amount', '000')

                # Decode the values (encoded as "2500" for 25.00)
                discount_percent = float(discount_percent_encoded) / 100.0 if discount_percent_encoded != '000' else 0.0
                discount_amount = float(discount_amount_encoded) / 100.0 if discount_amount_encoded != '000' else 0.0

                # Calculate total payment sum
                payment_sum = sum(float(p['amount']) / 100.0 for p in payments)
                logger.debug(f"Original payment sum: {payment_sum}")

                if discount_percent > 0:
                    # Percentage-based: calculate adjustment from payment sum (subtotal)
                    adjustment = payment_sum * (discount_percent / 100.0)
                    logger.debug(f"Percentage {'surcharge' if discount_type == '1' else 'discount'}: {discount_percent}% = {adjustment}")
                elif discount_amount > 0:
                    # Fixed amount
                    adjustment = discount_amount
                    logger.debug(f"Fixed {'surcharge' if discount_type == '1' else 'discount'}: {adjustment}")

                # Apply adjustment (positive for surcharge, effectively positive for discount too since we're adjusting to match total)
                if adjustment > 0:
                    # For surcharge (type="1"), ADD to payment amounts
                    # For discount (type="0"), payments should already be reduced, but we need to ensure they match total
                    if discount_type == "1":
                        # Surcharge: Add to first payment
                        new_total = payment_sum + adjustment
                        logger.info(f"Adjusting payments for surcharge: {payment_sum} + {adjustment} = {new_total}")

                        # Encode and update first payment
                        first_payment_amount = float(payments[0]['amount']) / 100.0
                        adjusted_first_payment = first_payment_amount + adjustment
                        payments[0]['amount'] = f"{int(adjusted_first_payment * 100):05d}"

                        logger.debug(f"Adjusted first payment from {first_payment_amount} to {adjusted_first_payment}")

            except Exception as e:
                logger.error(f"Error adjusting payments for discount/surcharge: {e}")
                logger.error(traceback.format_exc())
                # Continue without adjustment if error occurs

        # Extract TransNum (TCPOS transaction/receipt number)
        trans_num = xml_json_object[transaction_uuid]['data'].get('@TransNum', '')

        # Extract operator code (cashier/operator ID)
        operator_code = xml_json_object[transaction_uuid]['data'].get('@operatorID', '')

        # Extract Comment field (for footer notes)
        comment = xml_json_object[transaction_uuid]['data'].get('@Comment', '')

        # is_credit_note already detected earlier (before payment adjustment)
        # No need to detect again here

        return items, payments, service_charge, tips, trans_num, is_credit_note, discount, comment, customer, operator_code

    except Exception as e:
        logger.error("Error: " + str(e))

    return None, None, None, None, None, False, None, None, None, None


def migrate_renamed_files(transactions_folder):
    """
    One-time migration: Convert old renamed files back to original names
    and create marker files instead
    """
    for root, dirs, files in os.walk(transactions_folder):
        for file in files:
            # Handle .xml.processed files
            if file.endswith('.xml.processed'):
                original_name = file[:-10]  # Remove .processed
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, original_name)
                marker_path = os.path.join(root, original_name + '.processed')

                # Rename back to original
                if not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    # Create marker
                    with open(marker_path, 'w') as f:
                        f.write(f"Migrated at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"Migrated: {file} -> {original_name}")

            # Handle .xml.skipped files
            elif file.endswith('.xml.skipped'):
                original_name = file[:-8]  # Remove .skipped
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, original_name)
                marker_path = os.path.join(root, original_name + '.skipped')

                # Rename back to original
                if not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    # Create marker
                    with open(marker_path, 'w') as f:
                        f.write(f"Migrated at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"Migrated: {file} -> {original_name}")


def files_watchdog(config, printer, stop_event=None):
    """
    Monitor a folder for TCPOS XML transaction files and process them.

    Args:
        config: Software-specific configuration dict (from config['software']['tcpos'])
        printer: Active printer instance (implements BasePrinter)
        stop_event: Optional threading.Event to signal when to stop
    """
    transactions_folder = config.get('transactions_folder')
    if not transactions_folder:
        logger.error("No transactions_folder specified in config")
        return

    # Run one-time migration
    logger.info("Running file migration...")
    migrate_renamed_files(transactions_folder)
    logger.info("File migration complete")

    while True:
        # Check if we should stop
        if stop_event and stop_event.is_set():
            logger.info("Watchdog stopping...")
            break

        for root, dirs, files in os.walk(transactions_folder):
            for file in files:
                try:
                    if file.endswith('.xml'):
                        # Skip if already processed or skipped (marker file exists)
                        marker_processed = os.path.join(root, file + '.processed')
                        marker_skipped = os.path.join(root, file + '.skipped')

                        if os.path.exists(marker_processed) or os.path.exists(marker_skipped):
                            continue  # Already processed, skip

                        logger.debug("File found: " + os.path.join(root, file))
                        items, payments, service_charge, tips, trans_num, is_credit_note, discount, comment, customer, operator_code = tcpos_parse_transaction(os.path.join(root, file))

                        if items and payments:
                            # Extract customer info from dict
                            customer_name = None
                            customer_crib = None
                            if customer:
                                customer_name = customer.get('name')
                                customer_crib = customer.get('code')

                            # Use operator code for POS name (e.g., "Operator: 1701")
                            pos_display = f"Operator: {operator_code}" if operator_code else "TCpos"

                            # Call printer's print_document method with correct parameters
                            printer.print_document(
                                items=items,
                                payments=payments,
                                service_charge=service_charge,
                                tips=tips,
                                discount=discount,
                                surcharge=None,
                                general_comment=comment if comment else "",
                                is_refund=is_credit_note,
                                receipt_number=trans_num,  # TCpos check number
                                pos_name=pos_display,  # Operator code
                                customer_name=customer_name,
                                customer_crib=customer_crib
                            )

                            # Create marker file (keep original for TCPOS refunds)
                            with open(marker_processed, 'w') as f:
                                f.write(f"Processed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                            logger.info(f"File processed: {file}")

                        else:
                            logger.debug("File skipped: " + os.path.join(root, file))
                            # Create skipped marker file
                            with open(marker_skipped, 'w') as f:
                                f.write(f"Skipped at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                            logger.info(f"File skipped: {file}")

                        time.sleep(1)

                except Exception as e:
                    logger.error("Watchdog error: " + str(e))
                    pass

        time.sleep(1)


if 0:
    tcpos_thread = threading.Thread(target=files_watchdog, daemon=True)
    tcpos_thread.start()

    while 1:
        time.sleep(1)
