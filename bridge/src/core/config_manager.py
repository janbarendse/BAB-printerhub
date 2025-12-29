"""
Configuration management for BAB-Cloud PrintHub.

This module handles loading, validating, and saving the central config.json file.
"""

import json
import os
import sys
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# Determine base directory (works for dev, UI runtime, and frozen/PyInstaller)
_env_base = os.environ.get("BAB_UI_BASE")
if _env_base:
    BASE_DIR = _env_base
elif getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script from src/core/ directory
    # Need to go up 3 levels: core -> src -> bridge
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from config.json.

    Args:
        config_path: Optional path to config file (defaults to BASE_DIR/config.json)

    Returns:
        dict: Configuration dictionary

    Raises:
        FileNotFoundError: If config file not found
        json.JSONDecodeError: If config file is invalid JSON
    """
    path = config_path or CONFIG_FILE

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {path}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise


def save_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """
    Save configuration to config.json atomically.

    Args:
        config: Configuration dictionary
        config_path: Optional path to config file

    Returns:
        bool: True if saved successfully

    Raises:
        Exception: If save fails
    """
    path = config_path or CONFIG_FILE

    try:
        # Write to temporary file first (atomic operation)
        temp_path = path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Replace original file
        if os.path.exists(path):
            os.replace(temp_path, path)
        else:
            os.rename(temp_path, path)

        logger.info(f"Configuration saved to {path}")
        return True

    except Exception as e:
        logger.error(f"Error saving config: {e}")
        # Clean up temp file if exists
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise


def get_software_config(config: Dict[str, Any], software_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get configuration for a specific software integration.

    Args:
        config: Full configuration dictionary
        software_name: Name of software (defaults to active software)

    Returns:
        dict: Software-specific configuration

    Raises:
        KeyError: If software not found in config
    """
    if software_name is None:
        software_name = config['software']['active']

    if software_name not in config['software']:
        raise KeyError(f"Software '{software_name}' not found in config")

    return config['software'][software_name]


def get_printer_config(config: Dict[str, Any], printer_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get configuration for a specific printer driver.

    Args:
        config: Full configuration dictionary
        printer_name: Name of printer (defaults to active printer)

    Returns:
        dict: Printer-specific configuration

    Raises:
        KeyError: If printer not found in config
    """
    if printer_name is None:
        printer_name = config['printer']['active']

    if printer_name not in config['printer']:
        raise KeyError(f"Printer '{printer_name}' not found in config")

    return config['printer'][printer_name]


def get_last_order_id(config: Dict[str, Any], software_name: Optional[str] = None) -> int:
    """
    Get the last processed order ID for a software integration.

    Args:
        config: Full configuration dictionary
        software_name: Name of software (defaults to active software)

    Returns:
        int: Last order ID (0 if not set)
    """
    try:
        software_config = get_software_config(config, software_name)
        return software_config.get('last_order_id', 0)
    except KeyError:
        logger.warning(f"Could not get last_order_id for {software_name}")
        return 0


def set_last_order_id(config: Dict[str, Any], order_id: int, software_name: Optional[str] = None, save: bool = True) -> bool:
    """
    Update the last processed order ID for a software integration.

    Args:
        config: Full configuration dictionary
        order_id: New last order ID
        software_name: Name of software (defaults to active software)
        save: Whether to save config to disk (default: True)

    Returns:
        bool: True if updated successfully
    """
    try:
        if software_name is None:
            software_name = config['software']['active']

        config['software'][software_name]['last_order_id'] = order_id
        logger.debug(f"Updated last_order_id for {software_name}: {order_id}")

        if save:
            return save_config(config)

        return True

    except Exception as e:
        logger.error(f"Error setting last_order_id: {e}")
        return False


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration structure.

    Args:
        config: Configuration dictionary to validate

    Returns:
        bool: True if valid

    Raises:
        ValueError: If configuration is invalid
    """
    # Check required top-level keys
    required_keys = ['software', 'printer', 'client', 'miscellaneous']
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    # Check software configuration
    if 'active' not in config['software']:
        raise ValueError("Missing software.active in config")

    active_software = config['software']['active']
    if active_software not in config['software']:
        raise ValueError(f"Active software '{active_software}' not found in config.software")

    # Check printer configuration
    if 'active' not in config['printer']:
        raise ValueError("Missing printer.active in config")

    active_printer = config['printer']['active']
    if active_printer not in config['printer']:
        raise ValueError(f"Active printer '{active_printer}' not found in config.printer")

    logger.info("Configuration validation passed")
    return True


def get_base_dir() -> str:
    """
    Get the base directory for the application.

    Returns:
        str: Base directory path
    """
    return BASE_DIR


def get_config_path() -> str:
    """
    Get the path to the config file.

    Returns:
        str: Config file path
    """
    return CONFIG_FILE
