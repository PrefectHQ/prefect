from unittest.mock import MagicMock

import cloudpickle

from prefect.blocks.notifications import SlackWebhook
from prefect.testing.utilities import AsyncMock


class TestSlackWebhook:
    async def test_notify(self, monkeypatch):
        async_webhook_client_mock = AsyncMock()
        async_webhook_client_constructor_mock = MagicMock(
            return_value=async_webhook_client_mock
        )
        monkeypatch.setattr(
            "prefect.blocks.notifications.AsyncWebhookClient",
            async_webhook_client_constructor_mock,
        )

        block = SlackWebhook(url="http://example.com/slack")
        await block.notify("test")

        async_webhook_client_constructor_mock.assert_called_once_with(url=block.url)
        async_webhook_client_mock.send.assert_called_once_with(text="test")

    def test_is_picklable(self):
        block = SlackWebhook(url="http://example.com/slack")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, SlackWebhook)
