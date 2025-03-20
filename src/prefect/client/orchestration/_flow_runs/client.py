from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import httpx
from typing_extensions import TypeVar

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectNotFound

T = TypeVar("T")
R = TypeVar("R", infer_variance=True)

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas import FlowRun, OrchestrationResult
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
        name: str | None = None,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        tags: "Iterable[str] | None" = None,
        parent_task_run_id: "UUID | None" = None,
        state: "State[R] | None" = None,
        work_pool_name: str | None = None,
        work_queue_name: str | None = None,
        job_variables: dict[str, Any] | None = None,
    ) -> "FlowRun":
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
                `Pending`.
            work_pool_name: The name of the work pool to run the flow run in.
            work_queue_name: The name of the work queue to place the flow run in.
            job_variables: The job variables to use when setting up flow run infrastructure.

        Raises:
            httpx.RequestError: if the Prefect API does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        from prefect.client.schemas.actions import FlowCreate, FlowRunCreate
        from prefect.client.schemas.objects import Flow, FlowRun, FlowRunPolicy
        from prefect.states import Pending, to_state_create

        parameters = parameters or {}
        context = context or {}

        if state is None:
            state = Pending()

        # Retrieve the flow id

        flow_data = FlowCreate(name=flow.name)
        response = self.request(
            "POST", "/flows/", json=flow_data.model_dump(mode="json")
        )
        flow_id = Flow.model_validate(response.json()).id

        flow_run_create = FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            name=name,
            parameters=parameters,
            context=context,
            tags=list(tags or []),
            parent_task_run_id=parent_task_run_id,
            state=to_state_create(state),
            empirical_policy=FlowRunPolicy(
                retries=flow.retries,
                retry_delay=int(flow.retry_delay_seconds or 0),
            ),
        )

        if work_pool_name is not None:
            flow_run_create.work_pool_name = work_pool_name
        if work_queue_name is not None:
            flow_run_create.work_queue_name = work_queue_name
        if job_variables is not None:
            flow_run_create.job_variables = job_variables

        flow_run_create_json = flow_run_create.model_dump(
            mode="json", exclude_unset=True
        )
        response = self.request("POST", "/flow_runs/", json=flow_run_create_json)

        flow_run = FlowRun.model_validate(response.json())

        # Restore the parameters to the local objects to retain expectations about
        # Python objects
        flow_run.parameters = parameters

        return flow_run

    def update_flow_run(
        self,
        flow_run_id: "UUID",
        flow_version: str | None = None,
        parameters: dict[str, Any] | None = None,
        name: str | None = None,
        tags: "Iterable[str] | None" = None,
        empirical_policy: "FlowRunPolicy | None" = None,
        infrastructure_pid: str | None = None,
        job_variables: dict[str, Any] | None = None,
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

        from prefect.client.schemas.actions import FlowRunUpdate

        flow_run_data = FlowRunUpdate(**params)

        return self.request(
            "PATCH",
            "/flow_runs/{id}",
            path_params={"id": flow_run_id},
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    def delete_flow_run(
        self,
        flow_run_id: "UUID",
    ) -> None:
        """
        Delete a flow run by UUID.

        Args:
            flow_run_id: The flow run UUID of interest.
        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """
        try:
            self.request("DELETE", "/flow_runs/{id}", path_params={"id": flow_run_id})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def read_flow_run(self, flow_run_id: "UUID") -> "FlowRun":
        """
        Query the Prefect API for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a Flow Run model representation of the flow run
        """
        try:
            response = self.request(
                "GET", "/flow_runs/{id}", path_params={"id": flow_run_id}
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import FlowRun

        return FlowRun.model_validate(response.json())

    def resume_flow_run(
        self, flow_run_id: "UUID", run_input: dict[str, Any] | None = None
    ) -> "OrchestrationResult[Any]":
        """
        Resumes a paused flow run.

        Args:
            flow_run_id: the flow run ID of interest
            run_input: the input to resume the flow run with

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        try:
            response = self.request(
                "POST",
                "/flow_runs/{id}/resume",
                path_params={"id": flow_run_id},
                json={"run_input": run_input},
            )
        except httpx.HTTPStatusError:
            raise
        from prefect.client.schemas import OrchestrationResult

        result: OrchestrationResult[Any] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    def read_flow_runs(
        self,
        *,
        flow_filter: "FlowFilter | None" = None,
        flow_run_filter: "FlowRunFilter | None" = None,
        task_run_filter: "TaskRunFilter | None" = None,
        deployment_filter: "DeploymentFilter | None" = None,
        work_pool_filter: "WorkPoolFilter | None" = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        sort: "FlowRunSort | None" = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> "list[FlowRun]":
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

        response = self.request("POST", "/flow_runs/filter", json=body)
        from prefect.client.schemas.objects import FlowRun

        return FlowRun.model_validate_list(response.json())

    def set_flow_run_state(
        self,
        flow_run_id: "UUID | str",
        state: "State[T]",
        force: bool = False,
    ) -> "OrchestrationResult[T]":
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
        from uuid import UUID, uuid4

        from prefect.states import to_state_create

        flow_run_id = (
            flow_run_id if isinstance(flow_run_id, UUID) else UUID(flow_run_id)
        )
        state_create = to_state_create(state)
        state_create.state_details.flow_run_id = flow_run_id
        state_create.state_details.transition_id = uuid4()
        try:
            response = self.request(
                "POST",
                "/flow_runs/{id}/set_state",
                path_params={"id": flow_run_id},
                json=dict(
                    state=state_create.model_dump(mode="json", serialize_as_any=True),
                    force=force,
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas import OrchestrationResult

        result: OrchestrationResult[T] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    def read_flow_run_states(self, flow_run_id: "UUID") -> "list[State]":
        """
        Query for the states of a flow run

        Args:
            flow_run_id: the id of the flow run

        Returns:
            a list of State model representations
                of the flow run states
        """
        response = self.request(
            "GET", "/flow_run_states/", params=dict(flow_run_id=str(flow_run_id))
        )
        from prefect.states import State

        return State.model_validate_list(response.json())

    def set_flow_run_name(self, flow_run_id: "UUID", name: str) -> httpx.Response:
        from prefect.client.schemas.actions import FlowRunUpdate

        flow_run_data = FlowRunUpdate(name=name)
        return self.request(
            "PATCH",
            "/flow_runs/{id}",
            path_params={"id": flow_run_id},
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    def create_flow_run_input(
        self, flow_run_id: "UUID", key: str, value: str, sender: str | None = None
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

        response = self.request(
            "POST",
            "/flow_runs/{id}/input",
            path_params={"id": flow_run_id},
            json={"key": key, "value": value, "sender": sender},
        )
        response.raise_for_status()

    def filter_flow_run_input(
        self, flow_run_id: "UUID", key_prefix: str, limit: int, exclude_keys: "set[str]"
    ) -> "list[FlowRunInput]":
        response = self.request(
            "POST",
            "/flow_runs/{id}/input/filter",
            path_params={"id": flow_run_id},
            json={
                "prefix": key_prefix,
                "limit": limit,
                "exclude_keys": list(exclude_keys),
            },
        )
        response.raise_for_status()
        from prefect.client.schemas.objects import FlowRunInput

        return FlowRunInput.model_validate_list(response.json())

    def read_flow_run_input(self, flow_run_id: "UUID", key: str) -> str:
        """
        Reads a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
        """
        response = self.request(
            "GET",
            "/flow_runs/{id}/input/{key}",
            path_params={"id": flow_run_id, "key": key},
        )
        response.raise_for_status()
        return response.content.decode()

    def delete_flow_run_input(self, flow_run_id: "UUID", key: str) -> None:
        """
        Deletes a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
        """
        response = self.request(
            "DELETE",
            "/flow_runs/{id}/input/{key}",
            path_params={"id": flow_run_id, "key": key},
        )
        response.raise_for_status()

    def update_flow_run_labels(
        self, flow_run_id: "UUID", labels: "KeyValueLabelsField"
    ) -> None:
        """
        Updates the labels of a flow run.
        """

        response = self.request(
            "PATCH",
            "/flow_runs/{id}/labels",
            path_params={"id": flow_run_id},
            json=labels,
        )
        response.raise_for_status()


class FlowRunAsyncClient(BaseAsyncClient):
    async def create_flow_run(
        self,
        flow: "FlowObject[Any, R]",
        name: str | None = None,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        tags: "Iterable[str] | None" = None,
        parent_task_run_id: "UUID | None" = None,
        state: "State[R] | None" = None,
        work_pool_name: str | None = None,
        work_queue_name: str | None = None,
        job_variables: dict[str, Any] | None = None,
    ) -> "FlowRun":
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
                `Pending`.
            work_pool_name: The name of the work pool to run the flow run in.
            work_queue_name: The name of the work queue to place the flow run in.
            job_variables: The job variables to use when setting up flow run infrastructure.

        Raises:
            httpx.RequestError: if the Prefect API does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        from prefect.client.schemas.actions import FlowCreate, FlowRunCreate
        from prefect.client.schemas.objects import Flow, FlowRun, FlowRunPolicy
        from prefect.states import Pending, to_state_create

        parameters = parameters or {}
        context = context or {}

        if state is None:
            state = Pending()

        # Retrieve the flow id

        flow_data = FlowCreate(name=flow.name)
        response = await self.request(
            "POST", "/flows/", json=flow_data.model_dump(mode="json")
        )
        flow_id = Flow.model_validate(response.json()).id

        flow_run_create = FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            name=name,
            parameters=parameters,
            context=context,
            tags=list(tags or []),
            parent_task_run_id=parent_task_run_id,
            state=to_state_create(state),
            empirical_policy=FlowRunPolicy(
                retries=flow.retries,
                retry_delay=int(flow.retry_delay_seconds or 0),
            ),
        )

        if work_pool_name is not None:
            flow_run_create.work_pool_name = work_pool_name
        if work_queue_name is not None:
            flow_run_create.work_queue_name = work_queue_name
        if job_variables is not None:
            flow_run_create.job_variables = job_variables

        flow_run_create_json = flow_run_create.model_dump(
            mode="json", exclude_unset=True
        )
        response = await self.request("POST", "/flow_runs/", json=flow_run_create_json)

        flow_run = FlowRun.model_validate(response.json())

        # Restore the parameters to the local objects to retain expectations about
        # Python objects
        flow_run.parameters = parameters

        return flow_run

    async def update_flow_run(
        self,
        flow_run_id: "UUID",
        flow_version: str | None = None,
        parameters: dict[str, Any] | None = None,
        name: str | None = None,
        tags: "Iterable[str] | None" = None,
        empirical_policy: "FlowRunPolicy | None" = None,
        infrastructure_pid: str | None = None,
        job_variables: dict[str, Any] | None = None,
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
        from prefect.client.schemas.actions import FlowRunUpdate

        flow_run_data = FlowRunUpdate(**params)

        return await self.request(
            "PATCH",
            "/flow_runs/{id}",
            path_params={"id": flow_run_id},
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    async def delete_flow_run(
        self,
        flow_run_id: "UUID",
    ) -> None:
        """
        Delete a flow run by UUID.

        Args:
            flow_run_id: The flow run UUID of interest.
        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """
        try:
            await self.request(
                "DELETE", "/flow_runs/{id}", path_params={"id": flow_run_id}
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_flow_run(self, flow_run_id: "UUID") -> "FlowRun":
        """
        Query the Prefect API for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a Flow Run model representation of the flow run
        """
        try:
            response = await self.request(
                "GET", "/flow_runs/{id}", path_params={"id": flow_run_id}
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas.objects import FlowRun

        return FlowRun.model_validate(response.json())

    async def resume_flow_run(
        self, flow_run_id: "UUID", run_input: dict[str, Any] | None = None
    ) -> "OrchestrationResult[Any]":
        """
        Resumes a paused flow run.

        Args:
            flow_run_id: the flow run ID of interest
            run_input: the input to resume the flow run with

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        try:
            response = await self.request(
                "POST",
                "/flow_runs/{id}/resume",
                path_params={"id": flow_run_id},
                json={"run_input": run_input},
            )
        except httpx.HTTPStatusError:
            raise
        from prefect.client.schemas import OrchestrationResult

        result: OrchestrationResult[Any] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    async def read_flow_runs(
        self,
        *,
        flow_filter: "FlowFilter | None" = None,
        flow_run_filter: "FlowRunFilter | None" = None,
        task_run_filter: "TaskRunFilter | None" = None,
        deployment_filter: "DeploymentFilter | None" = None,
        work_pool_filter: "WorkPoolFilter | None" = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        sort: "FlowRunSort | None" = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> "list[FlowRun]":
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

        response = await self.request("POST", "/flow_runs/filter", json=body)
        from prefect.client.schemas.objects import FlowRun

        return FlowRun.model_validate_list(response.json())

    async def set_flow_run_state(
        self,
        flow_run_id: "UUID | str",
        state: "State[T]",
        force: bool = False,
    ) -> "OrchestrationResult[T]":
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
        from uuid import UUID, uuid4

        from prefect.states import to_state_create

        flow_run_id = (
            flow_run_id if isinstance(flow_run_id, UUID) else UUID(flow_run_id)
        )
        state_create = to_state_create(state)
        state_create.state_details.flow_run_id = flow_run_id
        state_create.state_details.transition_id = uuid4()
        try:
            response = await self.request(
                "POST",
                "/flow_runs/{id}/set_state",
                path_params={"id": flow_run_id},
                json=dict(
                    state=state_create.model_dump(mode="json", serialize_as_any=True),
                    force=force,
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        from prefect.client.schemas import OrchestrationResult

        result: OrchestrationResult[T] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    async def read_flow_run_states(self, flow_run_id: "UUID") -> "list[State]":
        """
        Query for the states of a flow run

        Args:
            flow_run_id: the id of the flow run

        Returns:
            a list of State model representations
                of the flow run states
        """
        response = await self.request(
            "GET", "/flow_run_states/", params=dict(flow_run_id=str(flow_run_id))
        )
        from prefect.states import State

        return State.model_validate_list(response.json())

    async def set_flow_run_name(self, flow_run_id: "UUID", name: str) -> httpx.Response:
        from prefect.client.schemas.actions import FlowRunUpdate

        flow_run_data = FlowRunUpdate(name=name)
        return await self.request(
            "PATCH",
            "/flow_runs/{id}",
            path_params={"id": flow_run_id},
            json=flow_run_data.model_dump(mode="json", exclude_unset=True),
        )

    async def create_flow_run_input(
        self, flow_run_id: "UUID", key: str, value: str, sender: str | None = None
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
        from prefect.client.schemas.objects import FlowRunInput

        FlowRunInput(flow_run_id=flow_run_id, key=key, value=value)

        response = await self.request(
            "POST",
            "/flow_runs/{id}/input",
            path_params={"id": flow_run_id},
            json={"key": key, "value": value, "sender": sender},
        )
        response.raise_for_status()

    async def filter_flow_run_input(
        self, flow_run_id: "UUID", key_prefix: str, limit: int, exclude_keys: "set[str]"
    ) -> "list[FlowRunInput]":
        response = await self.request(
            "POST",
            "/flow_runs/{id}/input/filter",
            path_params={"id": flow_run_id},
            json={
                "prefix": key_prefix,
                "limit": limit,
                "exclude_keys": list(exclude_keys),
            },
        )
        response.raise_for_status()
        from prefect.client.schemas.objects import FlowRunInput

        return FlowRunInput.model_validate_list(response.json())

    async def read_flow_run_input(self, flow_run_id: "UUID", key: str) -> str:
        """
        Reads a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
        """
        response = await self.request(
            "GET",
            "/flow_runs/{id}/input/{key}",
            path_params={"id": flow_run_id, "key": key},
        )
        response.raise_for_status()
        return response.content.decode()

    async def delete_flow_run_input(self, flow_run_id: "UUID", key: str) -> None:
        """
        Deletes a flow run input.

        Args:
            flow_run_id: The flow run id.
            key: The input key.
        """
        response = await self.request(
            "DELETE",
            "/flow_runs/{id}/input/{key}",
            path_params={"id": flow_run_id, "key": key},
        )
        response.raise_for_status()

    async def update_flow_run_labels(
        self, flow_run_id: "UUID", labels: "KeyValueLabelsField"
    ) -> None:
        """
        Updates the labels of a flow run.
        """

        response = await self.request(
            "PATCH",
            "/flow_runs/{id}/labels",
            path_params={"id": flow_run_id},
            json=labels,
        )
        response.raise_for_status()
