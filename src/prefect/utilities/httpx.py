import anyio
import httpx
import typing


class PrefectHttpxClient(httpx.AsyncClient):
    async def send(self, *args, **kwargs):
        response = await super().send(*args, **kwargs)

        if response.status_code == 429:
            # respect CloudFlare conventions for handling rate-limit response headers
            # see https://support.cloudflare.com/hc/en-us/articles/115001635128-Configuring-Rate-Limiting-from-UI
            retry_seconds = int(response.headers["Retry-After"])
            await anyio.sleep(retry_seconds)
            response = await super().send(*args, **kwargs)

        return response
