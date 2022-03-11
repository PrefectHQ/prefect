import anyio
import httpx


class PrefectHttpxClient(httpx.AsyncClient):
    RETRY_MAX = 5

    async def send(self, *args, **kwargs):
        response = await super().send(*args, **kwargs)

        retry_count = 0
        while response.status_code == 429 and retry_count < self.RETRY_MAX:
            retry_count += 1
            # respect CloudFlare conventions for handling rate-limit response headers
            # see https://support.cloudflare.com/hc/en-us/articles/115001635128-Configuring-Rate-Limiting-from-UI
            retry_seconds = int(response.headers["Retry-After"])
            await anyio.sleep(retry_seconds)
            response = await super().send(*args, **kwargs)

        return response
