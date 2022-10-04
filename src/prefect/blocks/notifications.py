from abc import ABC, abstractmethod
from typing import Optional

import apprise
from apprise import Apprise, AppriseAsset, NotifyType
from pydantic import Field, SecretStr

from prefect.blocks.core import Block
from prefect.utilities.asyncutils import sync_compatible


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


class PrefectNotifyType(NotifyType):
    """
    A mapping of Prefect notification types for use with Apprise.

    Attributes:
        DEFAULT: A plain notification that does not insert any notification type images.
    """

    DEFAULT = "prefect_default"


apprise.NOTIFY_TYPES += (PrefectNotifyType.DEFAULT,)


class AppriseNotificationBlock(NotificationBlock, ABC):
    """
    A base class for sending notifications using Apprise.

    Attributes:
        url: Incoming webhook URL used to send notifications.
    """

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="Incoming webhook URL used to send notifications.",
        example="https://hooks.example.com/XXX",
    )

    def block_initialization(self) -> None:
        # A custom `AppriseAsset` that ensures Prefect Notifications
        # appear correctly across multiple messaging platforms
        prefect_app_data = AppriseAsset(
            app_id="Prefect Notifications",
            app_desc="Prefect Notifications",
            app_url="https://prefect.io",
        )

        self._apprise_client = Apprise(asset=prefect_app_data)
        self._apprise_client.add(self.url.get_secret_value())

    @sync_compatible
    async def notify(self, body: str, subject: Optional[str] = None):
        await self._apprise_client.async_notify(
            body=body, title=subject, notify_type=PrefectNotifyType.DEFAULT
        )


# TODO: Move to prefect-slack once collection block auto-registration is
# available
class SlackWebhook(AppriseNotificationBlock):
    """
    Enables sending notifications via a provided Slack webhook.

    Attributes:
        url: Slack webhook URL which can be used to send messages
            (e.g. `https://hooks.slack.com/XXX`).

    Examples:
        Load a saved Slack webhook and send a message:
        ```python
        from prefect.blocks.notifications import SlackWebhook

        slack_webhook_block = SlackWebhook.load("BLOCK_NAME")
        slack_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _block_type_name = "Slack Webhook"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/7dkzINU9r6j44giEFuHuUC/85d4cd321ad60c1b1e898bc3fbd28580/5cb480cd5f1b6d3fbadece79.png?h=250"

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="Slack incoming webhook URL used to send notifications.",
        example="https://hooks.slack.com/XXX",
    )


class MicrosoftTeamsWebhook(AppriseNotificationBlock):
    """
    Enables sending notifications via a provided Microsoft Teams webhook.

    Attributes:
        url: Teams webhook URL which can be used to send messages.

    Examples:
        Load a saved Teams webhook and send a message:
        ```python
        from prefect.blocks.notifications import MicrosoftTeamsWebhook
        teams_webhook_block = MicrosoftTeamsWebhook.load("BLOCK_NAME")
        teams_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _block_type_name = "Microsoft Teams Webhook"
    _block_type_slug = "ms-teams-webhook"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/6n0dSTBzwoVPhX8Vgg37i7/9040e07a62def4f48242be3eae6d3719/teams_logo.png?h=250"

    url: SecretStr = Field(
        ...,
        title="Webhook URL",
        description="The Teams incoming webhook URL used to send notifications.",
        example="https://your-org.webhook.office.com/webhookb2/XXX/IncomingWebhook/YYY/ZZZ",
    )
