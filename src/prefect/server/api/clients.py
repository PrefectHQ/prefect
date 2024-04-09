from typing import Dict, List, Optional
from uuid import UUID

import httpx
from httpx import Response
from prefect._vendor.starlette import status
from typing_extensions import Self

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.exceptions import ObjectNotFound

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from prefect.client.base import PrefectHttpxClient
from prefect.logging import get_logger
from prefect.server.schemas.filters import VariableFilter, VariableFilterName
from prefect.server.schemas.responses import DeploymentResponse, WorkPoolResponse

logger = get_logger(__name__)


class BaseClient:
    _http_client: PrefectHttpxClient

    def __init__(self, additional_headers: Dict[str, str] = {}):
        from prefect.server.api.server import create_app

        # create_app caches application instances, and invoking it with no arguments
        # will point it to the the currently running server instance
        api_app = create_app()

        self._http_client = PrefectHttpxClient(
            transport=httpx.ASGITransport(app=api_app, raise_app_exceptions=False),
            headers={**additional_headers},
            base_url="http://prefect-in-memory/api",
            enable_csrf_support=False,
        )

    async def __aenter__(self) -> Self:
        await self._http_client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._http_client.__aexit__(*args)


class OrchestrationClient(BaseClient):
    async def read_deployment_raw(self, deployment_id: UUID) -> Response:
        return await self._http_client.get(f"/deployments/{deployment_id}")

    async def read_deployment(
        self, deployment_id: UUID
    ) -> Optional[DeploymentResponse]:
        try:
            response = await self.read_deployment_raw(deployment_id)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                return None
            raise
        return DeploymentResponse.parse_obj(response.json())

    VARIABLE_PAGE_SIZE = 200
    MAX_VARIABLES_PER_WORKSPACE = 1000

    async def read_workspace_variables(
        self, names: Optional[List[str]] = None
    ) -> Dict[str, str]:
        variables: Dict[str, str] = {}

        offset = 0

        filter = VariableFilter()

        if names is not None and not names:
            return variables
        elif names is not None:
            filter.name = VariableFilterName(any_=list(set(names)))

        for offset in range(
            0, self.MAX_VARIABLES_PER_WORKSPACE, self.VARIABLE_PAGE_SIZE
        ):
            response = await self._http_client.post(
                "/variables/filter",
                json={
                    "variables": filter.dict(),
                    "limit": self.VARIABLE_PAGE_SIZE,
                    "offset": offset,
                },
            )
            if response.status_code >= 300:
                response.raise_for_status()

            results = response.json()
            for variable in results:
                variables[variable["name"]] = variable["value"]

            if len(results) < self.VARIABLE_PAGE_SIZE:
                break

        return variables


class WorkPoolsOrchestrationClient(BaseClient):
    async def __aenter__(self) -> Self:
        return self

    async def read_work_pool(self, work_pool_name: str) -> WorkPoolResponse:
        """
        Reads information for a given work pool
        Args:
            work_pool_name: The name of the work pool to for which to get
                information.
        Returns:
            Information about the requested work pool.
        """
        try:
            response = await self._http_client.get(f"/work_pools/{work_pool_name}")
            response.raise_for_status()
            return pydantic.parse_obj_as(WorkPoolResponse, response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
