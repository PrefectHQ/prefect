from unittest.mock import MagicMock

import cloudpickle

from prefect import flow
from prefect.blocks.notifications import MSTeamsWebhook, SlackWebhook
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

    def test_is_picklable(self):
        block = SlackWebhook(url="http://example.com/slack")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, SlackWebhook)


class TestMSTeamsWebhook:
    async def test_notify_async(self, monkeypatch):
        async_webhook_client_mock = AsyncMock()
        async_webhook_client_constructor_mock = MagicMock(
            return_value=async_webhook_client_mock
        )
        monkeypatch.setattr(
            "pymsteams.async_connectorcard",
            async_webhook_client_constructor_mock,
        )

        url = "http://example.com/teams"
        block = MSTeamsWebhook(url=url)
        await block.notify("test")

        async_webhook_client_constructor_mock.assert_called_once_with(
            block.url.get_secret_value()
        )
        async_webhook_client_mock.text.assert_called_once_with("test")
        async_webhook_client_mock.send.assert_called_once_with()

    def test_notify_sync(self, monkeypatch):
        async_webhook_client_mock = AsyncMock()
        async_webhook_client_constructor_mock = MagicMock(
            return_value=async_webhook_client_mock
        )
        monkeypatch.setattr(
            "pymsteams.async_connectorcard",
            async_webhook_client_constructor_mock,
        )

        @flow
        def test_flow():
            url = "http://example.com/teams"
            block = MSTeamsWebhook(url=url)
            block.notify("test")

        test_flow()
        url = "http://example.com/teams"
        async_webhook_client_constructor_mock.assert_called_once_with(url)
        async_webhook_client_mock.text.assert_called_once_with("test")
        async_webhook_client_mock.send.assert_called_once_with()

    def test_is_picklable(self):
        block = MSTeamsWebhook(url="http://example.com/teams")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, MSTeamsWebhook)
