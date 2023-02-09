"""
WARNING: This module is deprecated and exists only for backwards compatibility
"""

import warnings
from prefect._internal.compatibility.deprecated import generate_deprecation_message

warnings.warn(
    generate_deprecation_message(
        "The `prefect.orion` module",
        start_date="Feb 2023",
        help="Use `prefect.server` instead.",
    ),
    DeprecationWarning,
    stacklevel=2,
)

from prefect.server import *

__all__ = ["schemas"]
