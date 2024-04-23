"""Tasks for sending Slack messages"""

from typing import TYPE_CHECKING, Dict, Optional, Sequence, Union

from prefect import get_run_logger, task
from prefect_slack.credentials import SlackCredentials, SlackWebhook

if TYPE_CHECKING:  # pragma: no cover
    import slack_sdk.models.attachments
    import slack_sdk.models.blocks


@task
async def send_chat_message(
    channel: str,
    slack_credentials: SlackCredentials,
    text: Optional[str] = None,
    attachments: Optional[
        Sequence[Union[Dict, "slack_sdk.models.attachments.Attachment"]]
    ] = None,
    slack_blocks: Optional[
        Sequence[Union[Dict, "slack_sdk.models.blocks.Block"]]
    ] = None,
) -> Dict:
    """
    Sends a message to a Slack channel

    Args:
        channel: The name of the channel in which to post the chat message
            (e.g. #general)
        slack_credentials: Instance of `SlackCredentials` initialized with a Slack
            bot token
        text: Contents of the message. It's a best practice to always provide a `text`
            argument when posting a message. The `text` argument is used in places where
            content cannot be rendered such as: system push notifications, assistive
            technology such as screen readers, etc.
        attachments: List of objects defining secondary context in the posted Slack
            message. The [Slack API docs](https://api.slack.com/messaging/composing/layouts#building-attachments)
            provide guidance on building attachments.
        slack_blocks: List of objects defining the layout and formatting of the posted
            message. The [Slack API docs](https://api.slack.com/block-kit/building)
            provide guidance on building messages with blocks.

    Returns:
        Dict: Response from the Slack API. Example response structures can be found in
            the [Slack API docs](https://api.slack.com/methods/chat.postMessage#examples)

    Examples:
        Post a message at the end of a flow run

        ```python
        from prefect import flow
        from prefect.context import get_run_context
        from prefect_slack import SlackCredentials
        from prefect_slack.messages import send_chat_message


        @flow
        def example_send_message_flow():
            context = get_run_context()

            # Run other tasks and subflows here

            token = "xoxb-your-bot-token-here"
            send_chat_message(
                slack_credentials=SlackCredentials(token),
                channel="#prefect",
                text=f"Flow run {context.flow_run.name} completed :tada:"
            )

        example_send_message_flow()
        ```
    """  # noqa
    logger = get_run_logger()
    logger.info("Posting chat message to %s", channel)

    client = slack_credentials.get_client()
    result = await client.chat_postMessage(
        channel=channel, text=text, blocks=slack_blocks, attachments=attachments
    )
    return result.data


@task
async def send_incoming_webhook_message(
    slack_webhook: SlackWebhook,
    text: Optional[str] = None,
    attachments: Optional[
        Sequence[Union[Dict, "slack_sdk.models.attachments.Attachment"]]
    ] = None,
    slack_blocks: Optional[
        Sequence[Union[Dict, "slack_sdk.models.blocks.Block"]]
    ] = None,
) -> None:
    """
    Sends a message via an incoming webhook

    Args:
        slack_webhook: Instance of `SlackWebhook` initialized with a Slack
            webhook URL.
        text: Contents of the message. It's a best practice to always provide a `text`
            argument when posting a message. The `text` argument is used in places where
            content cannot be rendered such as: system push notifications, assistive
            technology such as screen readers, etc.
        attachments: List of objects defining secondary context in the posted Slack
            message. The [Slack API docs](https://api.slack.com/messaging/composing/layouts#building-attachments)
            provide guidance on building attachments.
        slack_blocks: List of objects defining the layout and formatting of the posted
            message. The [Slack API docs](https://api.slack.com/block-kit/building)
            provide guidance on building messages with blocks.

    Examples:
        Post a message at the end of a flow run

        ```python
        from prefect import flow
        from prefect_slack import SlackWebhook
        from prefect_slack.messages import send_incoming_webhook_message


        @flow
        def example_send_message_flow():
            # Run other tasks and subflows here

            webhook_url = "https://hooks.slack.com/XXX"
            send_incoming_webhook_message(
                slack_webhook=SlackWebhook(
                    url=webhook_url
                ),
                text="Warehouse loading flow completed :sparkles:"
            )

        example_send_message_flow()
        ```
    """  # noqa
    logger = get_run_logger()
    logger.info("Posting message to provided webhook")

    client = slack_webhook.get_client()
    await client.send(text=text, attachments=attachments, blocks=slack_blocks)
