from unittest.mock import MagicMock

import pytest

from prefect.testing.utilities import AsyncMock, prefect_test_harness


@pytest.fixture(autouse=True, scope="session")
def prefect_db():
    with prefect_test_harness():
        yield


@pytest.fixture
def slack_credentials():
    slack_credentials_mock = MagicMock()
    chat_postMessage_mock = AsyncMock()
    chat_postMessage_mock.return_value = MagicMock(data=dict())
    slack_credentials_mock.get_client.return_value = MagicMock(
        chat_postMessage=chat_postMessage_mock
    )
    return slack_credentials_mock


@pytest.fixture
def slack_webhook():
    slack_webhook_mock = MagicMock()
    slack_webhook_mock.get_client.return_value = AsyncMock()
    return slack_webhook_mock
