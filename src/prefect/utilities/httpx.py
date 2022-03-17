import typing

import anyio
import httpx
from httpx._client import USE_CLIENT_DEFAULT, UseClientDefault
from httpx._models import Response
from httpx._types import (
    AuthTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestFiles,
    TimeoutTypes,
    URLTypes,
)

from prefect.settings import PREFECT_API_REQUEST_TIMEOUT


class PrefectHttpxClient(httpx.AsyncClient):
    RETRY_MAX = 5

    async def send(self, *args, **kwargs) -> Response:
        """
        Build and send a request with prefect-specific error and retry handling.
        """
        retry_count = 0
        response = await super().send(*args, **kwargs)

        while response.status_code == 429 and retry_count < self.RETRY_MAX:
            retry_count += 1
            # respect CloudFlare conventions for handling rate-limit response headers
            # see https://support.cloudflare.com/hc/en-us/articles/115001635128-Configuring-Rate-Limiting-from-UI
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                retry_seconds = float(retry_after)
            else:
                retry_seconds = 2**retry_count  # default to exponential backoff

            await anyio.sleep(retry_seconds)
            response = await super().send(*args, **kwargs)

        response.raise_for_status()

        return response
