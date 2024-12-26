from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient, Client


class BaseClient:
    def __init__(self, client: "Client"):
        self._client = client


class BaseAsyncClient:
    def __init__(self, client: "AsyncClient"):
        self._client = client
