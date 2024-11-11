from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_slack import SlackCredentials, SlackWebhook
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook.async_client import AsyncWebhookClient
from slack_sdk.webhook.webhook_response import WebhookResponse


def test_slack_credentials():
    assert isinstance(SlackCredentials(token="xoxb-xxxx").get_client(), AsyncWebClient)


def test_slack_webhook():
    assert isinstance(
        SlackWebhook(url="https://hooks.slack.com/xxxx").get_client(),
        AsyncWebhookClient,
    )


@pytest.mark.skipif(
    condition=not hasattr(SlackWebhook, "raise_on_failure"),
    reason="The raise_on_failure option is only implemented in prefect>=2.17.2",
)
async def test_slack_webhook_block_does_not_raise_on_success(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        AsyncWebhookClient,
        "send",
        AsyncMock(
            return_value=WebhookResponse(
                url="http://wherever", status_code=222, body="yay", headers={}
            )
        ),
    )
    block = SlackWebhook(url="http://wherever")

    with block.raise_on_failure():
        await block.notify("hello", "world")


@pytest.mark.skipif(
    condition=not hasattr(SlackWebhook, "raise_on_failure"),
    reason="The raise_on_failure option is only implemented in prefect>=2.17.2",
)
async def test_slack_webhook_block_handles_raise_on_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        AsyncWebhookClient,
        "send",
        AsyncMock(
            return_value=WebhookResponse(
                url="http://wherever", status_code=400, body="woops", headers={}
            )
        ),
    )

    from prefect.blocks.abstract import NotificationError

    block = SlackWebhook(url="http://wherever")

    with pytest.raises(NotificationError, match="Failed to send message: woops"):
        with block.raise_on_failure():
            await block.notify("hello", "world")


def test_slack_webhook_sync_notify(monkeypatch):
    """Test the sync notify path"""
    mock_client = MagicMock()
    mock_client.send.return_value = WebhookResponse(
        url="http://test", status_code=200, body="ok", headers={}
    )

    webhook = SlackWebhook(url="http://test")
    monkeypatch.setattr(webhook, "get_client", MagicMock(return_value=mock_client))

    webhook.notify("test message")
    mock_client.send.assert_called_once_with(text="test message")


async def test_slack_webhook_async_notify(monkeypatch):
    """Test the async notify path"""
    mock_client = MagicMock()
    mock_client.send = AsyncMock(
        return_value=WebhookResponse(
            url="http://test", status_code=200, body="ok", headers={}
        )
    )

    webhook = SlackWebhook(url="http://test")
    monkeypatch.setattr(webhook, "get_client", MagicMock(return_value=mock_client))

    await webhook.notify_async("test message")
    mock_client.send.assert_called_once_with(text="test message")


@pytest.mark.parametrize("message", ["test message 1", "test message 2"])
async def test_slack_webhook_notify_async_dispatch(monkeypatch, message):
    """Test that async_dispatch properly handles both sync and async contexts"""

    mock_response = WebhookResponse(
        url="http://test", status_code=200, body="ok", headers={}
    )

    mock_client = MagicMock()
    mock_client.send = AsyncMock(return_value=mock_response)

    webhook = SlackWebhook(url="http://test")
    monkeypatch.setattr(webhook, "get_client", lambda sync_client=False: mock_client)

    # Test notification
    await webhook.notify(message)
    mock_client.send.assert_called_once_with(text=message)
