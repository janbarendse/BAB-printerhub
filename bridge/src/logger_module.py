"""
Centralized logging configuration for BAB-Cloud PrintHub.

Provides a configured logger instance that writes to both console and file.
"""

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

# File handler (with rotation)
log_file = os.path.join(BASE_DIR, 'log.log')
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(detailed_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Prevent logging from propagating to root logger
logger.propagate = False

logger.info("Logger initialized")
