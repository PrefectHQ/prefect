from typing import cast

import pytest
from prefect_email.credentials import (
    EmailServerCredentials,
    SMTPServer,
    SMTPType,
)
from prefect_email.types import SMTPServerLike
from pydantic import SecretStr


@pytest.mark.parametrize(
    "smtp_server", ["gmail", "GMAIL", "smtp.gmail.com", "SMTP.GMAIL.COM"]
)
@pytest.mark.parametrize(
    "smtp_type, smtp_port",
    [
        ("SSL", 465),
        ("STARTTLS", 587),
        ("ssl", 465),
        ("StartTLS", 587),
        ("insecure", 25),
    ],
)
def test_email_server_credentials_get_server(
    smtp_server: SMTPServerLike, smtp_type: SMTPType, smtp_port: int
):
    server = EmailServerCredentials(
        username="username",
        password=SecretStr("password"),
        smtp_server=smtp_server,
        smtp_type=smtp_type,
    ).get_server()
    if smtp_type.value.lower() == "insecure":  # type: ignore
        assert getattr(server, "username") == "username"
        assert getattr(server, "password") == "password"
    assert getattr(server, "server").lower() == "smtp.gmail.com"
    assert getattr(server, "port") == smtp_port


def test_email_server_credentials_get_server_error(smtp: SMTPServer):
    with pytest.raises(ValueError):
        EmailServerCredentials(
            username="username",
            password=SecretStr("password"),
            smtp_type="INVALID",  # type: ignore
        ).get_server()


def test_email_server_credentials_override_smtp_port(smtp: SMTPServerLike):
    server = EmailServerCredentials(
        username="username",
        password=SecretStr("password"),
        smtp_server=SMTPServer.GMAIL,
        smtp_type=SMTPType.SSL,
        smtp_port=1234,
    ).get_server()
    assert getattr(server, "port") == 1234


def test_email_server_credentials_defaults(smtp: SMTPServerLike):
    server = EmailServerCredentials().get_server()
    assert getattr(server, "port") == 465
    assert getattr(server, "server").lower() == "smtp.gmail.com"


@pytest.mark.parametrize("smtp_type", [SMTPType.STARTTLS, "STARTTLS", 587])
def test_email_service_credentials_roundtrip_smtp_type_enum(
    smtp: SMTPServerLike, smtp_type: SMTPType
):
    email_server_credentials = EmailServerCredentials(
        smtp_server="us-smtp-outbound-1.mimecast.com",
        smtp_type=smtp_type,
        username="username",
        password=SecretStr("password"),
    )
    email_server_credentials.save("email-credentials", overwrite=True)  # type: ignore
    credentials: EmailServerCredentials = cast(
        EmailServerCredentials, EmailServerCredentials.load("email-credentials")
    )
    assert credentials.smtp_type == SMTPType.STARTTLS
    server = credentials.get_server()
    assert getattr(server, "port") == 587
