"""
Device ID generation and persistence for SDK telemetry.

The device ID is an anonymous identifier used to correlate events
from the same installation without identifying the user.
"""

import os
from pathlib import Path
from uuid import uuid4

from prefect.settings import get_current_settings


def _get_device_id_path() -> Path:
    """Get the path to the device ID file."""
    settings = get_current_settings()
    return settings.home / ".sdk_telemetry" / "device_id"


def get_or_create_device_id() -> str:
    """
    Get the existing device ID or create a new one.

    The device ID is stored in $PREFECT_HOME/.sdk_telemetry/device_id

    Returns:
        A UUID string identifying this installation
    """
    device_id_path = _get_device_id_path()

    # Try to read existing device ID
    if device_id_path.exists():
        try:
            device_id = device_id_path.read_text().strip()
            if device_id:
                return device_id
        except Exception:
            pass

    # Generate new device ID
    device_id = str(uuid4())

    # Persist device ID
    try:
        device_id_path.parent.mkdir(parents=True, exist_ok=True)
        device_id_path.write_text(device_id)
        # Set restrictive permissions (owner read/write only)
        os.chmod(device_id_path, 0o600)
    except Exception:
        # If we can't persist, still return the generated ID
        # (it will be regenerated next time)
        pass

    return device_id
