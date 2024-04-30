from unittest.mock import AsyncMock

import pytest
from prefect_slack import SlackWebhook
from slack_sdk.webhook.async_client import AsyncWebhookClient, WebhookResponse


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
