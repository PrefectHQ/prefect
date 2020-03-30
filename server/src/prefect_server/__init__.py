# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import sys as _sys

if _sys.version_info < (3, 7):
    raise ImportError("Prefect server requires Python 3.7+.")

from prefect_server.configuration import config

import prefect_server.database
import prefect_server.utilities
import prefect_server.api
import prefect_server.services

# -------------------------------------------
# versioneer - automatic versioning
from ._version import get_versions

try:
    __version__ = get_versions()["version"]
except Exception:
    __version__ = "0+unknown"

del get_versions
