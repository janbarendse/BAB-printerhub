"""
Utility script to view, test, and update Odoo credentials
Usage: python update_odoo_credentials.py
"""
import json
from cryptography.fernet import Fernet

# Use the same key as rpc_client.py
KEY = b'YjvNA1Pb7hx0v3XUXTORD-IYWBo_-MpXAsH42wz6Jzs='
cipher_suite = Fernet(KEY)
CREDS_FILE = 'odoo_credentials_encrypted.json'


def decrypt_credentials():
    """Decrypt and display current credentials"""
    try:
        with open(CREDS_FILE, 'r') as f:
            encrypted = json.load(f)

        print("\n=== Current Odoo Credentials (Decrypted) ===\n")

        decrypted = {}
        for field, value in encrypted.items():
            if field == 'pos_config_name':
                decrypted[field] = value
                print(f"{field:15} : {value}")
            else:
                decrypted_value = cipher_suite.decrypt(value.encode()).decode()
                decrypted[field] = decrypted_value

                # Mask password for security
                if field == 'password':
                    display_value = '*' * len(decrypted_value)
                else:
                    display_value = decrypted_value
                print(f"{field:15} : {display_value}")

        print("\n")
        return decrypted

    except FileNotFoundError:
        print(f"Error: {CREDS_FILE} not found!")
        return None
    except Exception as e:
        print(f"Error decrypting credentials: {e}")
        return None


def encrypt_credentials(url, database, username, password, pos_config_name):
    """Encrypt and save new credentials"""
    try:
        encrypted = {
            'url': cipher_suite.encrypt(url.encode()).decode(),
            'database': cipher_suite.encrypt(database.encode()).decode(),
            'username': cipher_suite.encrypt(username.encode()).decode(),
            'password': cipher_suite.encrypt(password.encode()).decode(),
            'pos_config_name': pos_config_name  # Not encrypted
        }

        with open(CREDS_FILE, 'w') as f:
            json.dump(encrypted, f, indent=4)

        print(f"\n✓ Credentials saved to {CREDS_FILE}")
        return True

    except Exception as e:
        print(f"Error encrypting credentials: {e}")
        return False


def test_connection(creds):
    """Test connection to Odoo with current credentials"""
    try:
        import xmlrpc.client

        print("Testing connection to Odoo...")
        print(f"URL: {creds['url']}")

        # Try to authenticate
        common = xmlrpc.client.ServerProxy(f"{creds['url']}/xmlrpc/2/common")
        uid = common.authenticate(
            creds['database'],
            creds['username'],
            creds['password'],
            {}
        )

        if uid:
            print(f"✓ Authentication successful! User ID: {uid}")

            # Try to fetch POS config
            models = xmlrpc.client.ServerProxy(f"{creds['url']}/xmlrpc/2/object")
            pos_config_ids = models.execute_kw(
                creds['database'],
                uid,
                creds['password'],
                'pos.config',
                'search',
                [[('name', '=', creds['pos_config_name'])]]
            )

            if pos_config_ids:
                print(f"✓ POS Config '{creds['pos_config_name']}' found! ID: {pos_config_ids[0]}")
                return True
            else:
                print(f"✗ POS Config '{creds['pos_config_name']}' not found!")
                print("Available POS configs:")
                all_configs = models.execute_kw(
                    creds['database'],
                    uid,
                    creds['password'],
                    'pos.config',
                    'search_read',
                    [[]],
                    {'fields': ['name']}
                )
                for cfg in all_configs:
                    print(f"  - {cfg['name']}")
                return False
        else:
            print("✗ Authentication failed!")
            return False

    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False


def main():
    """Main menu"""
    print("\n" + "="*50)
    print("    Odoo Credentials Manager")
    print("="*50)

    while True:
        print("\nOptions:")
        print("  1) View current credentials (decrypted)")
        print("  2) Test connection to Odoo")
        print("  3) Update credentials")
        print("  4) Exit")

        choice = input("\nSelect option (1-4): ").strip()

        if choice == '1':
            decrypt_credentials()

        elif choice == '2':
            creds = decrypt_credentials()
            if creds:
                test_connection(creds)

        elif choice == '3':
            print("\n=== Update Odoo Credentials ===\n")
            url = input("Odoo URL (e.g., https://yourdomain.odoo.com): ").strip()
            database = input("Database name: ").strip()
            username = input("Username (email): ").strip()
            password = input("Password: ").strip()
            pos_config = input("POS Config Name: ").strip()

            if url and database and username and password and pos_config:
                if encrypt_credentials(url, database, username, password, pos_config):
                    print("\nTesting new credentials...")
                    creds = decrypt_credentials()
                    if creds:
                        test_connection(creds)
            else:
                print("Error: All fields are required!")

        elif choice == '4':
            print("\nExiting...")
            break

        else:
            print("Invalid option!")


if __name__ == "__main__":
    main()
