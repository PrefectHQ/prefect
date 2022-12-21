from abc import ABC
from typing import Dict, List, Optional

import apprise
from apprise import Apprise, AppriseAsset, NotifyType
from apprise.plugins.NotifyOpsgenie import NotifyOpsgenie
from apprise.plugins.NotifyPagerDuty import NotifyPagerDuty
from apprise.plugins.NotifyTwilio import NotifyTwilio
from pydantic import AnyHttpUrl, Field, SecretStr
from typing_extensions import Literal

from prefect.blocks.abstract import NotificationBlock
from prefect.utilities.asyncutils import sync_compatible


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


class PagerDutyWebHook(AbstractAppriseNotificationBlock):
    """
    Enables sending notifications via a provided PagerDuty webhook.
    See [Apprise notify_pagerduty docs](https://github.com/caronc/apprise/wiki/Notify_pagerduty)
    for more info on formatting the URL.

    Examples:
        Load a saved PagerDuty webhook and send a message:
        ```python
        from prefect.blocks.notifications import PagerDutyWebHook
        pagerduty_webhook_block = PagerDutyWebHook.load("BLOCK_NAME")
        pagerduty_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _description = "Enables sending notifications via a provided PagerDuty webhook."

    _block_type_name = "Pager Duty Webhook"
    _block_type_slug = "pager-duty-webhook"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/6FHJ4Lcozjfl1yDPxCvQDT/c2f6bdf47327271c068284897527f3da/PagerDuty-Logo.wine.png?h=250"

    # The default cannot be prefect_default because NotifyPagerDuty's
    # PAGERDUTY_SEVERITY_MAP only has these notify types defined as keys
    notify_type: Literal["info", "success", "warning", "failure"] = Field(
        default="info", description="The severity of the notification."
    )

    integration_key: SecretStr = Field(
        default=...,
        description=(
            "This can be found on the Events API V2 "
            "integration's detail page, and is also referred to as a Routing Key. "
            "This must be provided alongside `api_key`, but will error if provided "
            "alongside `url`."
        ),
    )

    api_key: SecretStr = Field(
        default=...,
        title="API Key",
        description=(
            "This can be found under Integrations. "
            "This must be provided alongside `integration_key`, but will error if "
            "provided alongside `url`."
        ),
    )

    source: Optional[str] = Field(
        default="Prefect", description="The source string as part of the payload."
    )

    component: str = Field(
        default="Notification",
        description="The component string as part of the payload.",
    )

    group: Optional[str] = Field(
        default=None, description="The group string as part of the payload."
    )

    class_id: Optional[str] = Field(
        default=None,
        title="Class ID",
        description="The class string as part of the payload.",
    )

    region_name: Literal["us", "eu"] = Field(
        default="us", description="The region name."
    )

    clickable_url: Optional[AnyHttpUrl] = Field(
        default=None,
        title="Clickable URL",
        description="A clickable URL to associate with the notice.",
    )

    include_image: bool = Field(
        default=True,
        description="Associate the notification status via a represented icon.",
    )

    custom_details: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional details to include as part of the payload.",
        example='{"disk_space_left": "145GB"}',
    )

    def block_initialization(self) -> None:
        url = SecretStr(
            NotifyPagerDuty(
                apikey=self.api_key.get_secret_value(),
                integrationkey=self.integration_key.get_secret_value(),
                source=self.source,
                component=self.component,
                group=self.group,
                class_id=self.class_id,
                region_name=self.region_name,
                click=self.clickable_url,
                include_image=self.include_image,
                details=self.custom_details,
            ).url()
        )
        self._start_apprise_client(url)


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


class OpsgenieWebhook(AbstractAppriseNotificationBlock):
    """
    Enables sending notifications via a provided Opsgenie webhook.
    See [Apprise notify_opsgenie docs](https://github.com/caronc/apprise/wiki/Notify_opsgenie)
    for more info on formatting the URL.

    Examples:
        Load a saved Opsgenie webhook and send a message:
        ```python
        from prefect.blocks.notifications import OpsgenieWebhook
        opsgenie_webhook_block = OpsgenieWebhook.load("BLOCK_NAME")
        opsgenie_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _description = "Enables sending notifications via a provided Opsgenie webhook."

    _block_type_name = "Opsgenie Webhook"
    _block_type_slug = "opsgenie-webhook"
    _logo_url = "https://images.ctfassets.net/sahxz1jinscj/3habq8fTzmplh7Ctkppk4/590cecb73f766361fcea9223cd47bad8/opsgenie.png"

    apikey: SecretStr = Field(
        default=...,
        title="API Key",
        description=("The API Key associated with your Opsgenie account."),
    )

    target_user: Optional[List] = Field(
        default=None, description="The user(s) you wish to notify."
    )

    target_team: Optional[List] = Field(
        default=None, description="The team(s) you wish to notify."
    )

    target_schedule: Optional[List] = Field(
        default=None, description="The schedule(s) you wish to notify."
    )

    target_escalation: Optional[List] = Field(
        default=None, description="The escalation(s) you wish to notify."
    )

    region_name: Literal["us", "eu"] = Field(
        default="us", description="The 2-character region code."
    )

    batch: bool = Field(
        default=False,
        description="Notify all targets in batches (instead of individually).",
    )

    tags: Optional[List] = Field(
        default=None,
        description="A comma-separated list of tags you can associate with your Opsgenie message.",
        example='["tag1", "tag2"]',
    )

    priority: Optional[str] = Field(
        default=3,
        description="The priority to associate with the message. It is on a scale between 1 (LOW) and 5 (EMERGENCY).",
    )

    alias: Optional[str] = Field(
        default=None, description="The alias to associate with the message."
    )

    entity: Optional[str] = Field(
        default=None, description="The entity to associate with the message."
    )

    details: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional details composed of key/values pairs.",
        example='{"key1": "value1", "key2": "value2"}',
    )

    def block_initialization(self) -> None:
        targets = []
        if self.target_user:
            [targets.append(f"@{x}") for x in self.target_user]
        if self.target_team:
            [targets.append(f"#{x}") for x in self.target_team]
        if self.target_schedule:
            [targets.append(f"*{x}") for x in self.target_schedule]
        if self.target_escalation:
            [targets.append(f"^{x}") for x in self.target_escalation]
        url = SecretStr(
            NotifyOpsgenie(
                apikey=self.apikey.get_secret_value(),
                targets=targets,
                region_name=self.region_name,
                details=self.details,
                priority=self.priority,
                alias=self.alias,
                entity=self.entity,
                batch=self.batch,
                tags=self.tags,
            ).url()
        )
        self._start_apprise_client(url)
