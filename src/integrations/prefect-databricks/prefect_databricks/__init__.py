from . import _version
from .credentials import DatabricksCredentials  # noqa

__version__ = _version.get_versions()["version"]
