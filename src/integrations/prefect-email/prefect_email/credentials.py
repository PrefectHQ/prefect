"""Credential classes used to perform authenticated interactions with email services"""

import ssl
from enum import Enum
from functools import partial
from smtplib import SMTP, SMTP_SSL
from typing import Optional, Union

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.core import Block

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretStr, validator
else:
    from pydantic import Field, SecretStr, validator


class SMTPType(Enum):
    """
    Protocols used to secure email transmissions.
    """

    SSL = 465
    STARTTLS = 587
    INSECURE = 25


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


def _cast_to_enum(obj: Union[str, SMTPType], enum: Enum, restrict: bool = False):
    """
    Casts string to an enum member, if valid; else returns the input
    obj, or raises a ValueError if restrict.

    Args:
        obj: A member's name of the enum.
        enum: An Enum class.
        restrict: Whether to only allow passing members from the enum.

    Returns:
        A member of the enum.
    """
    if isinstance(obj, enum):
        # if already an enum member, continue
        return obj
    valid_enums = list(enum.__members__)

    # capitalize and try to match an enum member
    if obj.upper() not in valid_enums:
        if restrict:
            raise ValueError(f"Must be one of {valid_enums}; got {obj!r}")
        else:
            # primarily used for SMTPServer so that users
            # can pass in their custom servers not listed
            # as one of the SMTPServer Enum values.
            return obj
    else:
        return getattr(enum, obj.upper())


class EmailServerCredentials(Block):
    """
    Block used to manage generic email server authentication.
    It is recommended you use a
    [Google App Password](https://support.google.com/accounts/answer/185833)
    if you use Gmail.

    Attributes:
        username: The username to use for authentication to the server.
            Unnecessary if SMTP login is not required.
        password: The password to use for authentication to the server.
            Unnecessary if SMTP login is not required.
        smtp_server: Either the hostname of the SMTP server, or one of the
            keys from the built-in SMTPServer Enum members, like "gmail".
        smtp_type: Either "SSL", "STARTTLS", or "INSECURE".
        smtp_port: If provided, overrides the smtp_type's default port number.

    Example:
        Load stored email server credentials:
        ```python
        from prefect_email import EmailServerCredentials
        email_credentials_block = EmailServerCredentials.load("BLOCK_NAME")
        ```
    """  # noqa E501

    _block_type_name = "Email Server Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/82bc6ed16ca42a2252a5512c72233a253b8a58eb-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-email/credentials/#prefect_email.credentials.EmailServerCredentials"  # noqa

    username: Optional[str] = Field(
        default=None,
        description=(
            "The username to use for authentication to the server. "
            "Unnecessary if SMTP login is not required."
        ),
    )
    password: SecretStr = Field(
        default_factory=partial(SecretStr, ""),
        description=(
            "The password to use for authentication to the server. "
            "Unnecessary if SMTP login is not required."
        ),
    )
    smtp_server: Union[SMTPServer, str] = Field(
        default=SMTPServer.GMAIL,
        description=(
            "Either the hostname of the SMTP server, or one of the "
            "keys from the built-in SMTPServer Enum members, like 'gmail'."
        ),
        title="SMTP Server",
    )
    smtp_type: Union[SMTPType, str] = Field(
        default=SMTPType.SSL,
        description=("Either 'SSL', 'STARTTLS', or 'INSECURE'."),
        title="SMTP Type",
    )
    smtp_port: Optional[int] = Field(
        default=None,
        description=("If provided, overrides the smtp_type's default port number."),
        title="SMTP Port",
    )

    @validator("smtp_server", pre=True)
    def _cast_smtp_server(cls, value):
        """
        Cast the smtp_server to an SMTPServer Enum member, if valid.
        """
        return _cast_to_enum(value, SMTPServer)

    @validator("smtp_type", pre=True)
    def _cast_smtp_type(cls, value):
        """
        Cast the smtp_type to an SMTPType Enum member, if valid.
        """
        if isinstance(value, int):
            return SMTPType(value)
        return _cast_to_enum(value, SMTPType, restrict=True)

    def get_server(self) -> SMTP:
        """
        Gets an authenticated SMTP server.

        Returns:
            SMTP: An authenticated SMTP server.

        Example:
            Gets a GMail SMTP server through defaults.
            ```python
            from prefect import flow
            from prefect_email import EmailServerCredentials

            @flow
            def example_get_server_flow():
                email_server_credentials = EmailServerCredentials(
                    username="username@gmail.com",
                    password="password",
                )
                server = email_server_credentials.get_server()
                return server

            example_get_server_flow()
            ```
        """
        smtp_server = self.smtp_server
        if isinstance(smtp_server, SMTPServer):
            smtp_server = smtp_server.value

        smtp_type = self.smtp_type
        smtp_port = self.smtp_port
        if smtp_port is None:
            smtp_port = smtp_type.value

        if smtp_type == SMTPType.INSECURE:
            server = SMTP(smtp_server, smtp_port)
        else:
            context = ssl.create_default_context()
            if smtp_type == SMTPType.SSL:
                server = SMTP_SSL(smtp_server, smtp_port, context=context)
            elif smtp_type == SMTPType.STARTTLS:
                server = SMTP(smtp_server, smtp_port)
                server.starttls(context=context)
            if self.username is not None:
                server.login(self.username, self.password.get_secret_value())

        return server
