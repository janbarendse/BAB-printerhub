"""
Single instance enforcement for BAB-Cloud PrintHub.

This module ensures only one instance of the application runs at a time
using Windows named mutex for cross-process synchronization.
"""

import sys
import logging

try:
    import win32event
    import win32api
    import winerror
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

logger = logging.getLogger(__name__)


class SingleInstance:
    """
    Ensures only one instance of the application runs.
    Uses Windows named mutex for cross-process synchronization.
    """

    def __init__(self, app_name="BAB_Cloud_PrintHub"):
        """
        Initialize the single instance manager.

        Args:
            app_name: Unique name for the application mutex
        """
        self.mutex_name = f"Global\\{app_name}_Mutex"
        self.mutex = None

    def acquire(self) -> bool:
        """
        Try to acquire the single instance lock.

        Returns:
            bool: True if this is the only instance, False if another exists
        """
        if not HAS_WIN32:
            logger.warning("win32api not available - single instance check disabled")
            return True  # Fail open if library not available

        try:
            self.mutex = win32event.CreateMutex(None, False, self.mutex_name)
            last_error = win32api.GetLastError()

            if last_error == winerror.ERROR_ALREADY_EXISTS:
                # Another instance is running
                logger.error("Another instance of BAB Cloud PrintHub is already running")
                return False

            # This is the first instance
            logger.info("Successfully acquired single instance lock")
            return True

        except Exception as e:
            logger.error(f"Error creating mutex: {e}")
            return True  # Fail open - allow running if error

    def release(self):
        """Release the mutex on shutdown."""
        if self.mutex and HAS_WIN32:
            try:
                win32api.CloseHandle(self.mutex)
                logger.info("Released single instance lock")
            except Exception as e:
                logger.error(f"Error releasing mutex: {e}")


def check_single_instance(app_name="BAB_Cloud_PrintHub") -> SingleInstance:
    """
    Check if another instance is running and exit if so.

    Args:
        app_name: Unique name for the application

    Returns:
        SingleInstance: Instance lock (must be kept alive until app exits)

    Raises:
        SystemExit: If another instance is already running
    """
    instance_lock = SingleInstance(app_name)

    if not instance_lock.acquire():
        print("=" * 60)
        print("ERROR: Another instance is already running!")
        print("=" * 60)
        print("BAB Cloud PrintHub is already running in the system tray.")
        print("Please close the existing instance before starting a new one.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    return instance_lock
