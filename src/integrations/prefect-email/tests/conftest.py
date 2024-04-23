from unittest.mock import MagicMock

import pytest

from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(autouse=True)
def prefect_db():
    with prefect_test_harness():
        yield


class EmailServerMethodsMock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, message):
        return message


@pytest.fixture
def email_server_credentials():
    email_server_credentials = MagicMock(username="someone@email.com")
    email_server_credentials.get_server.side_effect = lambda: EmailServerMethodsMock()
    return email_server_credentials


class SMTPMock(MagicMock):
    def __init__(self, server, port, context=None):
        super().__init__()
        self.server = server
        self.port = port
        self.context = context

    def login(self, username, password):
        self.username = username
        self.password = password

    def starttls(self, context=None):
        self.context = context


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr("prefect_email.credentials.SMTP", SMTPMock)
    monkeypatch.setattr("prefect_email.credentials.SMTP_SSL", SMTPMock)
