"""
Fiscal utilities for NKF generation and other fiscal operations.

NKF (Number di Komprobante Fiskal) Format:
- Total length: 19 characters
- Structure:
  * Source of document (1 character): A
  * CRIB number (9 digits): e.g., 122202235
  * Cash register/printer number (2 digits): e.g., 11
  * Type of receipt/invoice (1 digit): 1, 2 (credit note), 3, 4 (credit note)
  * Sequential number (6 digits): e.g., 000001

Example: A122202235111000001
"""


def generate_nkf(nkf_config, document_type, last_order_id):
    """
    Generate NKF (Number di Komprobante Fiskal) dynamically.

    Args:
        nkf_config (dict): Dictionary containing:
            - source (str): Source of document (1 char), e.g., "A"
            - crib_number (str): CRIB number (9 digits), e.g., "122202235"
            - cash_register (str): Cash register/printer number (2 digits), e.g., "11"
        document_type (str): Type of receipt/invoice (1 digit): "1", "2", "3", or "4"
        last_order_id (int): Sequential number to be formatted as 6 digits

    Returns:
        str: Generated NKF (19 characters)

    Examples:
        >>> config = {"source": "A", "crib_number": "122202235", "cash_register": "11"}
        >>> generate_nkf(config, "1", 1)
        'A122202235111000001'

        >>> generate_nkf(config, "2", 417)
        'A122202235112000417'
    """
    # Extract configuration values
    source = nkf_config.get("source", "A")
    crib_number = nkf_config.get("crib_number", "122202235")
    cash_register = nkf_config.get("cash_register", "11")

    # Validate and format components
    # Source: 1 character
    source = str(source)[:1].upper()

    # CRIB number: 9 digits (pad with zeros if needed)
    crib_number = str(crib_number).zfill(9)[:9]

    # Cash register: 2 digits (pad with zeros if needed)
    cash_register = str(cash_register).zfill(2)[:2]

    # Document type: 1 digit (should be 1, 2, 3, or 4)
    document_type = str(document_type)[:1]

    # Sequential number: 6 digits (pad with zeros if needed)
    sequential = str(last_order_id).zfill(6)[:6]

    # Construct NKF: source + crib + register + type + sequential = 19 chars
    nkf = f"{source}{crib_number}{cash_register}{document_type}{sequential}"

    return nkf


def parse_nkf(nkf):
    """
    Parse an NKF string into its components.

    Args:
        nkf (str): NKF string (19 characters)

    Returns:
        dict: Dictionary containing parsed components

    Example:
        >>> parse_nkf("A122202235111000001")
        {
            'source': 'A',
            'crib_number': '122202235',
            'cash_register': '11',
            'document_type': '1',
            'sequential': '000001'
        }
    """
    if len(nkf) != 19:
        raise ValueError(f"Invalid NKF length: {len(nkf)} (expected 19)")

    return {
        "source": nkf[0],
        "crib_number": nkf[1:10],
        "cash_register": nkf[10:12],
        "document_type": nkf[12],
        "sequential": nkf[13:19]
    }
