import anyio
import httpx
from fastapi import status
from httpx._models import Response


class PrefectHttpxClient(httpx.AsyncClient):
    RETRY_MAX = 5

    async def _httpx_send(self, *args, **kwargs) -> Response:
        return await super().send(*args, **kwargs)

    async def send(self, *args, **kwargs) -> Response:
        """
        Build and send a request with prefect-specific error and retry handling.
        """
        retry_count = 0
        response = await self._httpx_send(*args, **kwargs)

        while (
            response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            and retry_count < self.RETRY_MAX
        ):
            retry_count += 1
            # respect CloudFlare conventions for handling rate-limit response headers
            # see https://support.cloudflare.com/hc/en-us/articles/115001635128-Configuring-Rate-Limiting-from-UI
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                retry_seconds = float(retry_after)
            else:
                retry_seconds = 2**retry_count  # default to exponential backoff

            await anyio.sleep(retry_seconds)
            response = await self._httpx_send(*args, **kwargs)

        response.raise_for_status()

        return response
