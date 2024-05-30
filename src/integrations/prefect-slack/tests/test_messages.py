from itertools import product
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union
from unittest.mock import Mock

import pytest
from prefect_slack.messages import send_chat_message, send_incoming_webhook_message

from prefect import flow  # type: ignore

if TYPE_CHECKING:
    from slack_sdk.models.attachments import Attachment
    from slack_sdk.models.blocks import Block

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


# channel: str,
# slack_credentials: SlackCredentials,
# text: Optional[str] = None,
# attachments: Optional[
#     Sequence[Union[dict[str, Any], "slack_sdk.models.attachments.Attachment"]]
# ] = None,
# slack_blocks: Optional[
#     Sequence[Union[dict[str, Any], "slack_sdk.models.blocks.Block"]]
# ] = None,
@pytest.mark.parametrize(
    ["channel", "text", "attachments", "slack_blocks"],
    product(CHANNELS, TEXT, ATTACHMENTS, SLACK_BLOCKS),
)
async def test_send_chat_message(
    slack_credentials: Mock,
    channel: str,
    text: Optional[str],
    attachments: Optional[Sequence[Union[dict[str, Any], "Attachment"]]] = None,
    slack_blocks: Optional[Sequence[Union[dict[str, Any], "Block"]]] = None,
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
    slack_webhook: Mock,
    text: Optional[str] = None,
    attachments: Optional[Sequence[Union[dict[str, Any], "Attachment"]]] = None,
    slack_blocks: Optional[Sequence[Union[dict[str, Any], "Block"]]] = None,
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
