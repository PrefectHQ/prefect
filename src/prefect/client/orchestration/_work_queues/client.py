from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError
from zoneinfo import ZoneInfo

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas import FlowRun
    from prefect.client.schemas.filters import (
        WorkQueueFilter,
    )
    from prefect.client.schemas.objects import (
        WorkQueue,
        WorkQueueStatusDetail,
    )


class WorkQueueClient(BaseClient):
    def create_work_queue(
        self,
        name: str,
        description: str | None = None,
        is_paused: bool | None = None,
        concurrency_limit: int | None = None,
        priority: int | None = None,
        work_pool_name: str | None = None,
    ) -> "WorkQueue":
        """
        Create a work queue.

        Args:
            name: a unique name for the work queue
            description: An optional description for the work queue.
            is_paused: Whether or not the work queue is paused.
            concurrency_limit: An optional concurrency limit for the work queue.
            priority: The queue's priority. Lower values are higher priority (1 is the highest).
            work_pool_name: The name of the work pool to use for this queue.

        Raises:
            ObjectAlreadyExists: If request returns 409
            httpx.RequestError: If request fails

        Returns:
            The created work queue
        """
        from prefect.client.schemas.actions import WorkQueueCreate
        from prefect.client.schemas.objects import WorkQueue

        create_model = WorkQueueCreate(name=name, filter=None)
        if description is not None:
            create_model.description = description
        if is_paused is not None:
            create_model.is_paused = is_paused
        if concurrency_limit is not None:
            create_model.concurrency_limit = concurrency_limit
        if priority is not None:
            create_model.priority = priority

        data = create_model.model_dump(mode="json")
        try:
            if work_pool_name is not None:
                response = self.request(
                    "POST",
                    "/work_pools/{work_pool_name}/queues",
                    path_params={"work_pool_name": work_pool_name},
                    json=data,
                )
            else:
                response = self.request("POST", "/work_queues/", json=data)
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            elif e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueue.model_validate(response.json())

    def read_work_queue_by_name(
        self,
        name: str,
        work_pool_name: str | None = None,
    ) -> "WorkQueue":
        """
        Read a work queue by name.

        Args:
            name (str): a unique name for the work queue
            work_pool_name (str, optional): the name of the work pool
                the queue belongs to.

        Raises:
            ObjectNotFound: if no work queue is found
            HTTPStatusError: other status errors

        Returns:
            WorkQueue: a work queue API object
        """
        from prefect.client.schemas.objects import WorkQueue

        try:
            if work_pool_name is not None:
                response = self.request(
                    "GET",
                    "/work_pools/{work_pool_name}/queues/{name}",
                    path_params={"work_pool_name": work_pool_name, "name": name},
                )
            else:
                response = self.request(
                    "GET", "/work_queues/name/{name}", path_params={"name": name}
                )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

        return WorkQueue.model_validate(response.json())

    def update_work_queue(self, id: "UUID", **kwargs: Any) -> None:
        """
        Update properties of a work queue.

        Args:
            id: the ID of the work queue to update
            **kwargs: the fields to update

        Raises:
            ValueError: if no kwargs are provided
            ObjectNotFound: if request returns 404
            httpx.RequestError: if the request fails

        """

        from prefect.client.schemas.actions import WorkQueueUpdate

        if not kwargs:
            raise ValueError("No fields provided to update.")

        data = WorkQueueUpdate(**kwargs).model_dump(mode="json", exclude_unset=True)
        try:
            self.request(
                "PATCH", "/work_queues/{id}", path_params={"id": id}, json=data
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def get_runs_in_work_queue(
        self,
        id: "UUID",
        limit: int = 10,
        scheduled_before: datetime.datetime | None = None,
    ) -> list["FlowRun"]:
        """
        Read flow runs off a work queue.

        Args:
            id: the id of the work queue to read from
            limit: a limit on the number of runs to return
            scheduled_before: a timestamp; only runs scheduled before this time will be returned.
                Defaults to now.

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            List[FlowRun]: a list of FlowRun objects read from the queue
        """
        from prefect.client.schemas import FlowRun

        if scheduled_before is None:
            scheduled_before = datetime.datetime.now(ZoneInfo("UTC"))

        try:
            response = self.request(
                "POST",
                "/work_queues/{id}/get_runs",
                path_params={"id": id},
                json={
                    "limit": limit,
                    "scheduled_before": scheduled_before.isoformat(),
                },
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return FlowRun.model_validate_list(response.json())

    def read_work_queue(
        self,
        id: "UUID",
    ) -> "WorkQueue":
        """
        Read a work queue.

        Args:
            id: the id of the work queue to load

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            WorkQueue: an instantiated WorkQueue object
        """

        from prefect.client.schemas.objects import WorkQueue

        try:
            response = self.request("GET", "/work_queues/{id}", path_params={"id": id})
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueue.model_validate(response.json())

    def read_work_queue_status(
        self,
        id: "UUID",
    ) -> "WorkQueueStatusDetail":
        """
        Read a work queue status.

        Args:
            id: the id of the work queue to load

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            WorkQueueStatus: an instantiated WorkQueueStatus object
        """

        from prefect.client.schemas.objects import WorkQueueStatusDetail

        try:
            response = self.request(
                "GET", "/work_queues/{id}/status", path_params={"id": id}
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueueStatusDetail.model_validate(response.json())

    def match_work_queues(
        self,
        prefixes: list[str],
        work_pool_name: str | None = None,
    ) -> list["WorkQueue"]:
        """
        Query the Prefect API for work queues with names with a specific prefix.

        Args:
            prefixes: a list of strings used to match work queue name prefixes
            work_pool_name: an optional work pool name to scope the query to

        Returns:
            a list of WorkQueue model representations
                of the work queues
        """
        from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName

        page_length = 100
        current_page = 0
        work_queues: list["WorkQueue"] = []

        while True:
            new_queues = self.read_work_queues(
                work_pool_name=work_pool_name,
                offset=current_page * page_length,
                limit=page_length,
                work_queue_filter=WorkQueueFilter(
                    name=WorkQueueFilterName(startswith_=prefixes)
                ),
            )
            if not new_queues:
                break
            work_queues += new_queues
            current_page += 1

        return work_queues

    def delete_work_queue_by_id(
        self,
        id: "UUID",
    ) -> None:
        """
        Delete a work queue by its ID.

        Args:
            id: the id of the work queue to delete

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """

        try:
            self.request("DELETE", "/work_queues/{id}", path_params={"id": id})
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def read_work_queues(
        self,
        work_pool_name: str | None = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list["WorkQueue"]:
        """
        Retrieves queues for a work pool.

        Args:
            work_pool_name: Name of the work pool for which to get queues.
            work_queue_filter: Criteria by which to filter queues.
            limit: Limit for the queue query.
            offset: Offset for the queue query.

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            List of queues for the specified work pool.
        """
        from prefect.client.schemas.objects import WorkQueue

        json: dict[str, Any] = {
            "work_queues": (
                work_queue_filter.model_dump(mode="json", exclude_unset=True)
                if work_queue_filter
                else None
            ),
            "limit": limit,
            "offset": offset,
        }

        if work_pool_name:
            try:
                response = self.request(
                    "POST",
                    "/work_pools/{work_pool_name}/queues/filter",
                    path_params={"work_pool_name": work_pool_name},
                    json=json,
                )
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ObjectNotFound(http_exc=e) from e
                else:
                    raise
        else:
            response = self.request("POST", "/work_queues/filter", json=json)

        return WorkQueue.model_validate_list(response.json())


class AsyncWorkQueueClient(BaseAsyncClient):
    async def create_work_queue(
        self,
        name: str,
        description: str | None = None,
        is_paused: bool | None = None,
        concurrency_limit: int | None = None,
        priority: int | None = None,
        work_pool_name: str | None = None,
    ) -> "WorkQueue":
        """
        Create a work queue.

        Args:
            name: a unique name for the work queue
            description: An optional description for the work queue.
            is_paused: Whether or not the work queue is paused.
            concurrency_limit: An optional concurrency limit for the work queue.
            priority: The queue's priority. Lower values are higher priority (1 is the highest).
            work_pool_name: The name of the work pool to use for this queue.

        Raises:
            ObjectAlreadyExists: If request returns 409
            httpx.RequestError: If request fails

        Returns:
            The created work queue
        """
        from prefect.client.schemas.actions import WorkQueueCreate
        from prefect.client.schemas.objects import WorkQueue

        create_model = WorkQueueCreate(name=name, filter=None)
        if description is not None:
            create_model.description = description
        if is_paused is not None:
            create_model.is_paused = is_paused
        if concurrency_limit is not None:
            create_model.concurrency_limit = concurrency_limit
        if priority is not None:
            create_model.priority = priority

        data = create_model.model_dump(mode="json")
        try:
            if work_pool_name is not None:
                response = await self.request(
                    "POST",
                    "/work_pools/{work_pool_name}/queues",
                    path_params={"work_pool_name": work_pool_name},
                    json=data,
                )
            else:
                response = await self.request("POST", "/work_queues/", json=data)
        except HTTPStatusError as e:
            if e.response.status_code == 409:
                raise ObjectAlreadyExists(http_exc=e) from e
            elif e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueue.model_validate(response.json())

    async def read_work_queue_by_name(
        self,
        name: str,
        work_pool_name: str | None = None,
    ) -> "WorkQueue":
        """
        Read a work queue by name.

        Args:
            name (str): a unique name for the work queue
            work_pool_name (str, optional): the name of the work pool
                the queue belongs to.

        Raises:
            ObjectNotFound: if no work queue is found
            HTTPStatusError: other status errors

        Returns:
            WorkQueue: a work queue API object
        """
        from prefect.client.schemas.objects import WorkQueue

        try:
            if work_pool_name is not None:
                response = await self.request(
                    "GET",
                    "/work_pools/{work_pool_name}/queues/{name}",
                    path_params={"work_pool_name": work_pool_name, "name": name},
                )
            else:
                response = await self.request(
                    "GET", "/work_queues/name/{name}", path_params={"name": name}
                )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

        return WorkQueue.model_validate(response.json())

    async def update_work_queue(self, id: "UUID", **kwargs: Any) -> None:
        """
        Update properties of a work queue.

        Args:
            id: the ID of the work queue to update
            **kwargs: the fields to update

        Raises:
            ValueError: if no kwargs are provided
            ObjectNotFound: if request returns 404
            httpx.RequestError: if the request fails

        """

        from prefect.client.schemas.actions import WorkQueueUpdate

        if not kwargs:
            raise ValueError("No fields provided to update.")

        data = WorkQueueUpdate(**kwargs).model_dump(mode="json", exclude_unset=True)
        try:
            await self.request(
                "PATCH", "/work_queues/{id}", path_params={"id": id}, json=data
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def get_runs_in_work_queue(
        self,
        id: "UUID",
        limit: int = 10,
        scheduled_before: datetime.datetime | None = None,
    ) -> list["FlowRun"]:
        """
        Read flow runs off a work queue.

        Args:
            id: the id of the work queue to read from
            limit: a limit on the number of runs to return
            scheduled_before: a timestamp; only runs scheduled before this time will be returned.
                Defaults to now.

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            List[FlowRun]: a list of FlowRun objects read from the queue
        """
        from prefect.client.schemas import FlowRun

        if scheduled_before is None:
            scheduled_before = datetime.datetime.now(ZoneInfo("UTC"))

        try:
            response = await self.request(
                "POST",
                "/work_queues/{id}/get_runs",
                path_params={"id": id},
                json={
                    "limit": limit,
                    "scheduled_before": scheduled_before.isoformat(),
                },
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return FlowRun.model_validate_list(response.json())

    async def read_work_queue(
        self,
        id: "UUID",
    ) -> "WorkQueue":
        """
        Read a work queue.

        Args:
            id: the id of the work queue to load

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            WorkQueue: an instantiated WorkQueue object
        """

        from prefect.client.schemas.objects import WorkQueue

        try:
            response = await self.request(
                "GET", "/work_queues/{id}", path_params={"id": id}
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueue.model_validate(response.json())

    async def read_work_queue_status(
        self,
        id: "UUID",
    ) -> "WorkQueueStatusDetail":
        """
        Read a work queue status.

        Args:
            id: the id of the work queue to load

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            WorkQueueStatus: an instantiated WorkQueueStatus object
        """

        from prefect.client.schemas.objects import WorkQueueStatusDetail

        try:
            response = await self.request(
                "GET", "/work_queues/{id}/status", path_params={"id": id}
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueueStatusDetail.model_validate(response.json())

    async def match_work_queues(
        self,
        prefixes: list[str],
        work_pool_name: str | None = None,
    ) -> list["WorkQueue"]:
        """
        Query the Prefect API for work queues with names with a specific prefix.

        Args:
            prefixes: a list of strings used to match work queue name prefixes
            work_pool_name: an optional work pool name to scope the query to

        Returns:
            a list of WorkQueue model representations
                of the work queues
        """
        from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName

        page_length = 100
        current_page = 0
        work_queues: list["WorkQueue"] = []

        while True:
            new_queues = await self.read_work_queues(
                work_pool_name=work_pool_name,
                offset=current_page * page_length,
                limit=page_length,
                work_queue_filter=WorkQueueFilter(
                    name=WorkQueueFilterName(startswith_=prefixes)
                ),
            )
            if not new_queues:
                break
            work_queues += new_queues
            current_page += 1

        return work_queues

    async def delete_work_queue_by_id(
        self,
        id: "UUID",
    ) -> None:
        """
        Delete a work queue by its ID.

        Args:
            id: the id of the work queue to delete

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """

        try:
            await self.request("DELETE", "/work_queues/{id}", path_params={"id": id})
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_work_queues(
        self,
        work_pool_name: str | None = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list["WorkQueue"]:
        """
        Retrieves queues for a work pool.

        Args:
            work_pool_name: Name of the work pool for which to get queues.
            work_queue_filter: Criteria by which to filter queues.
            limit: Limit for the queue query.
            offset: Offset for the queue query.

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            List of queues for the specified work pool.
        """
        from prefect.client.schemas.objects import WorkQueue

        json: dict[str, Any] = {
            "work_queues": (
                work_queue_filter.model_dump(mode="json", exclude_unset=True)
                if work_queue_filter
                else None
            ),
            "limit": limit,
            "offset": offset,
        }

        if work_pool_name:
            try:
                response = await self.request(
                    "POST",
                    "/work_pools/{work_pool_name}/queues/filter",
                    path_params={"work_pool_name": work_pool_name},
                    json=json,
                )
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ObjectNotFound(http_exc=e) from e
                else:
                    raise
        else:
            response = await self.request("POST", "/work_queues/filter", json=json)

        return WorkQueue.model_validate_list(response.json())
