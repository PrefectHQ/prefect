from __future__ import annotations

from typing import Any

from httpx import AsyncClient, AsyncHTTPTransport, Response
from pydantic import Field, HttpUrl, SecretStr
from typing_extensions import Literal

from prefect.blocks.core import Block
from prefect.types import SecretDict
from prefect.utilities.urls import (
    SSRFProtectedAsyncHTTPTransport,
    validate_restricted_url,
)

# Use a global HTTP transport to maintain a process-wide connection pool for
# interservice requests
_http_transport = AsyncHTTPTransport()
_insecure_http_transport = AsyncHTTPTransport(verify=False)
# Separate pools for calls that must be protected from DNS-rebinding SSRF.  The
# protected transport validates the resolved IP at connection time and connects
# to the pre-resolved address, closing the TOCTOU window exploited by DNS
# rebinding attacks.
_safe_http_transport = SSRFProtectedAsyncHTTPTransport()
_safe_insecure_http_transport = SSRFProtectedAsyncHTTPTransport(verify=False)


class Webhook(Block):
    """
    Block that enables calling webhooks.
    """

    _block_type_name = "Webhook"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/c7247cb359eb6cf276734d4b1fbf00fb8930e89e-250x250.png"  # type: ignore
    _documentation_url = HttpUrl(
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

    def block_initialization(self) -> None:
        if self.allow_private_urls:
            transport = _http_transport if self.verify else _insecure_http_transport
        else:
            transport = (
                _safe_http_transport if self.verify else _safe_insecure_http_transport
            )
        self._client = AsyncClient(transport=transport)

    async def call(self, payload: dict[str, Any] | str | None = None) -> Response:
        """
        Call the webhook.

        Args:
            payload: an optional payload to send when calling the webhook.
        """
        if not self.allow_private_urls:
            validate_restricted_url(self.url.get_secret_value())

        async with self._client:
            if isinstance(payload, str):
                return await self._client.request(
                    method=self.method,
                    url=self.url.get_secret_value(),
                    headers=self.headers.get_secret_value(),
                    content=payload,
                )
            else:
                return await self._client.request(
                    method=self.method,
                    url=self.url.get_secret_value(),
                    headers=self.headers.get_secret_value(),
                    json=payload,
                )
