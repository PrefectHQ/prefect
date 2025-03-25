from __future__ import annotations

import logging
from abc import ABC
from typing import Any, Optional, cast

from pydantic import AnyHttpUrl, Field, HttpUrl, SecretStr
from typing_extensions import Literal

from prefect.blocks.abstract import NotificationBlock, NotificationError
from prefect.logging import LogEavesdropper
from prefect.types import SecretDict
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.templating import apply_values, find_placeholders
from prefect.utilities.urls import validate_restricted_url

PREFECT_NOTIFY_TYPE_DEFAULT = "prefect_default"


class AbstractAppriseNotificationBlock(NotificationBlock, ABC):
    """
    An abstract class for sending notifications using Apprise.
    """

    notify_type: Literal["prefect_default", "info", "success", "warning", "failure"] = (
        Field(
            default=PREFECT_NOTIFY_TYPE_DEFAULT,
            description=(
                "The type of notification being performed; the prefect_default "
                "is a plain notification that does not attach an image."
            ),
        )
    )

    def __init__(self, *args: Any, **kwargs: Any):
        from apprise import (
            NOTIFY_TYPES,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType] incomplete type hints in apprise
        )

        if PREFECT_NOTIFY_TYPE_DEFAULT not in NOTIFY_TYPES:
            NOTIFY_TYPES += (PREFECT_NOTIFY_TYPE_DEFAULT,)  # pyright: ignore[reportUnknownVariableType]

        super().__init__(*args, **kwargs)

    def _start_apprise_client(self, url: SecretStr):
        from apprise import Apprise, AppriseAsset

        # A custom `AppriseAsset` that ensures Prefect Notifications
        # appear correctly across multiple messaging platforms
        prefect_app_data = AppriseAsset(
            app_id="Prefect Notifications",
            app_desc="Prefect Notifications",
            app_url="https://prefect.io",
        )

        self._apprise_client = Apprise(asset=prefect_app_data)
        self._apprise_client.add(servers=url.get_secret_value())  # pyright: ignore[reportUnknownMemberType]

    def block_initialization(self) -> None:
        self._start_apprise_client(getattr(self, "url"))

    @sync_compatible
    async def notify(  # pyright: ignore[reportIncompatibleMethodOverride] TODO: update to sync only once base class is updated
        self,
        body: str,
        subject: str | None = None,
    ) -> None:
        with LogEavesdropper("apprise", level=logging.DEBUG) as eavesdropper:
            result = await self._apprise_client.async_notify(  # pyright: ignore[reportUnknownMemberType] incomplete type hints in apprise
                body=body,
                title=subject or "",
                notify_type=self.notify_type,  # pyright: ignore[reportArgumentType]
            )
        if not result and self._raise_on_failure:
            raise NotificationError(log=eavesdropper.text())


class AppriseNotificationBlock(AbstractAppriseNotificationBlock, ABC):
    """
    A base class for sending notifications using Apprise, through webhook URLs.
    """

    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )
    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="Incoming webhook URL used to send notifications.",
        examples=["https://hooks.example.com/XXX"],
    )
    allow_private_urls: bool = Field(
        default=True,
        description="Whether to allow notifications to private URLs. Defaults to True.",
    )

    @sync_compatible
    async def notify(  # pyright: ignore[reportIncompatibleMethodOverride] TODO: update to sync only once base class is updated
        self,
        body: str,
        subject: str | None = None,
    ):
        if not self.allow_private_urls:
            try:
                validate_restricted_url(self.url.get_secret_value())
            except ValueError as exc:
                if self._raise_on_failure:
                    raise NotificationError(str(exc))
                raise

        await super().notify(body, subject)  # pyright: ignore[reportGeneralTypeIssues] TODO: update to sync only once base class is updated


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
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/c1965ecbf8704ee1ea20d77786de9a41ce1087d1-500x500.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="Slack incoming webhook URL used to send notifications.",
        examples=["https://hooks.slack.com/XXX"],
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
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/817efe008a57f0a24f3587414714b563e5e23658-250x250.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="The Microsoft Power Automate (Workflows) URL used to send notifications to Teams.",
        examples=[
            "https://prod-NO.LOCATION.logic.azure.com:443/workflows/WFID/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=SIGNATURE"
        ],
    )

    include_image: bool = Field(
        default=True,
        description="Include an image with the notification.",
    )

    wrap: bool = Field(
        default=True,
        description="Wrap the notification text.",
    )

    def block_initialization(self) -> None:
        """see https://github.com/caronc/apprise/pull/1172"""
        from apprise.plugins.workflows import NotifyWorkflows

        if not (
            parsed_url := cast(
                dict[str, Any],
                NotifyWorkflows.parse_native_url(self.url.get_secret_value()),  # pyright: ignore[reportUnknownMemberType] incomplete type hints in apprise
            )
        ):
            raise ValueError("Invalid Microsoft Teams Workflow URL provided.")

        parsed_url |= {"include_image": self.include_image, "wrap": self.wrap}

        self._start_apprise_client(SecretStr(NotifyWorkflows(**parsed_url).url()))  # pyright: ignore[reportUnknownMemberType] incomplete type hints in apprise


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
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/8dbf37d17089c1ce531708eac2e510801f7b3aee-250x250.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    # The default cannot be prefect_default because NotifyPagerDuty's
    # PAGERDUTY_SEVERITY_MAP only has these notify types defined as keys
    notify_type: Literal["info", "success", "warning", "failure"] = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
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

    custom_details: Optional[dict[str, str]] = Field(
        default=None,
        description="Additional details to include as part of the payload.",
        examples=['{"disk_space_left": "145GB"}'],
    )

    def block_initialization(self) -> None:
        try:
            # Try importing for apprise>=1.18.0
            from apprise.plugins.pagerduty import NotifyPagerDuty
        except ImportError:
            # Fallback for versions apprise<1.18.0
            from apprise.plugins.NotifyPagerDuty import (  # pyright: ignore[reportMissingImports] this is a fallback
                NotifyPagerDuty,  # pyright: ignore[reportUnknownVariableType] incomplete type hints in apprise
            )

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
            ).url()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] incomplete type hints in apprise
        )
        self._start_apprise_client(url)

    @sync_compatible
    async def notify(  # pyright: ignore[reportIncompatibleMethodOverride] TODO: update to sync only once base class is updated
        self,
        body: str,
        subject: str | None = None,
    ):
        """
        Apprise will combine subject and body by default, so we need to move
        the body into the custom_details field. custom_details is part of the
        webhook url, so we need to update the url and restart the client.
        """
        if subject:
            self.custom_details = self.custom_details or {}
            self.custom_details.update(
                {"Prefect Notification Body": body.replace(" ", "%20")}
            )
            body = " "
            self.block_initialization()

        await super().notify(body, subject)  # pyright: ignore[reportGeneralTypeIssues] TODO: update to sync only once base class is updated


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
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/8bd8777999f82112c09b9c8d57083ac75a4a0d65-250x250.png"
    )  # noqa
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

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
        examples=["18001234567"],
    )

    to_phone_numbers: list[str] = Field(
        default=...,
        description="A list of valid Twilio phone number(s) to send the message to.",
        # not wrapped in brackets because of the way UI displays examples; in code should be ["18004242424"]
        examples=["18004242424"],
    )

    def block_initialization(self) -> None:
        try:
            # Try importing for apprise>=1.18.0
            from apprise.plugins.twilio import NotifyTwilio
        except ImportError:
            # Fallback for versions apprise<1.18.0
            from apprise.plugins.NotifyTwilio import (  # pyright: ignore[reportMissingImports] this is a fallback
                NotifyTwilio,  # pyright: ignore[reportUnknownVariableType] incomplete type hints in apprise
            )

        url = SecretStr(
            NotifyTwilio(
                account_sid=self.account_sid,
                auth_token=self.auth_token.get_secret_value(),
                source=self.from_phone_number,
                targets=self.to_phone_numbers,
            ).url()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] incomplete type hints in apprise
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
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/d8b5bc6244ae6cd83b62ec42f10d96e14d6e9113-280x280.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    apikey: SecretStr = Field(
        default=...,
        title="API Key",
        description="The API Key associated with your Opsgenie account.",
    )

    target_user: Optional[list[str]] = Field(
        default=None, description="The user(s) you wish to notify."
    )

    target_team: Optional[list[str]] = Field(
        default=None, description="The team(s) you wish to notify."
    )

    target_schedule: Optional[list[str]] = Field(
        default=None, description="The schedule(s) you wish to notify."
    )

    target_escalation: Optional[list[str]] = Field(
        default=None, description="The escalation(s) you wish to notify."
    )

    region_name: Literal["us", "eu"] = Field(
        default="us", description="The 2-character region code."
    )

    batch: bool = Field(
        default=False,
        description="Notify all targets in batches (instead of individually).",
    )

    tags: Optional[list[str]] = Field(
        default=None,
        description=(
            "A comma-separated list of tags you can associate with your Opsgenie"
            " message."
        ),
        examples=['["tag1", "tag2"]'],
    )

    priority: Optional[int] = Field(
        default=3,
        description=(
            "The priority to associate with the message. It is on a scale between 1"
            " (LOW) and 5 (EMERGENCY)."
        ),
    )

    alias: Optional[str] = Field(
        default=None, description="The alias to associate with the message."
    )

    entity: Optional[str] = Field(
        default=None, description="The entity to associate with the message."
    )

    details: Optional[dict[str, str]] = Field(
        default=None,
        description="Additional details composed of key/values pairs.",
        examples=['{"key1": "value1", "key2": "value2"}'],
    )

    def block_initialization(self) -> None:
        try:
            # Try importing for apprise>=1.18.0
            from apprise.plugins.opsgenie import NotifyOpsgenie
        except ImportError:
            # Fallback for versions apprise<1.18.0
            from apprise.plugins.NotifyOpsgenie import (  # pyright: ignore[reportMissingImports] this is a fallback
                NotifyOpsgenie,  # pyright: ignore[reportUnknownVariableType] incomplete type hints in apprise
            )

        targets: list[str] = []
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
                action="new",
            ).url()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] incomplete type hints in apprise
        )
        self._start_apprise_client(url)


class MattermostWebhook(AbstractAppriseNotificationBlock):
    """
    Enables sending notifications via a provided Mattermost webhook.
    See [Apprise notify_Mattermost docs](https://github.com/caronc/apprise/wiki/Notify_Mattermost) # noqa


    Examples:
        Load a saved Mattermost webhook and send a message:
        ```python
        from prefect.blocks.notifications import MattermostWebhook

        mattermost_webhook_block = MattermostWebhook.load("BLOCK_NAME")

        mattermost_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _description = "Enables sending notifications via a provided Mattermost webhook."
    _block_type_name = "Mattermost Webhook"
    _block_type_slug = "mattermost-webhook"
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/1350a147130bf82cbc799a5f868d2c0116207736-250x250.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    hostname: str = Field(
        default=...,
        description="The hostname of your Mattermost server.",
        examples=["Mattermost.example.com"],
    )
    secure: bool = Field(
        default=False,
        description="Whether to use secure https connection.",
    )

    token: SecretStr = Field(
        default=...,
        description="The token associated with your Mattermost webhook.",
    )

    botname: Optional[str] = Field(
        title="Bot name",
        default=None,
        description="The name of the bot that will send the message.",
    )

    channels: Optional[list[str]] = Field(
        default=None,
        description="The channel(s) you wish to notify.",
    )

    include_image: bool = Field(
        default=False,
        description="Whether to include the Apprise status image in the message.",
    )

    path: Optional[str] = Field(
        default=None,
        description="An optional sub-path specification to append to the hostname.",
    )

    port: int = Field(
        default=8065,
        description="The port of your Mattermost server.",
    )

    def block_initialization(self) -> None:
        try:
            # Try importing for apprise>=1.18.0
            from apprise.plugins.mattermost import NotifyMattermost
        except ImportError:
            # Fallback for versions apprise<1.18.0
            from apprise.plugins.NotifyMattermost import (  # pyright: ignore[reportMissingImports] this is a fallback
                NotifyMattermost,  # pyright: ignore[reportUnknownVariableType] incomplete type hints in apprise
            )

        url = SecretStr(
            NotifyMattermost(
                token=self.token.get_secret_value(),
                fullpath=self.path,
                host=self.hostname,
                botname=self.botname,
                channels=self.channels,
                include_image=self.include_image,
                port=self.port,
                secure=self.secure,
            ).url()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] incomplete type hints in apprise
        )
        self._start_apprise_client(url)


class DiscordWebhook(AbstractAppriseNotificationBlock):
    """
    Enables sending notifications via a provided Discord webhook.
    See [Apprise notify_Discord docs](https://github.com/caronc/apprise/wiki/Notify_Discord) # noqa

    Examples:
        Load a saved Discord webhook and send a message:
        ```python
        from prefect.blocks.notifications import DiscordWebhook

        discord_webhook_block = DiscordWebhook.load("BLOCK_NAME")

        discord_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _description = "Enables sending notifications via a provided Discord webhook."
    _block_type_name = "Discord Webhook"
    _block_type_slug = "discord-webhook"
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/9e94976c80ef925b66d24e5d14f0d47baa6b8f88-250x250.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    webhook_id: SecretStr = Field(
        default=...,
        description=(
            "The first part of 2 tokens provided to you after creating a"
            " incoming-webhook."
        ),
    )

    webhook_token: SecretStr = Field(
        default=...,
        description=(
            "The second part of 2 tokens provided to you after creating a"
            " incoming-webhook."
        ),
    )

    botname: Optional[str] = Field(
        title="Bot name",
        default=None,
        description=(
            "Identify the name of the bot that should issue the message. If one isn't"
            " specified then the default is to just use your account (associated with"
            " the incoming-webhook)."
        ),
    )

    tts: bool = Field(
        default=False,
        description="Whether to enable Text-To-Speech.",
    )

    include_image: bool = Field(
        default=False,
        description=(
            "Whether to include an image in-line with the message describing the"
            " notification type."
        ),
    )

    avatar: bool = Field(
        default=False,
        description="Whether to override the default discord avatar icon.",
    )

    avatar_url: Optional[str] = Field(
        title="Avatar URL",
        default=None,
        description=(
            "Over-ride the default discord avatar icon URL. By default this is not set"
            " and Apprise chooses the URL dynamically based on the type of message"
            " (info, success, warning, or error)."
        ),
    )

    def block_initialization(self) -> None:
        try:
            # Try importing for apprise>=1.18.0
            from apprise.plugins.discord import NotifyDiscord
        except ImportError:
            # Fallback for versions apprise<1.18.0
            from apprise.plugins.NotifyDiscord import (  # pyright: ignore[reportMissingImports] this is a fallback
                NotifyDiscord,  # pyright: ignore[reportUnknownVariableType] incomplete type hints in apprise
            )

        url = SecretStr(
            NotifyDiscord(
                webhook_id=self.webhook_id.get_secret_value(),
                webhook_token=self.webhook_token.get_secret_value(),
                botname=self.botname,
                tts=self.tts,
                include_image=self.include_image,
                avatar=self.avatar,
                avatar_url=self.avatar_url,
            ).url()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] incomplete type hints in apprise
        )
        self._start_apprise_client(url)


class CustomWebhookNotificationBlock(NotificationBlock):
    """
    Enables sending notifications via any custom webhook.

    All nested string param contains `{{key}}` will be substituted with value from context/secrets.

    Context values include: `subject`, `body` and `name`.

    Examples:
        Load a saved custom webhook and send a message:
        ```python
        from prefect.blocks.notifications import CustomWebhookNotificationBlock

        custom_webhook_block = CustomWebhookNotificationBlock.load("BLOCK_NAME")

        custom_webhook_block.notify("Hello from Prefect!")
        ```
    """

    _block_type_name = "Custom Webhook"
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/c7247cb359eb6cf276734d4b1fbf00fb8930e89e-250x250.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    name: str = Field(title="Name", description="Name of the webhook.")

    url: str = Field(
        title="Webhook URL",
        description="The webhook URL.",
        examples=["https://hooks.slack.com/XXX"],
    )

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        default="POST", description="The webhook request method. Defaults to `POST`."
    )

    params: Optional[dict[str, str]] = Field(
        default=None, title="Query Params", description="Custom query params."
    )
    json_data: Optional[dict[str, Any]] = Field(
        default=None,
        title="JSON Data",
        description="Send json data as payload.",
        examples=[
            '{"text": "{{subject}}\\n{{body}}", "title": "{{name}}", "token":'
            ' "{{tokenFromSecrets}}"}'
        ],
    )
    form_data: Optional[dict[str, str]] = Field(
        default=None,
        title="Form Data",
        description=(
            "Send form data as payload. Should not be used together with _JSON Data_."
        ),
        examples=[
            '{"text": "{{subject}}\\n{{body}}", "title": "{{name}}", "token":'
            ' "{{tokenFromSecrets}}"}'
        ],
    )

    headers: Optional[dict[str, str]] = Field(None, description="Custom headers.")
    cookies: Optional[dict[str, str]] = Field(None, description="Custom cookies.")

    timeout: float = Field(
        default=10, description="Request timeout in seconds. Defaults to 10."
    )

    secrets: SecretDict = Field(
        default_factory=lambda: SecretDict(dict()),
        title="Custom Secret Values",
        description="A dictionary of secret values to be substituted in other configs.",
        examples=['{"tokenFromSecrets":"SomeSecretToken"}'],
    )

    def _build_request_args(self, body: str, subject: str | None) -> dict[str, Any]:
        """Build kwargs for httpx.AsyncClient.request"""
        # prepare values
        values = self.secrets.get_secret_value()
        # use 'null' when subject is None
        values.update(
            {
                "subject": "null" if subject is None else subject,
                "body": body,
                "name": self.name,
            }
        )
        # do substution
        return apply_values(
            {
                "method": self.method,
                "url": self.url,
                "params": self.params,
                "data": self.form_data,
                "json": self.json_data,
                "headers": self.headers,
                "cookies": self.cookies,
                "timeout": self.timeout,
            },
            values,
        )

    def block_initialization(self) -> None:
        # check form_data and json_data
        if self.form_data is not None and self.json_data is not None:
            raise ValueError("both `Form Data` and `JSON Data` provided")
        allowed_keys = {"subject", "body", "name"}.union(
            self.secrets.get_secret_value().keys()
        )
        # test template to raise a error early
        for name in ["url", "params", "form_data", "json_data", "headers", "cookies"]:
            template = getattr(self, name)
            if template is None:
                continue
            # check for placeholders not in predefined keys and secrets
            placeholders = find_placeholders(template)
            for placeholder in placeholders:
                if placeholder.name not in allowed_keys:
                    raise KeyError(f"{name}/{placeholder}")

    @sync_compatible
    async def notify(self, body: str, subject: str | None = None) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        import httpx

        request_args = self._build_request_args(body, subject)
        cookies = request_args.pop("cookies", dict())
        # make request with httpx
        client = httpx.AsyncClient(
            headers={"user-agent": "Prefect Notifications"}, cookies=cookies
        )
        async with client:
            resp = await client.request(**request_args)
        resp.raise_for_status()


class SendgridEmail(AbstractAppriseNotificationBlock):
    """
    Enables sending notifications via any sendgrid account.
    See [Apprise Notify_sendgrid docs](https://github.com/caronc/apprise/wiki/Notify_Sendgrid)

    Examples:
        Load a saved Sendgrid and send a email message:
        ```python
        from prefect.blocks.notifications import SendgridEmail

        sendgrid_block = SendgridEmail.load("BLOCK_NAME")

        sendgrid_block.notify("Hello from Prefect!")
        ```
    """

    _description = "Enables sending notifications via Sendgrid email service."
    _block_type_name = "Sendgrid Email"
    _block_type_slug = "sendgrid-email"
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/82bc6ed16ca42a2252a5512c72233a253b8a58eb-250x250.png"
    )
    _documentation_url = HttpUrl(
        "https://docs.prefect.io/latest/automate/events/automations-triggers#sending-notifications-with-automations"
    )

    api_key: SecretStr = Field(
        default=...,
        title="API Key",
        description="The API Key associated with your sendgrid account.",
    )

    sender_email: str = Field(
        title="Sender email id",
        description="The sender email id.",
        examples=["test-support@gmail.com"],
    )

    to_emails: list[str] = Field(
        default=...,
        title="Recipient emails",
        description="Email ids of all recipients.",
        examples=['"recipient1@gmail.com"'],
    )

    def block_initialization(self) -> None:
        try:
            # Try importing for apprise>=1.18.0
            from apprise.plugins.sendgrid import NotifySendGrid
        except ImportError:
            # Fallback for versions apprise<1.18.0
            from apprise.plugins.NotifySendGrid import (  # pyright: ignore[reportMissingImports] this is a fallback
                NotifySendGrid,  # pyright: ignore[reportUnknownVariableType] incomplete type hints in apprise
            )

        url = SecretStr(
            NotifySendGrid(
                apikey=self.api_key.get_secret_value(),
                from_email=self.sender_email,
                targets=self.to_emails,
            ).url()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType] incomplete type hints in apprise
        )

        self._start_apprise_client(url)
