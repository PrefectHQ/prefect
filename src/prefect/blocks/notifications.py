from abc import ABC, abstractmethod
from typing import List, Optional

import apprise
from apprise import Apprise, AppriseAsset, NotifyType
from apprise.plugins.NotifyTwilio import NotifyTwilio
from pydantic import Field, SecretStr
from typing_extensions import Literal

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


class AbstractAppriseNotificationBlock(NotificationBlock, ABC):
    """
    An abstract class for sending notifications using Apprise.
    """

    notify_type: Literal[
        "prefect_default", "info", "success", "warning", "failure"
    ] = Field(
        default=PrefectNotifyType.DEFAULT,
        description=(
            "The type of notification being performed; the prefect_default "
            "is a plain notification that does not attach an image."
        ),
    )

    def _start_apprise_client(self, url: SecretStr):
        # A custom `AppriseAsset` that ensures Prefect Notifications
        # appear correctly across multiple messaging platforms
        prefect_app_data = AppriseAsset(
            app_id="Prefect Notifications",
            app_desc="Prefect Notifications",
            app_url="https://prefect.io",
        )

        self._apprise_client = Apprise(asset=prefect_app_data)
        self._apprise_client.add(url.get_secret_value())

    def block_initialization(self) -> None:
        self._start_apprise_client(self.url)

    @sync_compatible
    async def notify(self, body: str, subject: Optional[str] = None):
        await self._apprise_client.async_notify(
            body=body, title=subject, notify_type=self.notify_type
        )


class AppriseNotificationBlock(AbstractAppriseNotificationBlock, ABC):
    """
    A base class for sending notifications using Apprise, through webhook URLs.
    """

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="Incoming webhook URL used to send notifications.",
        example="https://hooks.example.com/XXX",
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


class TwilioSMS(AbstractAppriseNotificationBlock):
    """Enables sending notifications via Twilio SMS.
    Find more on sending Twilio SMS messages in the [docs](https://www.twilio.com/docs/sms).

    Examples:
        Load a saved `TwilioSMS` block and send a message:
        ```python
        from prefect.blocks.notifications import TwilioSMS
        twilio_webhook_block = TwilioSMS.load("BLOCK_NAME")
        twilio_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _description = "Enables sending notifications via Twilio SMS."
    _block_type_name = "Twilio SMS"
    _block_type_slug = "twilio-sms"
    _logo_url = "https://images.ctfassets.net/zscdif0zqppk/YTCgPL6bnK3BczP2gV9md/609283105a7006c57dbfe44ee1a8f313/58482bb9cef1014c0b5e4a31.png?h=250"  # noqa

    account_sid: str = Field(
        default=...,
        description=(
            "The Twilio Account SID - it can be found on the homepage "
            "of the Twilio console."
        ),
    )

    auth_token: SecretStr = Field(
        default=...,
        description=(
            "The Twilio Authentication Token - "
            "it can be found on the homepage of the Twilio console."
        ),
    )

    from_phone_number: str = Field(
        default=...,
        description="The valid Twilio phone number to send the message from.",
        example="18001234567",
    )

    to_phone_numbers: List[str] = Field(
        default=...,
        description="A list of valid Twilio phone number(s) to send the message to.",
        # not wrapped in brackets because of the way UI displays examples; in code should be ["18004242424"]
        example="18004242424",
    )

    def block_initialization(self) -> None:
        url = SecretStr(
            NotifyTwilio(
                account_sid=self.account_sid,
                auth_token=self.auth_token.get_secret_value(),
                source=self.from_phone_number,
                targets=self.to_phone_numbers,
            ).url()
        )
        self._start_apprise_client(url)
