from abc import ABC, abstractmethod
from typing import Optional

from pydantic import Field, SecretStr
from slack_sdk.webhook.async_client import AsyncWebhookClient

from prefect.blocks.core import Block


class NotificationBlock(Block, ABC):
    """
    A `Block` base class for sending notifications.
    """

    _block_schema_capabilities = ["notify"]

    @abstractmethod
    async def notify(self, body: str, subject: Optional[str] = None):
        """
        Send a notification
        """


# TODO: Move to prefect-slack once collection block auto-registration is
# available
class SlackWebhook(NotificationBlock):
    """
    Enables sending notifications via a provided Slack webhook.

    Args:
        url (SecretStr): Slack webhook URL which can be used to send messages
            (e.g. `https://hooks.slack.com/XXX`).

    Examples:
        ```python
        from prefect.blocks.notifications import SlackWebhook

        slack_webhook_block = SlackWebhook.load(BLOCK_NAME)
        slack_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _block_type_name = "Slack Webhook"
    _logo_url = "https://assets.brandfolder.com/pl546j-7le8zk-afym5u/v/3033396/original/Slack_Mark_Web.png"

    url: SecretStr = Field(..., title="Webhook URL")

    def block_initialization(self) -> None:
        self._async_webhook_client = AsyncWebhookClient(url=self.url.get_secret_value())

    async def notify(self, body: str, subject: Optional[str] = None):
        await self._async_webhook_client.send(text=body)
