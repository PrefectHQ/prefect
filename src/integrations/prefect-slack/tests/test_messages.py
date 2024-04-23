from itertools import product

import pytest
from prefect_slack.messages import send_chat_message, send_incoming_webhook_message

from prefect import flow

CHANNELS = ["#random", "#general"]
TEXT = ["hello", "goodbye"]
ATTACHMENTS = [
    None,
    [
        {
            "text": "This is an attachment",
            "id": 1,
            "fallback": "This is an attachment's fallback",
        }
    ],
]
SLACK_BLOCKS = [
    None,
    [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "This is a Slack mrkdwn block"},
        }
    ],
]


@pytest.mark.parametrize(
    ["channel", "text", "attachments", "slack_blocks"],
    product(CHANNELS, TEXT, ATTACHMENTS, SLACK_BLOCKS),
)
async def test_send_chat_message(
    slack_credentials, channel, text, attachments, slack_blocks
):
    @flow
    async def test_flow():
        return await send_chat_message(
            slack_credentials=slack_credentials,
            text=text,
            channel=channel,
            attachments=attachments,
            slack_blocks=slack_blocks,
        )

    await test_flow()
    slack_credentials.get_client().chat_postMessage.assert_called_with(
        text=text, channel=channel, blocks=slack_blocks, attachments=attachments
    )


@pytest.mark.parametrize(
    ["text", "attachments", "slack_blocks"],
    product(TEXT, ATTACHMENTS, SLACK_BLOCKS),
)
async def test_send_incoming_webhook_message(
    slack_webhook, text, attachments, slack_blocks
):
    @flow
    async def test_flow():
        await send_incoming_webhook_message(
            slack_webhook=slack_webhook,
            text=text,
            attachments=attachments,
            slack_blocks=slack_blocks,
        )

    await test_flow()
    slack_webhook.get_client().send.assert_called_with(
        text=text, blocks=slack_blocks, attachments=attachments
    )
