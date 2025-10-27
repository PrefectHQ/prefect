"""
Utilities for Python version compatibility
"""

# Please organize additions to this file by version
import warnings
import importlib.metadata
from importlib.metadata import (
    EntryPoint as EntryPoint,
    EntryPoints as EntryPoints,
    entry_points as entry_points,
)

importlib_metadata = importlib.metadata

warnings.warn(
    "The prefect.utilities.compat module is deprecated. "
    "Use importlib.metadata directly instead.",
    DeprecationWarning,
    stacklevel=2,
)
