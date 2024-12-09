"""
Utilities for Python version compatibility
"""
# Please organize additions to this file by version

import sys

if sys.version_info < (3, 10):
    import importlib_metadata as importlib_metadata
    from importlib_metadata import (
        EntryPoint as EntryPoint,
        EntryPoints as EntryPoints,
        entry_points as entry_points,
    )
else:
    import importlib.metadata
    from importlib.metadata import (
        EntryPoint as EntryPoint,
        EntryPoints as EntryPoints,
        entry_points as entry_points,
    )

    importlib_metadata = importlib.metadata
