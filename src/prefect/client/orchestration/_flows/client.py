from __future__ import annotations

from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError, RequestError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.filters import (
        DeploymentFilter,
        FlowFilter,
        FlowRunFilter,
        TaskRunFilter,
        WorkPoolFilter,
        WorkQueueFilter,
    )
    from prefect.client.schemas.objects import (
        Flow,
    )
    from prefect.client.schemas.sorting import FlowSort
    from prefect.flows import Flow as FlowObject


class FlowClient(BaseClient):
    def create_flow(self, flow: "FlowObject[Any, Any]") -> "UUID":
        """
        Create a flow in the Prefect API.

        Args:
            flow: a `Flow` object

        Raises:
            httpx.RequestError: if a flow was not created for any reason

        Returns:
            the ID of the flow in the backend
        """
        return self.create_flow_from_name(flow.name)

    def create_flow_from_name(self, flow_name: str) -> "UUID":
        """
        Create a flow in the Prefect API.

        Args:
            flow_name: the name of the new flow

        Raises:
            httpx.RequestError: if a flow was not created for any reason

        Returns:
            the ID of the flow in the backend
        """
        from prefect.client.schemas.actions import FlowCreate

        flow_data = FlowCreate(name=flow_name)
        response = self.request(
            "POST", "/flows/", json=flow_data.model_dump(mode="json")
        )

        flow_id = response.json().get("id")
        if not flow_id:
            raise RequestError(f"Malformed response: {response}")

        # Return the id of the created flow
        from uuid import UUID

        return UUID(flow_id)

    def read_flow(self, flow_id: "UUID") -> "Flow":
        """
        Query the Prefect API for a flow by id.

        Args:
            flow_id: the flow ID of interest

        Returns:
            a Flow model representation of the flow
        """
        response = self.request("GET", "/flows/{id}", path_params={"id": flow_id})
        from prefect.client.schemas.objects import Flow

        return Flow.model_validate(response.json())

    def delete_flow(self, flow_id: "UUID") -> None:
        """
        Delete a flow by UUID.

        Args:
            flow_id: ID of the flow to be deleted
        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fail
        """
        try:
            self.request("DELETE", "/flows/{id}", path_params={"id": flow_id})
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def read_flows(
        self,
        *,
        flow_filter: "FlowFilter | None" = None,
        flow_run_filter: "FlowRunFilter | None" = None,
        task_run_filter: "TaskRunFilter | None" = None,
        deployment_filter: "DeploymentFilter | None" = None,
        work_pool_filter: "WorkPoolFilter | None" = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        sort: "FlowSort | None" = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list["Flow"]:
        """
        Query the Prefect API for flows. Only flows matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            work_pool_filter: filter criteria for work pools
            work_queue_filter: filter criteria for work pool queues
            sort: sort criteria for the flows
            limit: limit for the flow query
            offset: offset for the flow query

        Returns:
            a list of Flow model representations of the flows
        """
        body: dict[str, Any] = {
            "flows": flow_filter.model_dump(mode="json") if flow_filter else None,
            "flow_runs": (
                flow_run_filter.model_dump(mode="json", exclude_unset=True)
                if flow_run_filter
                else None
            ),
            "task_runs": (
                task_run_filter.model_dump(mode="json") if task_run_filter else None
            ),
            "deployments": (
                deployment_filter.model_dump(mode="json") if deployment_filter else None
            ),
            "work_pools": (
                work_pool_filter.model_dump(mode="json") if work_pool_filter else None
            ),
            "work_queues": (
                work_queue_filter.model_dump(mode="json") if work_queue_filter else None
            ),
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }

        response = self.request("POST", "/flows/filter", json=body)
        from prefect.client.schemas.objects import Flow

        return Flow.model_validate_list(response.json())

    def read_flow_by_name(
        self,
        flow_name: str,
    ) -> "Flow":
        """
        Query the Prefect API for a flow by name.

        Args:
            flow_name: the name of a flow

        Returns:
            a fully hydrated Flow model
        """
        response = self.request(
            "GET", "/flows/name/{name}", path_params={"name": flow_name}
        )
        from prefect.client.schemas.objects import Flow

        return Flow.model_validate(response.json())


class FlowAsyncClient(BaseAsyncClient):
    async def create_flow(self, flow: "FlowObject[Any, Any]") -> "UUID":
        """
        Create a flow in the Prefect API.

        Args:
            flow: a `Flow` object

        Raises:
            httpx.RequestError: if a flow was not created for any reason

        Returns:
            the ID of the flow in the backend
        """
        return await self.create_flow_from_name(flow.name)

    async def create_flow_from_name(self, flow_name: str) -> "UUID":
        """
        Create a flow in the Prefect API.

        Args:
            flow_name: the name of the new flow

        Raises:
            httpx.RequestError: if a flow was not created for any reason

        Returns:
            the ID of the flow in the backend
        """
        from prefect.client.schemas.actions import FlowCreate

        flow_data = FlowCreate(name=flow_name)
        response = await self.request(
            "POST", "/flows/", json=flow_data.model_dump(mode="json")
        )

        flow_id = response.json().get("id")
        if not flow_id:
            raise RequestError(f"Malformed response: {response}")

        # Return the id of the created flow
        from uuid import UUID

        return UUID(flow_id)

    async def read_flow(self, flow_id: "UUID") -> "Flow":
        """
        Query the Prefect API for a flow by id.

        Args:
            flow_id: the flow ID of interest

        Returns:
            a Flow model representation of the flow
        """
        response = await self.request("GET", "/flows/{id}", path_params={"id": flow_id})
        from prefect.client.schemas.objects import Flow

        return Flow.model_validate(response.json())

    async def delete_flow(self, flow_id: "UUID") -> None:
        """
        Delete a flow by UUID.

        Args:
            flow_id: ID of the flow to be deleted
        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fail
        """
        try:
            await self.request("DELETE", "/flows/{id}", path_params={"id": flow_id})
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_flows(
        self,
        *,
        flow_filter: "FlowFilter | None" = None,
        flow_run_filter: "FlowRunFilter | None" = None,
        task_run_filter: "TaskRunFilter | None" = None,
        deployment_filter: "DeploymentFilter | None" = None,
        work_pool_filter: "WorkPoolFilter | None" = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        sort: "FlowSort | None" = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list["Flow"]:
        """
        Query the Prefect API for flows. Only flows matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            work_pool_filter: filter criteria for work pools
            work_queue_filter: filter criteria for work pool queues
            sort: sort criteria for the flows
            limit: limit for the flow query
            offset: offset for the flow query

        Returns:
            a list of Flow model representations of the flows
        """
        body: dict[str, Any] = {
            "flows": flow_filter.model_dump(mode="json") if flow_filter else None,
            "flow_runs": (
                flow_run_filter.model_dump(mode="json", exclude_unset=True)
                if flow_run_filter
                else None
            ),
            "task_runs": (
                task_run_filter.model_dump(mode="json") if task_run_filter else None
            ),
            "deployments": (
                deployment_filter.model_dump(mode="json") if deployment_filter else None
            ),
            "work_pools": (
                work_pool_filter.model_dump(mode="json") if work_pool_filter else None
            ),
            "work_queues": (
                work_queue_filter.model_dump(mode="json") if work_queue_filter else None
            ),
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }

        response = await self.request("POST", "/flows/filter", json=body)
        from prefect.client.schemas.objects import Flow

        return Flow.model_validate_list(response.json())

    async def read_flow_by_name(
        self,
        flow_name: str,
    ) -> "Flow":
        """
        Query the Prefect API for a flow by name.

        Args:
            flow_name: the name of a flow

        Returns:
            a fully hydrated Flow model
        """
        response = await self.request(
            "GET", "/flows/name/{name}", path_params={"name": flow_name}
        )
        from prefect.client.schemas.objects import Flow

        return Flow.model_validate(response.json())
