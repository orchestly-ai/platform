"""
Enterprise license validation.

Reads ORCHESTLY_LICENSE_KEY from environment and validates it.
In the current implementation, any key with the prefix 'orch_ent_' is
considered valid. Future versions will validate against a license server.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_LICENSE_PREFIX = "orch_ent_"


def get_license_key() -> Optional[str]:
    """Return the configured enterprise license key, or None."""
    return os.environ.get("ORCHESTLY_LICENSE_KEY")


def has_enterprise_license() -> bool:
    """Check whether a valid enterprise license key is configured."""
    key = get_license_key()
    if not key:
        return False
    # Basic prefix validation — future: verify signature / call license server
    return key.startswith(_LICENSE_PREFIX)


def get_license_status() -> dict:
    """Return a dict describing the current license status."""
    key = get_license_key()
    if not key:
        return {
            "edition": "community",
            "licensed": False,
            "message": "No enterprise license key configured. Set ORCHESTLY_LICENSE_KEY to activate enterprise features.",
        }
    if has_enterprise_license():
        # Mask most of the key for display
        masked = key[:len(_LICENSE_PREFIX) + 4] + "..." + key[-4:] if len(key) > len(_LICENSE_PREFIX) + 8 else key[:len(_LICENSE_PREFIX)] + "****"
        return {
            "edition": "enterprise",
            "licensed": True,
            "key_hint": masked,
            "message": "Enterprise license active.",
        }
    return {
        "edition": "community",
        "licensed": False,
        "message": "Invalid enterprise license key format. Keys must start with 'orch_ent_'.",
    }
