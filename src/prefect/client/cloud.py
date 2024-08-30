import re
from typing import Any, Dict, List, Optional, cast

import anyio
import httpx
import pydantic
from starlette import status

import prefect.context
import prefect.settings
from prefect.client.base import PrefectHttpxAsyncClient
from prefect.client.schemas.objects import (
    IPAllowlist,
    IPAllowlistMyAccessResponse,
    Workspace,
)
from prefect.exceptions import ObjectNotFound, PrefectException
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_CLOUD_API_URL,
    PREFECT_UNIT_TEST_MODE,
)

PARSE_API_URL_REGEX = re.compile(r"accounts/(.{36})/workspaces/(.{36})")


def get_cloud_client(
    host: Optional[str] = None,
    api_key: Optional[str] = None,
    httpx_settings: Optional[dict] = None,
    infer_cloud_url: bool = False,
) -> "CloudClient":
    """
    Needs a docstring.
    """
    if httpx_settings is not None:
        httpx_settings = httpx_settings.copy()

    if infer_cloud_url is False:
        host = host or PREFECT_CLOUD_API_URL.value()
    else:
        configured_url = prefect.settings.PREFECT_API_URL.value()
        host = re.sub(PARSE_API_URL_REGEX, "", configured_url)

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
        httpx_settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        httpx_settings = httpx_settings or dict()
        httpx_settings.setdefault("headers", dict())
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        if not PREFECT_UNIT_TEST_MODE.value():
            httpx_settings.setdefault("follow_redirects", True)
        self._client = PrefectHttpxAsyncClient(
            **httpx_settings, enable_csrf_support=False
        )

        api_url = prefect.settings.PREFECT_API_URL.value() or ""
        if match := (
            re.search(PARSE_API_URL_REGEX, host)
            or re.search(PARSE_API_URL_REGEX, api_url)
        ):
            self.account_id, self.workspace_id = match.groups()

    @property
    def account_base_url(self) -> str:
        if not self.account_id:
            raise ValueError("Account ID not set")

        return f"accounts/{self.account_id}"

    @property
    def workspace_base_url(self) -> str:
        if not self.workspace_id:
            raise ValueError("Workspace ID not set")

        return f"{self.account_base_url}/workspaces/{self.workspace_id}"

    async def api_healthcheck(self):
        """
        Attempts to connect to the Cloud API and raises the encountered exception if not
        successful.

        If successful, returns `None`.
        """
        with anyio.fail_after(10):
            await self.read_workspaces()

    async def read_workspaces(self) -> List[Workspace]:
        workspaces = pydantic.TypeAdapter(List[Workspace]).validate_python(
            await self.get("/me/workspaces")
        )
        return workspaces

    async def read_worker_metadata(self) -> Dict[str, Any]:
        response = await self.get(
            f"{self.workspace_base_url}/collections/work_pool_types"
        )
        return cast(Dict[str, Any], response)

    async def read_account_settings(self) -> Dict[str, Any]:
        response = await self.get(f"{self.account_base_url}/settings")
        return cast(Dict[str, Any], response)

    async def update_account_settings(self, settings: Dict[str, Any]):
        await self.request(
            "PATCH",
            f"{self.account_base_url}/settings",
            json=settings,
        )

    async def read_account_ip_allowlist(self) -> IPAllowlist:
        response = await self.get(f"{self.account_base_url}/ip_allowlist")
        return IPAllowlist.model_validate(response)

    async def update_account_ip_allowlist(self, updated_allowlist: IPAllowlist):
        await self.request(
            "PUT",
            f"{self.account_base_url}/ip_allowlist",
            json=updated_allowlist.model_dump(mode="json"),
        )

    async def check_ip_allowlist_access(self) -> IPAllowlistMyAccessResponse:
        response = await self.get(f"{self.account_base_url}/ip_allowlist/my_access")
        return IPAllowlistMyAccessResponse.model_validate(response)

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
        return await self.request("GET", route, **kwargs)

    async def request(self, method, route, **kwargs):
        try:
            res = await self._client.request(method, route, **kwargs)
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                raise CloudUnauthorizedError(str(exc)) from exc
            elif exc.response.status_code == status.HTTP_404_NOT_FOUND:
                raise ObjectNotFound(http_exc=exc) from exc
            else:
                raise

        if res.status_code == status.HTTP_204_NO_CONTENT:
            return

        return res.json()
