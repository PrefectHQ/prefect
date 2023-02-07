from typing import Optional

from httpx import AsyncClient, AsyncHTTPTransport, Response
from pydantic import Field, SecretStr
from typing_extensions import Literal

from prefect.blocks.core import Block
from prefect.blocks.fields import SecretDict

# Use a global HTTP transport to maintain a process-wide connection pool for
# interservice requests
_http_transport = AsyncHTTPTransport()


class Webhook(Block):
    """
    Block that enables calling webhooks.
    """

    _block_type_name = "Webhook"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/6ciCsTFsvUAiiIvTllMfOU/627e9513376ca457785118fbba6a858d/webhook_icon_138018.png?h=250"  # type: ignore
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/webhook/#prefect.blocks.webhook.Webhook"

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        default="POST", description="The webhook request method. Defaults to `POST`."
    )

    url: SecretStr = Field(
        default=...,
        title="Webhook URL",
        description="The webhook URL.",
        example="https://hooks.slack.com/XXX",
    )

    headers: SecretDict = Field(
        default_factory=lambda: SecretDict(dict()),
        title="Webhook Headers",
        description="A dictionary of headers to send with the webhook request.",
    )

    def block_initialization(self):
        self._client = AsyncClient(transport=_http_transport)

    async def call(self, payload: Optional[dict] = None) -> Response:
        """
        Call the webhook.

        Args:
            payload: an optional payload to send when calling the webhook.
        """
        async with self._client:
            return await self._client.request(
                method=self.method,
                url=self.url.get_secret_value(),
                headers=self.headers.get_secret_value(),
                json=payload,
            )
