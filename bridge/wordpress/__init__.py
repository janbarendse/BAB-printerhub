"""
WordPress Z-Report Poller Package

Temporary bridge to WordPress portal for remote Z-report triggers.
This will be replaced by the Portal system in a future release.
"""

from .wordpress_poller import start_wordpress_poller, WordPressPoller

__all__ = ['start_wordpress_poller', 'WordPressPoller']
