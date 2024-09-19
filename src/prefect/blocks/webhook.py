from typing import Optional

from httpx import AsyncClient, AsyncHTTPTransport, Response
from pydantic import Field, SecretStr
from typing_extensions import Literal

from prefect.blocks.core import Block
from prefect.types import SecretDict
from prefect.utilities.urls import validate_restricted_url

# Use a global HTTP transport to maintain a process-wide connection pool for
# interservice requests
_http_transport = AsyncHTTPTransport()
_insecure_http_transport = AsyncHTTPTransport(verify=False)


class Webhook(Block):
    """
    Block that enables calling webhooks.
    """

    _block_type_name = "Webhook"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/c7247cb359eb6cf276734d4b1fbf00fb8930e89e-250x250.png"  # type: ignore
    _documentation_url = (
        "https://docs.prefect.io/latest/automate/events/webhook-triggers"
    )

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        default="POST", description="The webhook request method. Defaults to `POST`."
    )

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="The webhook URL.",
        examples=["https://hooks.slack.com/XXX"],
    )

    headers: SecretDict = Field(
        default_factory=lambda: SecretDict(dict()),
        title="Webhook Headers",
        description="A dictionary of headers to send with the webhook request.",
    )
    allow_private_urls: bool = Field(
        default=True,
        description="Whether to allow notifications to private URLs. Defaults to True.",
    )
    verify: bool = Field(
        default=True,
        description="Whether or not to enforce a secure connection to the webhook.",
    )

    def block_initialization(self):
        if self.verify:
            self._client = AsyncClient(transport=_http_transport)
        else:
            self._client = AsyncClient(transport=_insecure_http_transport)

    async def call(self, payload: Optional[dict] = None) -> Response:
        """
        Call the webhook.

        Args:
            payload: an optional payload to send when calling the webhook.
        """
        if not self.allow_private_urls:
            validate_restricted_url(self.url.get_secret_value())

        async with self._client:
            return await self._client.request(
                method=self.method,
                url=self.url.get_secret_value(),
                headers=self.headers.get_secret_value(),
                json=payload,
            )
