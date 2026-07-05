"""Compatibility wrapper for API-key storage.

The implementation lives in settings.py because it also stores non-secret app
preferences. This module gives the project the explicit key_storage.py file
that extension/app integrations usually look for.
"""

from settings import load_api_key, save_api_key


__all__ = ["load_api_key", "save_api_key"]
