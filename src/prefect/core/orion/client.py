import contextvars

import httpx


class Client:
    def __init__(self, http_client: httpx.AsyncClient = None) -> None:
        self._client = http_client or httpx.AsyncClient(base_url="http://localhost/")

    async def post(self, route: str, **kwargs) -> httpx.Response:
        return await self._client.post(route, **kwargs)

    async def get(self, route: str) -> httpx.Response:
        return await self._client.get(route)


# Async safe singleton for storing the default client for the current frame
_CLIENT: contextvars.ContextVar["Client"] = contextvars.ContextVar("client")


def get_client() -> "Client":
    client = _CLIENT.get(None)
    if not client:
        client = Client()
        set_client(client)
    return client


def set_client(client: "Client") -> contextvars.Token:
    return _CLIENT.set(client)
