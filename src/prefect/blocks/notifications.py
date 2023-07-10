from abc import ABC
from typing import Dict, List, Optional

from pydantic import AnyHttpUrl, Field, SecretStr
from typing_extensions import Literal

from prefect.blocks.abstract import NotificationBlock
from prefect.blocks.fields import SecretDict
from prefect.events.instrument import instrument_instance_method_call
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.templating import apply_values, find_placeholders

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

    def __init__(self, *args, **kwargs):
        import apprise

        if PREFECT_NOTIFY_TYPE_DEFAULT not in apprise.NOTIFY_TYPES:
            apprise.NOTIFY_TYPES += (PREFECT_NOTIFY_TYPE_DEFAULT,)

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
        self._apprise_client.add(url.get_secret_value())

    def block_initialization(self) -> None:
        self._start_apprise_client(self.url)

    @sync_compatible
    @instrument_instance_method_call()
    async def notify(self, body: str, subject: Optional[str] = None):
        await self._apprise_client.async_notify(
            body=body, title=subject, notify_type=self.notify_type
        )


class AppriseNotificationBlock(AbstractAppriseNotificationBlock, ABC):
    """
    A base class for sending notifications using Apprise, through webhook URLs.
    """

    _documentation_url = "https://docs.prefect.io/ui/notifications/"
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
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.SlackWebhook"

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
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.MicrosoftTeamsWebhook"

    url: SecretStr = Field(
        ...,
        title="Webhook URL",
        description="The Teams incoming webhook URL used to send notifications.",
        example=(
            "https://your-org.webhook.office.com/webhookb2/XXX/IncomingWebhook/YYY/ZZZ"
        ),
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
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.PagerDutyWebHook"

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
        from apprise.plugins.NotifyPagerDuty import NotifyPagerDuty

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
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.TwilioSMS"

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
        from apprise.plugins.NotifyTwilio import NotifyTwilio

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
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.OpsgenieWebhook"

    apikey: SecretStr = Field(
        default=...,
        title="API Key",
        description="The API Key associated with your Opsgenie account.",
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
        description=(
            "A comma-separated list of tags you can associate with your Opsgenie"
            " message."
        ),
        example='["tag1", "tag2"]',
    )

    priority: Optional[str] = Field(
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

    details: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional details composed of key/values pairs.",
        example='{"key1": "value1", "key2": "value2"}',
    )

    def block_initialization(self) -> None:
        from apprise.plugins.NotifyOpsgenie import NotifyOpsgenie

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
    _logo_url = "https://images.ctfassets.net/zscdif0zqppk/3mlbsJDAmK402ER1sf0zUF/a48ac43fa38f395dd5f56c6ed29f22bb/mattermost-logo-png-transparent.png?h=250"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.MattermostWebhook"

    hostname: str = Field(
        default=...,
        description="The hostname of your Mattermost server.",
        example="Mattermost.example.com",
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

    channels: Optional[List[str]] = Field(
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
        from apprise.plugins.NotifyMattermost import NotifyMattermost

        url = SecretStr(
            NotifyMattermost(
                token=self.token.get_secret_value(),
                fullpath=self.path,
                host=self.hostname,
                botname=self.botname,
                channels=self.channels,
                include_image=self.include_image,
                port=self.port,
            ).url()
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
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/6ciCsTFsvUAiiIvTllMfOU/627e9513376ca457785118fbba6a858d/webhook_icon_138018.png?h=250"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.CustomWebhookNotificationBlock"

    name: str = Field(title="Name", description="Name of the webhook.")

    url: str = Field(
        title="Webhook URL",
        description="The webhook URL.",
        example="https://hooks.slack.com/XXX",
    )

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        default="POST", description="The webhook request method. Defaults to `POST`."
    )

    params: Optional[Dict[str, str]] = Field(
        default=None, title="Query Params", description="Custom query params."
    )
    json_data: Optional[dict] = Field(
        default=None,
        title="JSON Data",
        description="Send json data as payload.",
        example=(
            '{"text": "{{subject}}\\n{{body}}", "title": "{{name}}", "token":'
            ' "{{tokenFromSecrets}}"}'
        ),
    )
    form_data: Optional[Dict[str, str]] = Field(
        default=None,
        title="Form Data",
        description=(
            "Send form data as payload. Should not be used together with _JSON Data_."
        ),
        example=(
            '{"text": "{{subject}}\\n{{body}}", "title": "{{name}}", "token":'
            ' "{{tokenFromSecrets}}"}'
        ),
    )

    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers.")
    cookies: Optional[Dict[str, str]] = Field(None, description="Custom cookies.")

    timeout: float = Field(
        default=10, description="Request timeout in seconds. Defaults to 10."
    )

    secrets: SecretDict = Field(
        default_factory=lambda: SecretDict(dict()),
        title="Custom Secret Values",
        description="A dictionary of secret values to be substituted in other configs.",
        example='{"tokenFromSecrets":"SomeSecretToken"}',
    )

    def _build_request_args(self, body: str, subject: Optional[str]):
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
    @instrument_instance_method_call()
    async def notify(self, body: str, subject: Optional[str] = None):
        import httpx

        # make request with httpx
        client = httpx.AsyncClient(headers={"user-agent": "Prefect Notifications"})
        resp = await client.request(**self._build_request_args(body, subject))
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
    """

    _description = "Enables sending notifications via Sendgrid email service."
    _block_type_name = "Sendgrid Email"
    _block_type_slug = "sendgrid-email"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/3PcxFuO9XUqs7wU9MiUBMg/af6affa646899cc1712d14b7fc4c0f1f/email__1_.png?h=250"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/notifications/#prefect.blocks.notifications.SendgridEmail"

    api_key: SecretStr = Field(
        default=...,
        title="API Key",
        description="The API Key associated with your sendgrid account.",
    )

    sender_email: str = Field(
        title="Sender email id",
        description="The sender email id.",
        example="test-support@gmail.com",
    )

    to_emails: List[str] = Field(
        default=...,
        title="Recipient emails",
        description="Email ids of all recipients.",
        example="recipient1@gmail.com",
    )

    def block_initialization(self) -> None:
        from apprise.plugins.NotifySendGrid import NotifySendGrid

        url = SecretStr(
            NotifySendGrid(
                apikey=self.api_key.get_secret_value(),
                from_email=self.sender_email,
                targets=self.to_emails,
            ).url()
        )

        self._start_apprise_client(url)
