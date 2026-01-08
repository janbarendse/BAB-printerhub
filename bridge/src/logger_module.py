"""
Centralized logging configuration for BAB-Cloud PrintHub.

Provides a configured logger instance that writes to both console and file.
"""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# Determine if running as compiled executable
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

# Determine base directory
# Priority: compiled executable > environment variable > source location
if _is_compiled():
    # Running as compiled executable - ALWAYS use exe directory (ignore BAB_UI_BASE)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running from source - check for environment variable override
    _env_base = os.environ.get("BAB_UI_BASE")
    if _env_base:
        BASE_DIR = _env_base.strip()
    else:
        # Running as script - go up 2 levels from src/logger_module.py to bridge/
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create logger
logger = logging.getLogger('BAB_Cloud_PrintHub')
logger.setLevel(logging.DEBUG)

# Create formatters
detailed_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

simple_formatter = logging.Formatter(
    '%(levelname)s - %(message)s'
)

def _load_config_log_level():
    config_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as handle:
            config = json.load(handle)
        level_name = str(config.get('system', {}).get('log_level', 'INFO')).upper()
    except Exception:
        level_name = 'INFO'

    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    return level_map.get(level_name, logging.INFO)


# File handler (with rotation)
log_file = os.path.join(BASE_DIR, 'log.log')
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(_load_config_log_level())
file_handler.setFormatter(detailed_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)

# Add handlers to logger (avoid duplicates on re-import)
_added_handlers = False
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    _added_handlers = True

# Prevent logging from propagating to root logger
logger.propagate = False

if _added_handlers:
    logger.info("Logger initialized")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Base directory: {BASE_DIR}")
    logger.info(f"Is compiled: {_is_compiled()}")
