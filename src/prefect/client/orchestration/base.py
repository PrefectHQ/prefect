from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypeAlias

from prefect.client.orchestration.routes import ServerRoutes

if TYPE_CHECKING:
    from httpx import AsyncClient, Client, Response

HTTP_METHODS: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


class BaseClient:
    def __init__(self, client: "Client"):
        self._client = client
        super().__init__()

    def request(
        self,
        method: HTTP_METHODS,
        path: ServerRoutes,
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "Response":
        if path_params:
            path = path.format(**path_params)  # type: ignore
        return self._client.request(method, path, params=params, **kwargs)


class BaseAsyncClient:
    def __init__(self, client: "AsyncClient"):
        self._client = client
        super().__init__()

    async def request(
        self,
        method: HTTP_METHODS,
        path: ServerRoutes,
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "Response":
        if path_params:
            path = path.format(**path_params)  # type: ignore
        return await self._client.request(method, path, params=params, **kwargs)
