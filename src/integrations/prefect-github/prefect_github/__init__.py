from . import _version
from .credentials import GitHubCredentials  # noqa
from .repository import GitHubRepository  # noqa

__version__ = _version.get_versions()["version"]
