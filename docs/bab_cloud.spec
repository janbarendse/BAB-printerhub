# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BAB-Cloud PrintHub

This spec file builds a Windows executable for the BAB-Cloud PrintHub application.
It includes all necessary dependencies, data files, and configuration.

Build with: pyinstaller --clean --noconfirm bab_cloud.spec
"""

block_cipher = None

a = Analysis(
    ['bridge\\src\\fiscal_printer_hub.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Application icon and branding
        ('bridge\\logo.png', '.'),

        # Configuration template
        ('bridge\\config.json', '.'),

        # Include all package folders from src/
        ('bridge\\src\\core', 'src\\core'),
        ('bridge\\src\\software', 'src\\software'),
        ('bridge\\src\\printers', 'src\\printers'),
        ('bridge\\src\\wordpress', 'src\\wordpress'),
    ],
    hiddenimports=[
        # Webview and UI
        'pywebview',
        'pywebview.platforms.winforms',
        'webview',

        # Windows integration
        'win32event',
        'win32api',
        'winerror',
        'pythonnet',
        'clr',

        # Cryptography for Odoo credentials
        'cryptography',
        'cryptography.fernet',

        # XML parsing for Odoo and TCPOS
        'xmltodict',

        # System tray
        'pystray',
        'pystray._win32',

        # Image processing
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',

        # HTTP requests
        'requests',
        'urllib3',

        # Serial communication
        'serial',
        'serial.tools',
        'serial.tools.list_ports',

        # Date/time
        'dateutil',
        'dateutil.parser',

        # Standard library imports that sometimes need explicit inclusion
        'queue',
        'threading',
        'json',
        'logging',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'notebook',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BAB_Cloud',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window - runs as system tray app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='bridge\\logo.png',  # Application icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BAB_Cloud',
)
