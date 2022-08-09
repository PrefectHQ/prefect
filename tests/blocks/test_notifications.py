from unittest.mock import MagicMock

import cloudpickle
import pytest

from prefect import flow
from prefect.blocks.notifications import SlackWebhook
from prefect.testing.utilities import AsyncMock


class TestSlackWebhook:
    async def test_notify_async(self, monkeypatch):
        async_webhook_client_mock = AsyncMock()
        async_webhook_client_constructor_mock = MagicMock(
            return_value=async_webhook_client_mock
        )
        monkeypatch.setattr(
            "slack_sdk.webhook.async_client.AsyncWebhookClient",
            async_webhook_client_constructor_mock,
        )

        block = SlackWebhook(url="http://example.com/slack")
        await block.notify("test")

        async_webhook_client_constructor_mock.assert_called_once_with(
            url=block.url.get_secret_value()
        )
        async_webhook_client_mock.send.assert_called_once_with(text="test")

    def test_notify_sync(self, monkeypatch):
        async_webhook_client_mock = AsyncMock()
        async_webhook_client_constructor_mock = MagicMock(
            return_value=async_webhook_client_mock
        )
        monkeypatch.setattr(
            "slack_sdk.webhook.async_client.AsyncWebhookClient",
            async_webhook_client_constructor_mock,
        )

        url = "http://example.com/slack"

        @flow
        def test_flow():
            block = SlackWebhook(url=url)
            block.notify("test")

        test_flow()
        async_webhook_client_constructor_mock.assert_called_once_with(url=url)
        async_webhook_client_mock.send.assert_called_once_with(text="test")

    def test_notify_sync(self, monkeypatch):
        async_webhook_client_mock = AsyncMock()
        async_webhook_client_constructor_mock = MagicMock(
            return_value=async_webhook_client_mock
        )
        monkeypatch.setattr(
            "slack_sdk.webhook.async_client.AsyncWebhookClient",
            async_webhook_client_constructor_mock,
        )

        url = "http://example.com/slack"

        @flow
        def test_flow():
            block = SlackWebhook(url=url)
            block.notify("test")

        with pytest.warns(DeprecationWarning, match="The `SlackWebhook`"):
            test_flow()

    def test_is_picklable(self):
        block = SlackWebhook(url="http://example.com/slack")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, SlackWebhook)
