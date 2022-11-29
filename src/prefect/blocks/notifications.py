from abc import ABC, abstractmethod
from typing import Dict, Optional

import apprise
from apprise import Apprise, AppriseAsset, NotifyType
from apprise.plugins.NotifyPagerDuty import NotifyPagerDuty
from pydantic import AnyHttpUrl, Field, SecretStr, root_validator
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


class AppriseNotificationBlock(NotificationBlock, ABC):
    """
    A base class for sending notifications using Apprise.
    """

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="Incoming webhook URL used to send notifications.",
        example="https://hooks.example.com/XXX",
    )

    notify_type: Literal[
        "info", "success", "warning", "failure", "prefect_default"
    ] = Field(
        default=PrefectNotifyType.DEFAULT,
        description=(
            "The type of notification being performed; the prefect_default "
            "is a plain notification that does not attach an image."
        ),
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
            body=body, title=subject, notify_type=self.notify_type
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


class PagerDutyWebHook(AppriseNotificationBlock):
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

    url: Optional[SecretStr] = Field(
        default=None,
        title="Webhook URL",
        description=(
            "The PagerDuty incoming webhook URL used to send notifications; "
            "if this is provided, the other fields are ignored and will error "
            "if provided alongside `api_key` or `integration_key`."
        ),
        example="pagerduty://{integration_key}@{api_key}/{source}/{component}",
    )

    # The default cannot be prefect_default because NotifyPagerDuty's
    # PAGERDUTY_SEVERITY_MAP only has these notify types defined as keys
    notify_type: Literal["info", "success", "warning", "failure"] = Field(
        default="info", description="The severity of the notifcation."
    )

    integration_key: Optional[SecretStr] = Field(
        default=None,
        description=(
            "A component of the webhook URL; this can be found on the Events API V2 "
            "integration's detail page, and is also referred to as a Routing Key. "
            "This must be provided alongside `api_key`, but will error if provided "
            "alongside `url`."
        ),
    )

    api_key: Optional[SecretStr] = Field(
        default=None,
        title="API Key",
        description=(
            "A component of the webhook URL; this can be found under Integrations. "
            "This must be provided alongside `integration_key`, but will error if "
            "provided alongside `url`."
        ),
    )

    source: Optional[str] = Field(
        default="Prefect",
        description=(
            "A component of the webhook URL; the source string "
            "as part of the payload."
        ),
    )

    component: str = Field(
        default="Notification",
        description=(
            "A component of the webhook URL; the component string "
            "as part of the payload."
        ),
    )

    group: Optional[str] = Field(
        default=None,
        description=(
            "A component of the webhook URL; the group string "
            "as part of the payload."
        ),
    )

    class_id: Optional[str] = Field(
        default=None,
        title="Class ID",
        description=(
            "A component of the webhook URL; the class string "
            "as part of the payload."
        ),
    )

    region_name: str = Field(
        default="us",
        description=(
            "A component of the webhook URL; by default this "
            "takes on the value of `us` but you can optionally "
            "set it to `eu` as well."
        ),
    )

    clickable_url: Optional[AnyHttpUrl] = Field(
        default=None,
        title="Clickable URL",
        description=(
            "A component of the webhook URL; "
            "a clickable URL to associate with the notice."
        ),
    )

    include_image: bool = Field(
        default=True,
        description=(
            "A component of the webhook URL; "
            "associate the notification status via a represented icon."
        ),
    )

    custom_details: Dict[str, str] = Field(
        default=None,
        description=(
            "A component of the webhook URL; "
            "additional details to include as part of the payload."
        ),
        example='{"disk_space_left": "145GB"}',
    )

    def block_initialization(self) -> None:
        if self.url is None:
            self.url = SecretStr(
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
        super().block_initialization()

    @root_validator(pre=True)
    def validate_has_either_url_or_components(cls, values):
        has_url = bool(values.get("url"))
        has_keys = bool(values.get("integration_key") or values.get("api_key"))
        if not (has_url ^ has_keys):
            raise ValueError(
                "Cannot provide url alongside integration_key and api_key."
            )
        return values

    @root_validator(pre=True)
    def validate_has_both_keys(cls, values):
        has_url = bool(values.get("url"))
        has_both_keys = bool(values.get("integration_key") and values.get("api_key"))
        if not has_url and not has_both_keys:
            raise ValueError(
                "Must provide both integration_key and api_key "
                "if url is not provided."
            )
        return values
