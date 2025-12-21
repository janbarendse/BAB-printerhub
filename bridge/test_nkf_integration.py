"""
Test script to verify NKF integration in all printer drivers.
"""

import json
from core.fiscal_utils import generate_nkf, parse_nkf

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

print("=" * 70)
print("NKF INTEGRATION TEST")
print("=" * 70)

# Test 1: Verify config structure
print("\n1. Config Structure:")
print(f"   NKF Config: {config['client']['NKF']}")
print(f"   Active Software: {config['software']['active']}")
print(f"   Last Order ID: {config['software']['odoo']['last_order_id']}")

# Test 2: Generate NKF for different document types
print("\n2. NKF Generation Tests:")
nkf_config = config['client']['NKF']
last_order_id = config['software']['odoo']['last_order_id']

for doc_type in ['1', '2', '3', '4']:
    nkf = generate_nkf(nkf_config, doc_type, last_order_id)
    parsed = parse_nkf(nkf)
    doc_names = {'1': 'Invoice Final Consumer', '2': 'Invoice Fiscal Credit',
                 '3': 'Credit Note Final Consumer', '4': 'Credit Note Fiscal'}
    print(f"   Type {doc_type} ({doc_names[doc_type]}): {nkf}")
    print(f"      Parsed: {parsed}")

# Test 3: Verify printer driver imports
print("\n3. Printer Driver Import Tests:")
try:
    from printers.cts310ii.cts310ii_driver import CTS310iiDriver
    print("   [OK] CTS310ii driver imports successfully")
except Exception as e:
    print(f"   [FAIL] CTS310ii driver import failed: {e}")

try:
    from printers.citizen.citizen_driver import CitizenDriver
    print("   [OK] Citizen driver imports successfully")
except Exception as e:
    print(f"   [FAIL] Citizen driver import failed: {e}")

try:
    from printers.star.star_driver import StarDriver
    print("   [OK] Star driver imports successfully")
except Exception as e:
    print(f"   [FAIL] Star driver import failed: {e}")

# Test 4: Mock driver initialization
print("\n4. Driver Initialization Test:")
try:
    from printers.cts310ii.cts310ii_driver import CTS310iiDriver
    driver_config = {
        'baud_rate': 9600,
        'serial_timeout': 5,
        'debug': True,
        'client': config['client'],
        'miscellaneous': config['miscellaneous'],
        'software': config['software']
    }
    driver = CTS310iiDriver(driver_config)
    print(f"   [OK] CTS310ii driver initialized: {driver}")

    # Verify the driver can access the config
    nkf_cfg = driver.client_config.get('NKF', {})
    print(f"   [OK] Driver can access NKF config: {nkf_cfg}")

    # Test NKF generation within driver context
    from core.fiscal_utils import generate_nkf
    software_config = driver.config.get('software', {})
    active_software = software_config.get('active', 'odoo')
    last_order = software_config.get(active_software, {}).get('last_order_id', 0)
    test_nkf = generate_nkf(nkf_cfg, '1', last_order)
    print(f"   [OK] Driver context NKF generation: {test_nkf}")

except Exception as e:
    print(f"   [FAIL] Driver initialization failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
