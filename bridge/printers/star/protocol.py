"""
CTS310ii Fiscal Printer Protocol Constants

Based on the protocol specification:
MHI_Programacion_CW_(EN).pdf

This module contains all protocol-related constants used for
communication with the CTS310ii fiscal printer.
"""

# Protocol control characters (in hex string format)
STX = "02"  # Start of transmission
ETX = "03"  # End of transmission
ACK = "06"  # Positive answer
BEL = "07"  # Intermediate response
NAK = "15"  # Negative answer
FS = "1C"   # Field separator

# Tax ID mapping (VAT percentage to printer tax ID)
tax_ids = {
    "6": "1",  # 6% VAT -> Tax ID 1
    "7": "2",  # 7% VAT -> Tax ID 2
    "9": "3"   # 9% VAT -> Tax ID 3
}

# Payment types
payment_types = {
    "void_pay/donation": "0",
    "pay/donation": "1",
}

# Payment methods
payment_methods = {
    "cash": "00",
    "check": "01",
    "credit_card": "02",
    "debit_card": "03",
    "credit_note": "04",
    "coupon": "05",
    "other_1": "06",
    "other_2": "07",
    "other_3": "08",
    "other_4": "09",
    "donations": "10",
}

# Discount/Surcharge/Service charge types
discount_surcharge_types = {
    "discount": "0",
    "surcharge": "1",
    "service_charge": "2",
}

# Response codes from printer
response_codes = {
    "0000": "Last command successful.",
    "0101": "Command invalid in the current state.",
    "0102": "Command invalid in the current document.",
    "0103": "Service jumper connected.",
    "0105": "Command requires service jumper.",
    "0107": "Invalid command.",
    "0108": "Command invalid through USB port.",
    "0109": "Command missing mandatory field.",
    "0110": "Invalid field length.",
    "0111": "Field value is invalid or out of range.",
    "0112": "Inactive TAX rate.",
    "0202": "Printing device out of line.",
    "0204": "Printing device out of paper.",
    "0205": "Invalid speed.",
    "0301": "Set fiscal info error.",
    "0302": "Set date error.",
    "0303": "Invalid date.",
    "0402": "CRIB cannot be modified.",
    "0501": "Transaction memory full.",
    "0503": "Transaction memory not connected",
    "0504": "Read/Write error on transaction memory.",
    "0505": "Invalid transaction memory.",
    "0601": "Command invalid outside of fiscal period.",
    "0602": "Fiscal period not started.",
    "0603": "Fiscal memory full.",
    "0604": "Fiscal memory not connected.",
    "0605": "Invalid fiscal memory.",
    "0606": "Command requires a Z report.",
    "0607": "Cannot find document.",
    "0608": "Fiscal period empty.",
    "0609": "Requested period empty.",
    "060A": "No more data is available.",
    "060B": "No more Z reports can be printed this day.",
    "060C": "Z report could not be saved.",
    "0701": "Total must be greater than zero.",
    "0801": "Reached comment line number limit.",
    "0901": "Reached no sale document line number limit.",
    "FFF0": "Checksum error in set fiscal info command",
    "FFF1": "Missing Checksum in set fiscal info command",
    "FFFF": "Unknown error.",
}

# Printer state codes
states_codes = {
    "0": "Standby",
    "1": "Start of sale",
    "2": "Sale",
    "3": "Subtotal",
    "4": "Payment",
    "5": "End of sale",
    "6": "Non Fiscal",
    "7": "Reserved",
    "8": "Error",
    "9": "Start of return",
    "10": "Return",
    "11": "Reading fiscal info",
    "12": "Storing logo",
    "13": "Read only",
}

# Serial communication settings
DEFAULT_BAUD_RATE = 9600
DEFAULT_SERIAL_TIMEOUT = 5  # seconds
