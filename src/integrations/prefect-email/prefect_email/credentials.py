"""Credential classes used to perform authenticated interactions with email services"""

import ssl
from functools import partial
from smtplib import SMTP, SMTP_SSL
from typing import Optional, Union

from pydantic import Field, SecretStr

from prefect.blocks.core import Block
from prefect_email.types import SMTPServer, SMTPType


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
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/82bc6ed16ca42a2252a5512c72233a253b8a58eb-250x250.png"  # type: ignore
    _documentation_url = "https://prefecthq.github.io/prefect-email/credentials/#prefect_email.credentials.EmailServerCredentials"  # type: ignore

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
    smtp_server: SMTPServer = Field(
        default=SMTPServer.GMAIL,
        description=(
            "Either the hostname of the SMTP server, or one of the "
            "keys from the built-in SMTPServer Enum members, like 'gmail'."
        ),
        title="SMTP Server",
    )
    smtp_type: SMTPType = Field(
        default=SMTPType.SSL,
        description=("Either 'SSL', 'STARTTLS', or 'INSECURE'."),
        title="SMTP Type",
    )
    smtp_port: Optional[int] = Field(
        default=None,
        description=("If provided, overrides the smtp_type's default port number."),
        title="SMTP Port",
    )

    def get_server(self) -> Union[SMTP, SMTP_SSL]:
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
        if self.smtp_type == SMTPType.INSECURE:
            server = SMTP(
                host=(
                    self.smtp_server
                    if isinstance(self.smtp_server, str)
                    else self.smtp_server.value
                ),
                port=(
                    self.smtp_port
                    if self.smtp_port is not None
                    else self.smtp_type.value
                ),
            )
        elif self.smtp_type == SMTPType.SSL:
            server = SMTP_SSL(
                host=(
                    self.smtp_server
                    if isinstance(self.smtp_server, str)
                    else self.smtp_server.value
                ),
                port=(
                    self.smtp_port
                    if self.smtp_port is not None
                    else self.smtp_type.value
                ),
                context=ssl.create_default_context(),
            )
        else:
            server = SMTP(
                host=(
                    self.smtp_server
                    if isinstance(self.smtp_server, str)
                    else self.smtp_server.value
                ),
                port=(
                    self.smtp_port
                    if self.smtp_port is not None
                    else self.smtp_type.value
                ),
            )
            server.starttls(context=ssl.create_default_context())
        if self.username is not None:
            server.login(self.username, self.password.get_secret_value())
        return server
