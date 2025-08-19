from __future__ import annotations

import warnings
from datetime import datetime
from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError

from prefect.client.base import ServerType
from prefect.client.orchestration.base import BaseAsyncClient, BaseClient

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.actions import (
        WorkPoolCreate,
        WorkPoolUpdate,
    )
    from prefect.client.schemas.filters import (
        WorkerFilter,
        WorkPoolFilter,
    )
    from prefect.client.schemas.objects import (
        Worker,
        WorkerMetadata,
        WorkPool,
    )
    from prefect.client.schemas.responses import WorkerFlowRunResponse

from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound, ObjectUnsupported


class WorkPoolClient(BaseClient):
    def send_worker_heartbeat(
        self,
        work_pool_name: str,
        worker_name: str,
        heartbeat_interval_seconds: float | None = None,
        get_worker_id: bool = False,
        worker_metadata: "WorkerMetadata | None" = None,
    ) -> "UUID | None":
        """
        Sends a worker heartbeat for a given work pool.

        Args:
            work_pool_name: The name of the work pool to heartbeat against.
            worker_name: The name of the worker sending the heartbeat.
            return_id: Whether to return the worker ID. Note: will return `None` if the connected server does not support returning worker IDs, even if `return_id` is `True`.
            worker_metadata: Metadata about the worker to send to the server.
        """
        from uuid import UUID

        params: dict[str, Any] = {
            "name": worker_name,
            "heartbeat_interval_seconds": heartbeat_interval_seconds,
        }
        if worker_metadata:
            params["metadata"] = worker_metadata.model_dump(mode="json")
        if get_worker_id:
            params["return_id"] = get_worker_id

        resp = self.request(
            "POST",
            "/work_pools/{work_pool_name}/workers/heartbeat",
            path_params={"work_pool_name": work_pool_name},
            json=params,
        )
        from prefect.settings import get_current_settings

        if (
            (
                self.server_type == ServerType.CLOUD
                or get_current_settings().testing.test_mode
            )
            and get_worker_id
            and resp.status_code == 200
        ):
            return UUID(resp.text)
        else:
            return None

    def read_workers_for_work_pool(
        self,
        work_pool_name: str,
        worker_filter: "WorkerFilter | None" = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list["Worker"]:
        """
        Reads workers for a given work pool.

        Args:
            work_pool_name: The name of the work pool for which to get
                member workers.
            worker_filter: Criteria by which to filter workers.
            limit: Limit for the worker query.
            offset: Limit for the worker query.
        """
        from prefect.client.schemas.objects import Worker

        response = self.request(
            "POST",
            "/work_pools/{work_pool_name}/workers/filter",
            path_params={"work_pool_name": work_pool_name},
            json={
                "workers": (
                    worker_filter.model_dump(mode="json", exclude_unset=True)
                    if worker_filter
                    else None
                ),
                "offset": offset,
                "limit": limit,
            },
        )

        return Worker.model_validate_list(response.json())

    def read_work_pool(self, work_pool_name: str) -> "WorkPool":
        """
        Reads information for a given work pool

        Args:
            work_pool_name: The name of the work pool to for which to get
                information.

        Returns:
            Information about the requested work pool.
        """
        from prefect.client.schemas.objects import WorkPool

        try:
            response = self.request(
                "GET",
                "/work_pools/{name}",
                path_params={"name": work_pool_name},
            )
            return WorkPool.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def read_work_pools(
        self,
        limit: int | None = None,
        offset: int = 0,
        work_pool_filter: "WorkPoolFilter | None" = None,
    ) -> list["WorkPool"]:
        """
        Reads work pools.

        Args:
            limit: Limit for the work pool query.
            offset: Offset for the work pool query.
            work_pool_filter: Criteria by which to filter work pools.

        Returns:
            A list of work pools.
        """
        from prefect.client.schemas.objects import WorkPool

        body: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "work_pools": (
                work_pool_filter.model_dump(mode="json") if work_pool_filter else None
            ),
        }
        response = self.request("POST", "/work_pools/filter", json=body)
        return WorkPool.model_validate_list(response.json())

    def create_work_pool(
        self,
        work_pool: "WorkPoolCreate",
        overwrite: bool = False,
    ) -> "WorkPool":
        """
        Creates a work pool with the provided configuration.

        Args:
            work_pool: Desired configuration for the new work pool.

        Returns:
            Information about the newly created work pool.
        """
        from prefect.client.schemas.actions import WorkPoolUpdate
        from prefect.client.schemas.objects import WorkPool

        try:
            response = self.request(
                "POST",
                "/work_pools/",
                json=work_pool.model_dump(mode="json", exclude_unset=True),
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            if e.response.status_code == 403 and "plan does not support" in str(e):
                raise ObjectUnsupported(http_exc=e) from e
            if e.response.status_code == 409:
                if overwrite:
                    existing_work_pool = self.read_work_pool(
                        work_pool_name=work_pool.name
                    )
                    if existing_work_pool.type != work_pool.type:
                        warnings.warn(
                            "Overwriting work pool type is not supported. Ignoring provided type.",
                            category=UserWarning,
                        )
                    self.update_work_pool(
                        work_pool_name=work_pool.name,
                        work_pool=WorkPoolUpdate.model_validate(
                            work_pool.model_dump(exclude={"name", "type"})
                        ),
                    )
                    response = self.request(
                        "GET",
                        "/work_pools/{name}",
                        path_params={"name": work_pool.name},
                    )
                else:
                    raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise

        return WorkPool.model_validate(response.json())

    def update_work_pool(
        self,
        work_pool_name: str,
        work_pool: "WorkPoolUpdate",
    ) -> None:
        """
        Updates a work pool.

        Args:
            work_pool_name: Name of the work pool to update.
            work_pool: Fields to update in the work pool.
        """
        try:
            self.request(
                "PATCH",
                "/work_pools/{name}",
                path_params={"name": work_pool_name},
                json=work_pool.model_dump(mode="json", exclude_unset=True),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def delete_work_pool(
        self,
        work_pool_name: str,
    ) -> None:
        """
        Deletes a work pool.

        Args:
            work_pool_name: Name of the work pool to delete.
        """
        try:
            self.request(
                "DELETE",
                "/work_pools/{name}",
                path_params={"name": work_pool_name},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def get_scheduled_flow_runs_for_work_pool(
        self,
        work_pool_name: str,
        work_queue_names: list[str] | None = None,
        scheduled_before: datetime | None = None,
    ) -> list["WorkerFlowRunResponse"]:
        """
        Retrieves scheduled flow runs for the provided set of work pool queues.

        Args:
            work_pool_name: The name of the work pool that the work pool
                queues are associated with.
            work_queue_names: The names of the work pool queues from which
                to get scheduled flow runs.
            scheduled_before: Datetime used to filter returned flow runs. Flow runs
                scheduled for after the given datetime string will not be returned.

        Returns:
            A list of worker flow run responses containing information about the
            retrieved flow runs.
        """
        from prefect.client.schemas.responses import WorkerFlowRunResponse

        body: dict[str, Any] = {}
        if work_queue_names is not None:
            body["work_queue_names"] = list(work_queue_names)
        if scheduled_before:
            body["scheduled_before"] = str(scheduled_before)

        try:
            response = self.request(
                "POST",
                "/work_pools/{name}/get_scheduled_flow_runs",
                path_params={"name": work_pool_name},
                json=body,
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

        return WorkerFlowRunResponse.model_validate_list(response.json())


class WorkPoolAsyncClient(BaseAsyncClient):
    async def send_worker_heartbeat(
        self,
        work_pool_name: str,
        worker_name: str,
        heartbeat_interval_seconds: float | None = None,
        get_worker_id: bool = False,
        worker_metadata: "WorkerMetadata | None" = None,
    ) -> "UUID | None":
        """
        Sends a worker heartbeat for a given work pool.

        Args:
            work_pool_name: The name of the work pool to heartbeat against.
            worker_name: The name of the worker sending the heartbeat.
            return_id: Whether to return the worker ID. Note: will return `None` if the connected server does not support returning worker IDs, even if `return_id` is `True`.
            worker_metadata: Metadata about the worker to send to the server.
        """
        from uuid import UUID

        params: dict[str, Any] = {
            "name": worker_name,
            "heartbeat_interval_seconds": heartbeat_interval_seconds,
        }
        if worker_metadata:
            params["metadata"] = worker_metadata.model_dump(mode="json")
        if get_worker_id:
            params["return_id"] = get_worker_id

        resp = await self.request(
            "POST",
            "/work_pools/{work_pool_name}/workers/heartbeat",
            path_params={"work_pool_name": work_pool_name},
            json=params,
        )
        from prefect.settings import get_current_settings

        if (
            (
                self.server_type == ServerType.CLOUD
                or get_current_settings().testing.test_mode
            )
            and get_worker_id
            and resp.status_code == 200
        ):
            return UUID(resp.text)
        else:
            return None

    async def read_workers_for_work_pool(
        self,
        work_pool_name: str,
        worker_filter: "WorkerFilter | None" = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list["Worker"]:
        """
        Reads workers for a given work pool.

        Args:
            work_pool_name: The name of the work pool for which to get
                member workers.
            worker_filter: Criteria by which to filter workers.
            limit: Limit for the worker query.
            offset: Limit for the worker query.
        """
        from prefect.client.schemas.objects import Worker

        response = await self.request(
            "POST",
            "/work_pools/{work_pool_name}/workers/filter",
            path_params={"work_pool_name": work_pool_name},
            json={
                "workers": (
                    worker_filter.model_dump(mode="json", exclude_unset=True)
                    if worker_filter
                    else None
                ),
                "offset": offset,
                "limit": limit,
            },
        )

        return Worker.model_validate_list(response.json())

    async def read_work_pool(self, work_pool_name: str) -> "WorkPool":
        """
        Reads information for a given work pool

        Args:
            work_pool_name: The name of the work pool to for which to get
                information.

        Returns:
            Information about the requested work pool.
        """
        from prefect.client.schemas.objects import WorkPool

        try:
            response = await self.request(
                "GET",
                "/work_pools/{name}",
                path_params={"name": work_pool_name},
            )
            return WorkPool.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_work_pools(
        self,
        limit: int | None = None,
        offset: int = 0,
        work_pool_filter: "WorkPoolFilter | None" = None,
    ) -> list["WorkPool"]:
        """
        Reads work pools.

        Args:
            limit: Limit for the work pool query.
            offset: Offset for the work pool query.
            work_pool_filter: Criteria by which to filter work pools.

        Returns:
            A list of work pools.
        """
        from prefect.client.schemas.objects import WorkPool

        body: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "work_pools": (
                work_pool_filter.model_dump(mode="json") if work_pool_filter else None
            ),
        }
        response = await self.request("POST", "/work_pools/filter", json=body)
        return WorkPool.model_validate_list(response.json())

    async def create_work_pool(
        self,
        work_pool: "WorkPoolCreate",
        overwrite: bool = False,
    ) -> "WorkPool":
        """
        Creates a work pool with the provided configuration.

        Args:
            work_pool: Desired configuration for the new work pool.

        Returns:
            Information about the newly created work pool.
        """
        from prefect.client.schemas.actions import WorkPoolUpdate
        from prefect.client.schemas.objects import WorkPool

        try:
            response = await self.request(
                "POST",
                "/work_pools/",
                json=work_pool.model_dump(mode="json", exclude_unset=True),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                if overwrite:
                    existing_work_pool = await self.read_work_pool(
                        work_pool_name=work_pool.name
                    )
                    if existing_work_pool.type != work_pool.type:
                        warnings.warn(
                            "Overwriting work pool type is not supported. Ignoring provided type.",
                            category=UserWarning,
                        )
                    await self.update_work_pool(
                        work_pool_name=work_pool.name,
                        work_pool=WorkPoolUpdate.model_validate(
                            work_pool.model_dump(exclude={"name", "type"})
                        ),
                    )
                    response = await self.request(
                        "GET",
                        "/work_pools/{name}",
                        path_params={"name": work_pool.name},
                    )
                else:
                    raise ObjectAlreadyExists(http_exc=e) from e
            else:
                raise

        return WorkPool.model_validate(response.json())

    async def update_work_pool(
        self,
        work_pool_name: str,
        work_pool: "WorkPoolUpdate",
    ) -> None:
        """
        Updates a work pool.

        Args:
            work_pool_name: Name of the work pool to update.
            work_pool: Fields to update in the work pool.
        """
        try:
            await self.request(
                "PATCH",
                "/work_pools/{name}",
                path_params={"name": work_pool_name},
                json=work_pool.model_dump(mode="json", exclude_unset=True),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_work_pool(
        self,
        work_pool_name: str,
    ) -> None:
        """
        Deletes a work pool.

        Args:
            work_pool_name: Name of the work pool to delete.
        """
        try:
            await self.request(
                "DELETE",
                "/work_pools/{name}",
                path_params={"name": work_pool_name},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def get_scheduled_flow_runs_for_work_pool(
        self,
        work_pool_name: str,
        work_queue_names: list[str] | None = None,
        scheduled_before: datetime | None = None,
    ) -> list["WorkerFlowRunResponse"]:
        """
        Retrieves scheduled flow runs for the provided set of work pool queues.

        Args:
            work_pool_name: The name of the work pool that the work pool
                queues are associated with.
            work_queue_names: The names of the work pool queues from which
                to get scheduled flow runs.
            scheduled_before: Datetime used to filter returned flow runs. Flow runs
                scheduled for after the given datetime string will not be returned.

        Returns:
            A list of worker flow run responses containing information about the
            retrieved flow runs.
        """
        from prefect.client.schemas.responses import WorkerFlowRunResponse

        body: dict[str, Any] = {}
        if work_queue_names is not None:
            body["work_queue_names"] = list(work_queue_names)
        if scheduled_before:
            body["scheduled_before"] = str(scheduled_before)

        try:
            response = await self.request(
                "POST",
                "/work_pools/{name}/get_scheduled_flow_runs",
                path_params={"name": work_pool_name},
                json=body,
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

        return WorkerFlowRunResponse.model_validate_list(response.json())
