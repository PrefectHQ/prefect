# pyright: reportPrivateUsage=false
from . import _version
from .credentials import GitHubCredentials  # noqa
from .repository import GitHubRepository  # noqa

__all__ = ["GitHubCredentials", "GitHubRepository"]

__version__ = getattr(_version, "__version__")
