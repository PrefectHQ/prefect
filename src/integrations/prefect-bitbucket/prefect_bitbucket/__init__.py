"""Contains the credentials and repository submodules."""

from . import _version
from .credentials import BitBucketCredentials  # noqa
from .repository import BitBucketRepository  # noqa

__version__ = _version.__version__
__all__ = ["BitBucketCredentials", "BitBucketRepository"]
