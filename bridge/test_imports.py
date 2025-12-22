"""Test script to verify src/ imports work correctly"""
import sys
sys.path.insert(0, '.')

try:
    # Test importing main modules
    from src import logger_module
    from src import version
    from src.core import config_manager
    from src.core import system_tray
    from src.printers import base_printer
    from src.software import base_software
    from src.wordpress import wordpress_poller

    print("[OK] All imports successful!")
    print(f"[OK] Version: {version.VERSION}")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
