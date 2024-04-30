from . import _version
from .credentials import GitLabCredentials
from .repositories import GitLabRepository

__version__ = _version.__version__
__all__ = ["GitLabRepository", "GitLabCredentials"]
