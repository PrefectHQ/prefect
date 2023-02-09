"""
WARNING: This module is deprecated and exists only for backwards compatibility.
         See `prefect.server` instead.
"""

import warnings
import sys
import inspect
from prefect._internal.compatibility.deprecated import generate_deprecation_message

warnings.warn(
    generate_deprecation_message(
        name="The `prefect.orion` module",
        start_date="Feb 2023",
        help="Use `prefect.server` instead.",
    ),
    DeprecationWarning,
    stacklevel=2,
)

import prefect.server

# Inject all of the new submodules into the sys.modules cache with the old names;
# this provides backwards compatibility for `import prefect.orion.<name>`
for name, module in inspect.getmembers(prefect.server, inspect.ismodule):
    sys.modules["prefect.orion.{name}"] = module


def __getattr__(name):
    # Forward all attribute retrieval to the new module; this provides backwards
    # compatibility for `from prefect.orion import schemas` and retrieval of other
    # non-module attributes
    return getattr(prefect.server, name)
