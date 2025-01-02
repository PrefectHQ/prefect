from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union
from uuid import UUID, uuid4

import httpx
import pydantic
from starlette import status

import prefect
import prefect.exceptions
import prefect.settings
import prefect.states
from prefect.client.orchestration.base import BaseAsyncClient, BaseClient

T = TypeVar("T")
R = TypeVar("R", infer_variance=True)

if TYPE_CHECKING:
    from prefect.client.schemas import FlowRun, OrchestrationResult
    from prefect.client.schemas.actions import (
        FlowRunCreate,
        FlowRunUpdate,
    )
    from prefect.client.schemas.filters import (
        DeploymentFilter,
        FlowFilter,
        FlowRunFilter,
        TaskRunFilter,
        WorkPoolFilter,
        WorkQueueFilter,
    )
    from prefect.client.schemas.objects import (
        FlowRunInput,
        FlowRunPolicy,
    )
    from prefect.client.schemas.sorting import (
        FlowRunSort,
    )
    from prefect.flows import Flow as FlowObject
    from prefect.states import State
    from prefect.types import KeyValueLabelsField


class FlowRunClient(BaseClient):
    def create_flow_run(
        self,
        flow: "FlowObject[Any, R]",
        name: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        parent_task_run_id: Optional[UUID] = None,
        state: Optional["State[R]"] = None,
    ) -> FlowRun:
        """
        Create a flow run for a flow.

        Args:
            flow: The flow model to create the flow run for
            name: An optional name for the flow run
            parameters: Parameter overrides for this flow run.
            context: Optional run context data
            tags: a list of tags to apply to this flow run
            parent_task_run_id: if a subflow run is being created, the placeholder task
                run identifier in the parent flow
            state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.

        Raises:
            httpx.RequestError: if the Prefect API does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        parameters = parameters or {}
        context = context or {}

        if state is None:
            state = prefect.states.Pending()

        # Retrieve the flow id
        flow_id = self.create_flow(flow)

        flow_run_create = FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            name=name,
            parameters=parameters,
            context=context,
            tags=list(tags or []),
            parent_task_run_id=parent_task_run_id,
            state=state.to_state_create(),
            empirical_policy=FlowRunPolicy(
                retries=flow.retries,
                retry_delay=int(flow.retry_delay_seconds or 0),
            ),
        )

        flow_run_create_json = flow_run_create.model_dump(mode="json")
        response = self._client.post("/flow_runs/", json=flow_run_create_json)
        flow_run = FlowRun.model_validate(response.json())

        # Restore the parameters to the local objects to retain expectations about
        # Python objects
        flow_run.parameters = parameters

        return flow_run

    def update_flow_run(
        self,
        flow_run_id: UUID,
        flow_version: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        name: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        empirical_policy: Optional[FlowRunPolicy] = None,
        infrastructure_pid: Optional[str] = None,
        job_variables: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Update a flow run's details.

        Args:
            flow_run_id: The identifier for the flow run to update.
            flow_version: A new version string for the flow run.
            parameters: A dictionary of parameter values for the flow run. This will not
                be merged with any existing parameters.
            name: A new name for the flow run.
            empirical_policy: A new flow run orchestration policy. This will not be
                merged with any existing policy.
            tags: An iterable of new tags for the flow run. These will not be merged with
                any existing tags.
            infrastructure_pid: The id of flow run as returned by an
                infrastructure block.

        Returns:
            an `httpx.Response` object from the PATCH request
        """
        params: dict[str, Any] = {}
        if flow_version is not None:
            params["flow_version"] = flow_version
        if parameters is not None:
            params["parameters"] = parameters
        if name is not None:
            params["name"] = name
        if tags is not None:
            params["tags"] = tags
        if empirical_policy is not None:
            params["empirical_policy"] = empirical_policy.model_dump(
                mode="json", exclude_unset=True
            )
        if infrastructure_pid:
            params["infrastructure_pid"] = infrastructure_pid
        if job_variables is not None:
            params["job_variables"] = job_variables

        flow_run_data = FlowRunUpdate(**params)

        return self._client.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    def read_flow_run(self, flow_run_id: UUID) -> FlowRun:
        """
        Query the Prefect API for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a Flow Run model representation of the flow run
        """
        try:
            response = self._client.get(f"/flow_runs/{flow_run_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return FlowRun.model_validate(response.json())

    def read_flow_runs(
        self,
        *,
        flow_filter: Optional[FlowFilter] = None,
        flow_run_filter: Optional[FlowRunFilter] = None,
        task_run_filter: Optional[TaskRunFilter] = None,
        deployment_filter: Optional[DeploymentFilter] = None,
        work_pool_filter: Optional[WorkPoolFilter] = None,
        work_queue_filter: Optional[WorkQueueFilter] = None,
        sort: Optional[FlowRunSort] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[FlowRun]:
        """
        Query the Prefect API for flow runs. Only flow runs matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            work_pool_filter: filter criteria for work pools
            work_queue_filter: filter criteria for work pool queues
            sort: sort criteria for the flow runs
            limit: limit for the flow run query
            offset: offset for the flow run query

        Returns:
            a list of Flow Run model representations
                of the flow runs
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
            "work_pool_queues": (
                work_queue_filter.model_dump(mode="json") if work_queue_filter else None
            ),
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }

        response = self._client.post("/flow_runs/filter", json=body)
        return pydantic.TypeAdapter(list[FlowRun]).validate_python(response.json())

    def set_flow_run_state(
        self,
        flow_run_id: UUID,
        state: "prefect.states.State[T]",
        force: bool = False,
    ) -> OrchestrationResult[T]:
        """
        Set the state of a flow run.

        Args:
            flow_run_id: the id of the flow run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Prefect API to accept the state

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        state_create = state.to_state_create()
        state_create.state_details.flow_run_id = flow_run_id
        state_create.state_details.transition_id = uuid4()
        try:
            response = self._client.post(
                f"/flow_runs/{flow_run_id}/set_state",
                json=dict(
                    state=state_create.model_dump(mode="json", serialize_as_any=True),
                    force=force,
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

        result: OrchestrationResult[T] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    def set_flow_run_name(self, flow_run_id: UUID, name: str) -> httpx.Response:
        flow_run_data = FlowRunUpdate(name=name)
        return self._client.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    def update_flow_run_labels(
        self, flow_run_id: UUID, labels: "KeyValueLabelsField"
    ) -> None:
        """
        Updates the labels of a flow run.
        """
        response = self._client.patch(
            f"/flow_runs/{flow_run_id}/labels",
            json=labels,
        )
        response.raise_for_status()


class FlowRunAsyncClient(BaseAsyncClient):
    async def create_flow_run(
        self,
        flow: "FlowObject[Any, R]",
        name: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        parent_task_run_id: Optional[UUID] = None,
        state: Optional["State[R]"] = None,
    ) -> FlowRun:
        """
        Create a flow run for a flow.

        Args:
            flow: The flow model to create the flow run for
            name: An optional name for the flow run
            parameters: Parameter overrides for this flow run.
            context: Optional run context data
            tags: a list of tags to apply to this flow run
            parent_task_run_id: if a subflow run is being created, the placeholder task
                run identifier in the parent flow
            state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.

        Raises:
            httpx.RequestError: if the Prefect API does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        parameters = parameters or {}
        context = context or {}

        if state is None:
            state = prefect.states.Pending()

        # Retrieve the flow id
        flow_id = await self.create_flow(flow)

        flow_run_create = FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            name=name,
            parameters=parameters,
            context=context,
            tags=list(tags or []),
            parent_task_run_id=parent_task_run_id,
            state=state.to_state_create(),
            empirical_policy=FlowRunPolicy(
                retries=flow.retries,
                retry_delay=int(flow.retry_delay_seconds or 0),
            ),
        )

        flow_run_create_json = flow_run_create.model_dump(mode="json")
        response = await self._client.post("/flow_runs/", json=flow_run_create_json)
        flow_run = FlowRun.model_validate(response.json())

        # Restore the parameters to the local objects to retain expectations about
        # Python objects
        flow_run.parameters = parameters

        return flow_run

    async def update_flow_run(
        self,
        flow_run_id: UUID,
        flow_version: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        name: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        empirical_policy: Optional[FlowRunPolicy] = None,
        infrastructure_pid: Optional[str] = None,
        job_variables: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Update a flow run's details.

        Args:
            flow_run_id: The identifier for the flow run to update.
            flow_version: A new version string for the flow run.
            parameters: A dictionary of parameter values for the flow run. This will not
                be merged with any existing parameters.
            name: A new name for the flow run.
            empirical_policy: A new flow run orchestration policy. This will not be
                merged with any existing policy.
            tags: An iterable of new tags for the flow run. These will not be merged with
                any existing tags.
            infrastructure_pid: The id of flow run as returned by an
                infrastructure block.

        Returns:
            an `httpx.Response` object from the PATCH request
        """
        params: dict[str, Any] = {}
        if flow_version is not None:
            params["flow_version"] = flow_version
        if parameters is not None:
            params["parameters"] = parameters
        if name is not None:
            params["name"] = name
        if tags is not None:
            params["tags"] = tags
        if empirical_policy is not None:
            params["empirical_policy"] = empirical_policy
        if infrastructure_pid:
            params["infrastructure_pid"] = infrastructure_pid
        if job_variables is not None:
            params["job_variables"] = job_variables

        flow_run_data = FlowRunUpdate(**params)

        return await self._client.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    async def delete_flow_run(
        self,
        flow_run_id: UUID,
    ) -> None:
        """
        Delete a flow run by UUID.

        Args:
            flow_run_id: The flow run UUID of interest.
        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """
        try:
            await self._client.delete(f"/flow_runs/{flow_run_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_flow_run(self, flow_run_id: UUID) -> FlowRun:
        """
        Query the Prefect API for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a Flow Run model representation of the flow run
        """
        try:
            response = await self._client.get(f"/flow_runs/{flow_run_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return FlowRun.model_validate(response.json())

    async def resume_flow_run(
        self, flow_run_id: UUID, run_input: Optional[dict[str, Any]] = None
    ) -> OrchestrationResult[Any]:
        """
        Resumes a paused flow run.

        Args:
            flow_run_id: the flow run ID of interest
            run_input: the input to resume the flow run with

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        try:
            response = await self._client.post(
                f"/flow_runs/{flow_run_id}/resume", json={"run_input": run_input}
            )
        except httpx.HTTPStatusError:
            raise

        result: OrchestrationResult[Any] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    async def read_flow_runs(
        self,
        *,
        flow_filter: Optional[FlowFilter] = None,
        flow_run_filter: Optional[FlowRunFilter] = None,
        task_run_filter: Optional[TaskRunFilter] = None,
        deployment_filter: Optional[DeploymentFilter] = None,
        work_pool_filter: Optional[WorkPoolFilter] = None,
        work_queue_filter: Optional[WorkQueueFilter] = None,
        sort: Optional[FlowRunSort] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[FlowRun]:
        """
        Query the Prefect API for flow runs. Only flow runs matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            work_pool_filter: filter criteria for work pools
            work_queue_filter: filter criteria for work pool queues
            sort: sort criteria for the flow runs
            limit: limit for the flow run query
            offset: offset for the flow run query

        Returns:
            a list of Flow Run model representations
                of the flow runs
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
            "work_pool_queues": (
                work_queue_filter.model_dump(mode="json") if work_queue_filter else None
            ),
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }

        response = await self._client.post("/flow_runs/filter", json=body)
        return pydantic.TypeAdapter(list[FlowRun]).validate_python(response.json())

    async def set_flow_run_state(
        self,
        flow_run_id: Union[UUID, str],
        state: "prefect.states.State[T]",
        force: bool = False,
    ) -> OrchestrationResult[T]:
        """
        Set the state of a flow run.

        Args:
            flow_run_id: the id of the flow run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Prefect API to accept the state

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        flow_run_id = (
            flow_run_id if isinstance(flow_run_id, UUID) else UUID(flow_run_id)
        )
        state_create = state.to_state_create()
        state_create.state_details.flow_run_id = flow_run_id
        state_create.state_details.transition_id = uuid4()
        try:
            response = await self._client.post(
                f"/flow_runs/{flow_run_id}/set_state",
                json=dict(
                    state=state_create.model_dump(mode="json", serialize_as_any=True),
                    force=force,
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

        result: OrchestrationResult[T] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    async def read_flow_run_states(
        self, flow_run_id: UUID
    ) -> list[prefect.states.State]:
        """
        Query for the states of a flow run

        Args:
            flow_run_id: the id of the flow run

        Returns:
            a list of State model representations
                of the flow run states
        """
        response = await self._client.get(
            "/flow_run_states/", params=dict(flow_run_id=str(flow_run_id))
        )
        return pydantic.TypeAdapter(list[prefect.states.State]).validate_python(
            response.json()
        )

    async def set_flow_run_name(self, flow_run_id: UUID, name: str) -> httpx.Response:
        flow_run_data = FlowRunUpdate(name=name)
        return await self._client.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    async def create_flow_run_input(
        self, flow_run_id: UUID, key: str, value: str, sender: Optional[str] = None
    ) -> None:
        """
        Creates a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
            value: The input value.
            sender: The sender of the input.
        """

        # Initialize the input to ensure that the key is valid.
        FlowRunInput(flow_run_id=flow_run_id, key=key, value=value)

        response = await self._client.post(
            f"/flow_runs/{flow_run_id}/input",
            json={"key": key, "value": value, "sender": sender},
        )
        response.raise_for_status()

    async def filter_flow_run_input(
        self, flow_run_id: UUID, key_prefix: str, limit: int, exclude_keys: set[str]
    ) -> list[FlowRunInput]:
        response = await self._client.post(
            f"/flow_runs/{flow_run_id}/input/filter",
            json={
                "prefix": key_prefix,
                "limit": limit,
                "exclude_keys": list(exclude_keys),
            },
        )
        response.raise_for_status()
        return pydantic.TypeAdapter(list[FlowRunInput]).validate_python(response.json())

    async def read_flow_run_input(self, flow_run_id: UUID, key: str) -> str:
        """
        Reads a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
        """
        response = await self._client.get(f"/flow_runs/{flow_run_id}/input/{key}")
        response.raise_for_status()
        return response.content.decode()

    async def delete_flow_run_input(self, flow_run_id: UUID, key: str) -> None:
        """
        Deletes a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
        """
        response = await self._client.delete(f"/flow_runs/{flow_run_id}/input/{key}")
        response.raise_for_status()

    async def update_flow_run_labels(
        self, flow_run_id: UUID, labels: "KeyValueLabelsField"
    ) -> None:
        """
        Updates the labels of a flow run.
        """

        response = await self._client.patch(
            f"/flow_runs/{flow_run_id}/labels", json=labels
        )
        response.raise_for_status()
