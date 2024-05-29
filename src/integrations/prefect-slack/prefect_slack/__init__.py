# pyright: reportPrivateUsage=false

from . import _version
from .credentials import SlackCredentials, SlackWebhook  # noqa

__all__ = ["SlackCredentials", "SlackWebhook"]

__version__ = getattr(_version, "__version__")
