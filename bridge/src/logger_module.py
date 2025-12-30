"""
Centralized logging configuration for BAB-Cloud PrintHub.

Provides a configured logger instance that writes to both console and file.
"""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# Determine base directory
_env_base = os.environ.get("BAB_UI_BASE")
if _env_base:
    BASE_DIR = _env_base.strip()
elif getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = os.path.dirname(sys.executable)
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
