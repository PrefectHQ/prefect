from typing import Dict, List, Optional
from urllib.parse import quote
from uuid import UUID

import httpx
import pydantic
from httpx import Response
from starlette import status
from typing_extensions import Self

from prefect.client.base import PrefectHttpxAsyncClient
from prefect.exceptions import ObjectNotFound
from prefect.logging import get_logger
from prefect.server.schemas.actions import DeploymentFlowRunCreate, StateCreate
from prefect.server.schemas.core import WorkPool
from prefect.server.schemas.filters import VariableFilter, VariableFilterName
from prefect.server.schemas.responses import DeploymentResponse, OrchestrationResult
from prefect.types import StrictVariableValue

logger = get_logger(__name__)


class BaseClient:
    _http_client: PrefectHttpxAsyncClient

    def __init__(self, additional_headers: Dict[str, str] = {}):
        from prefect.server.api.server import create_app

        # create_app caches application instances, and invoking it with no arguments
        # will point it to the the currently running server instance
        api_app = create_app()

        self._http_client = PrefectHttpxAsyncClient(
            transport=httpx.ASGITransport(app=api_app, raise_app_exceptions=False),
            headers={**additional_headers},
            base_url="http://prefect-in-memory/api",
            enable_csrf_support=False,
            raise_on_all_errors=False,
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
        return DeploymentResponse.model_validate(response.json())

    async def read_flow_raw(self, flow_id: UUID) -> Response:
        return await self._http_client.get(f"/flows/{flow_id}")

    async def create_flow_run(
        self, deployment_id: UUID, flow_run_create: DeploymentFlowRunCreate
    ) -> Response:
        return await self._http_client.post(
            f"/deployments/{deployment_id}/create_flow_run",
            json=flow_run_create.model_dump(mode="json"),
        )

    async def read_flow_run_raw(self, flow_run_id: UUID) -> Response:
        return await self._http_client.get(f"/flow_runs/{flow_run_id}")

    async def read_task_run_raw(self, task_run_id: UUID) -> Response:
        return await self._http_client.get(f"/task_runs/{task_run_id}")

    async def resume_flow_run(self, flow_run_id: UUID) -> OrchestrationResult:
        response = await self._http_client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )
        response.raise_for_status()
        return OrchestrationResult.model_validate(response.json())

    async def pause_deployment(self, deployment_id: UUID) -> Response:
        return await self._http_client.post(
            f"/deployments/{deployment_id}/pause_deployment",
        )

    async def resume_deployment(self, deployment_id: UUID) -> Response:
        return await self._http_client.post(
            f"/deployments/{deployment_id}/resume_deployment",
        )

    async def set_flow_run_state(
        self, flow_run_id: UUID, state: StateCreate
    ) -> Response:
        return await self._http_client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json={
                "state": state.model_dump(mode="json"),
                "force": False,
            },
        )

    async def pause_work_pool(self, work_pool_name: str) -> Response:
        return await self._http_client.patch(
            f"/work_pools/{quote(work_pool_name)}", json={"is_paused": True}
        )

    async def resume_work_pool(self, work_pool_name: str) -> Response:
        return await self._http_client.patch(
            f"/work_pools/{quote(work_pool_name)}", json={"is_paused": False}
        )

    async def read_work_pool_raw(self, work_pool_id: UUID) -> Response:
        return await self._http_client.post(
            "/work_pools/filter",
            json={"work_pools": {"id": {"any_": [str(work_pool_id)]}}},
        )

    async def read_work_pool(self, work_pool_id: UUID) -> Optional[WorkPool]:
        response = await self.read_work_pool_raw(work_pool_id)
        response.raise_for_status()

        pools = pydantic.TypeAdapter(List[WorkPool]).validate_python(response.json())
        return pools[0] if pools else None

    async def read_work_queue_raw(self, work_queue_id: UUID) -> Response:
        return await self._http_client.get(f"/work_queues/{work_queue_id}")

    async def read_work_queue_status_raw(self, work_queue_id: UUID) -> Response:
        return await self._http_client.get(f"/work_queues/{work_queue_id}/status")

    async def pause_work_queue(self, work_queue_id: UUID) -> Response:
        return await self._http_client.patch(
            f"/work_queues/{work_queue_id}",
            json={"is_paused": True},
        )

    async def resume_work_queue(self, work_queue_id: UUID) -> Response:
        return await self._http_client.patch(
            f"/work_queues/{work_queue_id}",
            json={"is_paused": False},
        )

    async def read_block_document_raw(
        self,
        block_document_id: UUID,
        include_secrets: bool = True,
    ) -> Response:
        return await self._http_client.get(
            f"/block_documents/{block_document_id}",
            params=dict(include_secrets=include_secrets),
        )

    VARIABLE_PAGE_SIZE = 200
    MAX_VARIABLES_PER_WORKSPACE = 1000

    async def read_workspace_variables(
        self, names: Optional[List[str]] = None
    ) -> Dict[str, StrictVariableValue]:
        variables: Dict[str, StrictVariableValue] = {}

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
                    "variables": filter.model_dump(),
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

    async def read_concurrency_limit_v2_raw(
        self, concurrency_limit_id: UUID
    ) -> Response:
        return await self._http_client.get(
            f"/v2/concurrency_limits/{concurrency_limit_id}"
        )


class WorkPoolsOrchestrationClient(BaseClient):
    async def __aenter__(self) -> Self:
        return self

    async def read_work_pool(self, work_pool_name: str) -> WorkPool:
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
            return WorkPool.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
