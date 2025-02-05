from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from httpx import AsyncClient, Client, Response

    from prefect.client.base import ServerType
    from prefect.client.orchestration.routes import ServerRoutes

HTTP_METHODS: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


class BaseClient:
    server_type: "ServerType"

    def __init__(self, client: "Client"):
        self._client = client

    def request(
        self,
        method: HTTP_METHODS,
        path: "ServerRoutes",
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "Response":
        if path_params:
            path = path.format(**path_params)  # type: ignore
        request = self._client.build_request(method, path, params=params, **kwargs)
        return self._client.send(request)


class BaseAsyncClient:
    server_type: "ServerType"

    def __init__(self, client: "AsyncClient"):
        self._client = client

    async def request(
        self,
        method: HTTP_METHODS,
        path: "ServerRoutes",
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "Response":
        if path_params:
            path = path.format(**path_params)  # type: ignore
        request = self._client.build_request(method, path, params=params, **kwargs)
        return await self._client.send(request)
