from enum import Enum


class SMTPType(Enum):
    """
    Protocols used to secure email transmissions.
    """

    SSL = 465
    STARTTLS = 587
    INSECURE = 25

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            return getattr(cls, value.upper())


class SMTPServer(Enum):
    """
    Server used to send email.
    """

    AOL = "smtp.aol.com"
    ATT = "smtp.mail.att.net"
    COMCAST = "smtp.comcast.net"
    ICLOUD = "smtp.mail.me.com"
    GMAIL = "smtp.gmail.com"
    OUTLOOK = "smtp-mail.outlook.com"
    YAHOO = "smtp.mail.yahoo.com"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            return getattr(cls, value.upper())
