import re
from typing import Dict, List

import anyio
import httpx
from fastapi import status

import prefect.context
import prefect.settings
from prefect.exceptions import PrefectException
from prefect.settings import PREFECT_API_KEY, PREFECT_CLOUD_URL


def get_cloud_client(
    host: str = None,
    api_key: str = None,
    httpx_settings: dict = None,
    infer_cloud_url: bool = False,
) -> "CloudClient":
    if httpx_settings is not None:
        httpx_settings = httpx_settings.copy()

    if infer_cloud_url is False:
        host = host or PREFECT_CLOUD_URL.value()
    else:
        configured_url = prefect.settings.PREFECT_API_URL.value()
        host = re.sub(r"accounts/.{36}/workspaces/.{36}\Z", "", configured_url)

    return CloudClient(
        host=host,
        api_key=api_key or PREFECT_API_KEY.value(),
        httpx_settings=httpx_settings,
    )


class CloudUnauthorizedError(PrefectException):
    """
    Raised when the CloudClient receives a 401 or 403 from the Cloud API.
    """


class CloudClient:
    def __init__(
        self,
        host: str,
        api_key: str,
        httpx_settings: dict = None,
    ) -> None:

        httpx_settings = httpx_settings or dict()
        httpx_settings.setdefault("headers", dict())
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        self._client = httpx.AsyncClient(**httpx_settings)

    async def api_healthcheck(self):
        """
        Attempts to connect to the Cloud API and raises the encountered exception if not
        successful.

        If successful, returns `None`.
        """
        with anyio.fail_after(10):
            await self.read_workspaces()

    async def read_workspaces(self) -> List[Dict]:
        return await self.get("/me/workspaces")

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._client.__aexit__(*exc_info)

    def __enter__(self):
        raise RuntimeError(
            "The `CloudClient` must be entered with an async context. Use 'async "
            "with CloudClient(...)' not 'with CloudClient(...)'"
        )

    def __exit__(self, *_):
        assert False, "This should never be called but must be defined for __enter__"

    async def get(self, route, **kwargs):
        try:
            res = await self._client.get(route, **kwargs)
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                raise CloudUnauthorizedError
            else:
                raise exc

        return res.json()
