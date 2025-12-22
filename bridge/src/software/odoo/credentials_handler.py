"""
Odoo credentials encryption/decryption handler.

This module handles loading and decrypting Odoo credentials from the encrypted JSON file.
Uses Fernet symmetric encryption to protect sensitive credentials at rest.
"""

import json
import os
from typing import Dict
from cryptography.fernet import Fernet


# Hardcoded encryption key (same as original)
ENCRYPTION_KEY = b'YjvNA1Pb7hx0v3XUXTORD-IYWBo_-MpXAsH42wz6Jzs='


def load_credentials(base_dir: str, filename: str = 'odoo_credentials_encrypted.json') -> Dict[str, str]:
    """
    Load and decrypt Odoo credentials from encrypted JSON file.

    Args:
        base_dir: Base directory path where credentials file is located
        filename: Name of the encrypted credentials file (default: odoo_credentials_encrypted.json)

    Returns:
        dict: Decrypted credentials containing:
            - url: Odoo server URL
            - database: Database name
            - username: Odoo username
            - password: Odoo password
            - pos_config_name: POS configuration name (not encrypted)

    Raises:
        FileNotFoundError: If credentials file not found
        json.JSONDecodeError: If credentials file is invalid JSON
        Exception: If decryption fails
    """
    filepath = os.path.join(base_dir, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Credentials file not found: {filepath}")

    # Initialize cipher
    cipher_suite = Fernet(ENCRYPTION_KEY)

    # Load encrypted credentials
    with open(filepath, 'r', encoding='utf-8') as file:
        encrypted_credentials = json.load(file)

    # Decrypt credentials
    decrypted_credentials = {}
    for field, value in encrypted_credentials.items():
        if field == 'pos_config_name':
            # POS config name is stored in plaintext
            decrypted_credentials[field] = value
        else:
            # All other fields are encrypted
            decrypted_credentials[field] = cipher_suite.decrypt(value.encode()).decode()

    return decrypted_credentials
