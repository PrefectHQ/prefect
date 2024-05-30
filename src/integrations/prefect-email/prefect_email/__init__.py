# pyright: reportPrivateUsage=false

from . import _version
from .credentials import EmailServerCredentials, SMTPServer, SMTPType
from .message import email_send_message

__version__ = getattr(_version, "__version__")

__all__ = ["EmailServerCredentials", "SMTPServer", "SMTPType", "email_send_message"]
