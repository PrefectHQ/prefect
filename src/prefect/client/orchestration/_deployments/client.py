from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Union
from uuid import UUID

from httpx import HTTPStatusError, RequestError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectNotFound

if TYPE_CHECKING:
    import datetime

    from prefect.client.schemas import FlowRun
    from prefect.client.schemas.actions import (
        DeploymentCreate,
        DeploymentScheduleCreate,
        DeploymentUpdate,
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
        ConcurrencyOptions,
        DeploymentBranchingOptions,
        DeploymentSchedule,
        VersionInfo,
    )
    from prefect.client.schemas.responses import (
        DeploymentResponse,
        FlowRunResponse,
    )
    from prefect.client.schemas.schedules import SCHEDULE_TYPES
    from prefect.client.schemas.sorting import (
        DeploymentSort,
    )
    from prefect.states import State
    from prefect.types import KeyValueLabelsField


class DeploymentClient(BaseClient):
    def create_deployment(
        self,
        flow_id: UUID,
        name: str,
        version: str | None = None,
        version_info: "VersionInfo | None" = None,
        schedules: list["DeploymentScheduleCreate"] | None = None,
        concurrency_limit: int | None = None,
        concurrency_options: "ConcurrencyOptions | None" = None,
        parameters: dict[str, Any] | None = None,
        description: str | None = None,
        work_queue_name: str | None = None,
        work_pool_name: str | None = None,
        tags: list[str] | None = None,
        storage_document_id: UUID | None = None,
        path: str | None = None,
        entrypoint: str | None = None,
        infrastructure_document_id: UUID | None = None,
        parameter_openapi_schema: dict[str, Any] | None = None,
        paused: bool | None = None,
        pull_steps: list[dict[str, Any]] | None = None,
        enforce_parameter_schema: bool | None = None,
        job_variables: dict[str, Any] | None = None,
        branch: str | None = None,
        base: UUID | None = None,
        root: UUID | None = None,
    ) -> UUID:
        """
        Create a deployment.

        Args:
            flow_id: the flow ID to create a deployment for
            name: the name of the deployment
            version: an optional version string for the deployment
            tags: an optional list of tags to apply to the deployment
            storage_document_id: an reference to the storage block document
                used for the deployed flow
            infrastructure_document_id: an reference to the infrastructure block document
                to use for this deployment
            job_variables: A dictionary of dot delimited infrastructure overrides that
                will be applied at runtime; for example `env.CONFIG_KEY=config_value` or
                `namespace='prefect'`. This argument was previously named `infra_overrides`.
                Both arguments are supported for backwards compatibility.

        Raises:
            RequestError: if the deployment was not created for any reason

        Returns:
            the ID of the deployment in the backend
        """

        from prefect.client.schemas.actions import DeploymentCreate

        if parameter_openapi_schema is None:
            parameter_openapi_schema = {}
        deployment_create = DeploymentCreate(
            flow_id=flow_id,
            name=name,
            version=version,
            version_info=version_info,
            parameters=dict(parameters or {}),
            tags=list(tags or []),
            work_queue_name=work_queue_name,
            description=description,
            storage_document_id=storage_document_id,
            path=path,
            entrypoint=entrypoint,
            infrastructure_document_id=infrastructure_document_id,
            job_variables=dict(job_variables or {}),
            parameter_openapi_schema=parameter_openapi_schema,
            paused=paused,
            schedules=schedules or [],
            concurrency_limit=concurrency_limit,
            concurrency_options=concurrency_options,
            pull_steps=pull_steps,
            enforce_parameter_schema=enforce_parameter_schema,
            branch=branch,
            base=base,
            root=root,
        )

        if work_pool_name is not None:
            deployment_create.work_pool_name = work_pool_name

        # Exclude newer fields that are not set to avoid compatibility issues
        exclude = {
            field
            for field in [
                "work_pool_name",
                "work_queue_name",
            ]
            if field not in deployment_create.model_fields_set
        }

        exclude_if_none = [
            "paused",
            "pull_steps",
            "enforce_parameter_schema",
            "version_info",
            "branch",
            "base",
            "root",
        ]

        for field in exclude_if_none:
            if getattr(deployment_create, field) is None:
                exclude.add(field)

        json = deployment_create.model_dump(mode="json", exclude=exclude)

        response = self.request(
            "POST",
            "/deployments/",
            json=json,
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise RequestError(f"Malformed response: {response}")

        return UUID(deployment_id)

    def set_deployment_paused_state(self, deployment_id: UUID, paused: bool) -> None:
        self.request(
            "PATCH",
            "/deployments/{id}",
            path_params={"id": deployment_id},
            json={"paused": paused},
        )

    def update_deployment(
        self,
        deployment_id: UUID,
        deployment: "DeploymentUpdate",
    ) -> None:
        self.request(
            "PATCH",
            "/deployments/{id}",
            path_params={"id": deployment_id},
            json=deployment.model_dump(
                mode="json",
                exclude_unset=True,
                exclude={"name", "flow_name", "triggers"},
            ),
        )

    def _create_deployment_from_schema(self, schema: "DeploymentCreate") -> UUID:
        """
        Create a deployment from a prepared `DeploymentCreate` schema.
        """
        # TODO: We are likely to remove this method once we have considered the
        #       packaging interface for deployments further.
        response = self.request(
            "POST", "/deployments/", json=schema.model_dump(mode="json")
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise RequestError(f"Malformed response: {response}")

        return UUID(deployment_id)

    def read_deployment(
        self,
        deployment_id: Union[UUID, str],
    ) -> "DeploymentResponse":
        """
        Query the Prefect API for a deployment by id.

        Args:
            deployment_id: the deployment ID of interest

        Returns:
            a [Deployment model][prefect.client.schemas.objects.Deployment] representation of the deployment
        """

        from prefect.client.schemas.responses import DeploymentResponse

        if not isinstance(deployment_id, UUID):
            try:
                deployment_id = UUID(deployment_id)
            except ValueError:
                raise ValueError(f"Invalid deployment ID: {deployment_id}")

        try:
            response = self.request(
                "GET",
                "/deployments/{id}",
                path_params={"id": deployment_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return DeploymentResponse.model_validate(response.json())

    def read_deployment_by_name(
        self,
        name: str,
    ) -> "DeploymentResponse":
        """
        Query the Prefect API for a deployment by name.

        Args:
            name: A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>

        Raises:
            ObjectNotFound: If request returns 404
            RequestError: If request fails

        Returns:
            a Deployment model representation of the deployment
        """
        from prefect.client.schemas.responses import DeploymentResponse

        try:
            flow_name, deployment_name = name.split("/")
            response = self.request(
                "GET",
                "/deployments/name/{flow_name}/{deployment_name}",
                path_params={
                    "flow_name": flow_name,
                    "deployment_name": deployment_name,
                },
            )
        except (HTTPStatusError, ValueError) as e:
            if isinstance(e, HTTPStatusError) and e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            elif isinstance(e, ValueError):
                raise ValueError(
                    f"Invalid deployment name format: {name}. Expected format: <FLOW_NAME>/<DEPLOYMENT_NAME>"
                ) from e
            else:
                raise

        return DeploymentResponse.model_validate(response.json())

    def read_deployments(
        self,
        *,
        flow_filter: "FlowFilter | None" = None,
        flow_run_filter: "FlowRunFilter | None" = None,
        task_run_filter: "TaskRunFilter | None" = None,
        deployment_filter: "DeploymentFilter | None" = None,
        work_pool_filter: "WorkPoolFilter | None" = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        limit: int | None = None,
        sort: "DeploymentSort | None" = None,
        offset: int = 0,
    ) -> list["DeploymentResponse"]:
        """
        Query the Prefect API for deployments. Only deployments matching all
        the provided criteria will be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            work_pool_filter: filter criteria for work pools
            work_queue_filter: filter criteria for work pool queues
            limit: a limit for the deployment query
            offset: an offset for the deployment query

        Returns:
            a list of Deployment model representations
                of the deployments
        """
        from prefect.client.schemas.responses import DeploymentResponse

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
            "limit": limit,
            "offset": offset,
            "sort": sort,
        }

        response = self.request("POST", "/deployments/filter", json=body)
        return DeploymentResponse.model_validate_list(response.json())

    def delete_deployment(
        self,
        deployment_id: UUID,
    ) -> None:
        """
        Delete deployment by id.

        Args:
            deployment_id: The deployment id of interest.
        Raises:
            ObjectNotFound: If request returns 404
            RequestError: If requests fails
        """
        try:
            self.request(
                "DELETE",
                "/deployments/{id}",
                path_params={"id": deployment_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def create_deployment_schedules(
        self,
        deployment_id: UUID,
        schedules: list[tuple["SCHEDULE_TYPES", bool]],
    ) -> list["DeploymentSchedule"]:
        """
        Create deployment schedules.

        Args:
            deployment_id: the deployment ID
            schedules: a list of tuples containing the schedule to create
                       and whether or not it should be active.

        Raises:
            RequestError: if the schedules were not created for any reason

        Returns:
            the list of schedules created in the backend
        """
        from prefect.client.schemas.actions import DeploymentScheduleCreate
        from prefect.client.schemas.objects import DeploymentSchedule

        deployment_schedule_create = [
            DeploymentScheduleCreate(schedule=schedule[0], active=schedule[1])
            for schedule in schedules
        ]

        json = [
            deployment_schedule_create.model_dump(mode="json")
            for deployment_schedule_create in deployment_schedule_create
        ]
        response = self.request(
            "POST",
            "/deployments/{id}/schedules",
            path_params={"id": deployment_id},
            json=json,
        )
        return DeploymentSchedule.model_validate_list(response.json())

    def read_deployment_schedules(
        self,
        deployment_id: UUID,
    ) -> list["DeploymentSchedule"]:
        """
        Query the Prefect API for a deployment's schedules.

        Args:
            deployment_id: the deployment ID

        Returns:
            a list of DeploymentSchedule model representations of the deployment schedules
        """
        from prefect.client.schemas.objects import DeploymentSchedule

        try:
            response = self.request(
                "GET",
                "/deployments/{id}/schedules",
                path_params={"id": deployment_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return DeploymentSchedule.model_validate_list(response.json())

    def update_deployment_schedule(
        self,
        deployment_id: UUID,
        schedule_id: UUID,
        active: bool | None = None,
        schedule: "SCHEDULE_TYPES | None" = None,
    ) -> None:
        """
        Update a deployment schedule by ID.

        Args:
            deployment_id: the deployment ID
            schedule_id: the deployment schedule ID of interest
            active: whether or not the schedule should be active
            schedule: the cron, rrule, or interval schedule this deployment schedule should use
        """
        from prefect.client.schemas.actions import DeploymentScheduleUpdate

        kwargs: dict[str, Any] = {}
        if active is not None:
            kwargs["active"] = active
        if schedule is not None:
            kwargs["schedule"] = schedule

        deployment_schedule_update = DeploymentScheduleUpdate(**kwargs)
        json = deployment_schedule_update.model_dump(mode="json", exclude_unset=True)

        try:
            self.request(
                "PATCH",
                "/deployments/{id}/schedules/{schedule_id}",
                path_params={"id": deployment_id, "schedule_id": schedule_id},
                json=json,
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def delete_deployment_schedule(
        self,
        deployment_id: UUID,
        schedule_id: UUID,
    ) -> None:
        """
        Delete a deployment schedule.

        Args:
            deployment_id: the deployment ID
            schedule_id: the ID of the deployment schedule to delete.

        Raises:
            RequestError: if the schedules were not deleted for any reason
        """
        try:
            self.request(
                "DELETE",
                "/deployments/{id}/schedules/{schedule_id}",
                path_params={"id": deployment_id, "schedule_id": schedule_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def get_scheduled_flow_runs_for_deployments(
        self,
        deployment_ids: list[UUID],
        scheduled_before: "datetime.datetime | None" = None,
        limit: int | None = None,
    ) -> list["FlowRunResponse"]:
        from prefect.client.schemas.responses import FlowRunResponse

        body: dict[str, Any] = dict(deployment_ids=[str(id) for id in deployment_ids])
        if scheduled_before:
            body["scheduled_before"] = str(scheduled_before)
        if limit:
            body["limit"] = limit

        response = self.request(
            "POST",
            "/deployments/get_scheduled_flow_runs",
            json=body,
        )

        return FlowRunResponse.model_validate_list(response.json())

    def create_flow_run_from_deployment(
        self,
        deployment_id: UUID,
        *,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        state: State[Any] | None = None,
        name: str | None = None,
        tags: Iterable[str] | None = None,
        idempotency_key: str | None = None,
        parent_task_run_id: UUID | None = None,
        work_queue_name: str | None = None,
        job_variables: dict[str, Any] | None = None,
        labels: "KeyValueLabelsField | None" = None,
    ) -> "FlowRun":
        """
        Create a flow run for a deployment.

        Args:
            deployment_id: The deployment ID to create the flow run from
            parameters: Parameter overrides for this flow run. Merged with the
                deployment defaults
            context: Optional run context data
            state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.
            name: An optional name for the flow run. If not provided, the server will
                generate a name.
            tags: An optional iterable of tags to apply to the flow run; these tags
                are merged with the deployment's tags.
            idempotency_key: Optional idempotency key for creation of the flow run.
                If the key matches the key of an existing flow run, the existing run will
                be returned instead of creating a new one.
            parent_task_run_id: if a subflow run is being created, the placeholder task
                run identifier in the parent flow
            work_queue_name: An optional work queue name to add this run to. If not provided,
                will default to the deployment's set work queue.  If one is provided that does not
                exist, a new work queue will be created within the deployment's work pool.
            job_variables: Optional variables that will be supplied to the flow run job.

        Raises:
            RequestError: if the Prefect API does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        from prefect.client.schemas.actions import DeploymentFlowRunCreate
        from prefect.client.schemas.objects import FlowRun
        from prefect.states import Scheduled, to_state_create

        parameters = parameters or {}
        context = context or {}
        state = state or Scheduled()
        tags = tags or []
        labels = labels or {}

        flow_run_create = DeploymentFlowRunCreate(
            parameters=parameters,
            context=context,
            state=to_state_create(state),
            tags=list(tags),
            name=name,
            idempotency_key=idempotency_key,
            parent_task_run_id=parent_task_run_id,
            job_variables=job_variables,
            labels=labels,
        )

        # done separately to avoid including this field in payloads sent to older API versions
        if work_queue_name:
            flow_run_create.work_queue_name = work_queue_name

        response = self.request(
            "POST",
            "/deployments/{id}/create_flow_run",
            path_params={"id": deployment_id},
            json=flow_run_create.model_dump(mode="json", exclude_unset=True),
        )
        return FlowRun.model_validate(response.json())

    def create_deployment_branch(
        self,
        deployment_id: UUID,
        branch: str,
        options: "DeploymentBranchingOptions | None" = None,
        overrides: "DeploymentUpdate | None" = None,
    ) -> UUID:
        from prefect.client.schemas.actions import DeploymentBranch
        from prefect.client.schemas.objects import DeploymentBranchingOptions

        response = self.request(
            "POST",
            "/deployments/{id}/branch",
            path_params={"id": deployment_id},
            json=DeploymentBranch(
                branch=branch,
                options=options or DeploymentBranchingOptions(),
                overrides=overrides,
            ).model_dump(mode="json", exclude_unset=True),
        )
        return UUID(response.json().get("id"))


class DeploymentAsyncClient(BaseAsyncClient):
    async def create_deployment(
        self,
        flow_id: UUID,
        name: str,
        version: str | None = None,
        version_info: "VersionInfo | None" = None,
        schedules: list["DeploymentScheduleCreate"] | None = None,
        concurrency_limit: int | None = None,
        concurrency_options: "ConcurrencyOptions | None" = None,
        parameters: dict[str, Any] | None = None,
        description: str | None = None,
        work_queue_name: str | None = None,
        work_pool_name: str | None = None,
        tags: list[str] | None = None,
        storage_document_id: UUID | None = None,
        path: str | None = None,
        entrypoint: str | None = None,
        infrastructure_document_id: UUID | None = None,
        parameter_openapi_schema: dict[str, Any] | None = None,
        paused: bool | None = None,
        pull_steps: list[dict[str, Any]] | None = None,
        enforce_parameter_schema: bool | None = None,
        job_variables: dict[str, Any] | None = None,
        branch: str | None = None,
        base: UUID | None = None,
        root: UUID | None = None,
    ) -> UUID:
        """
        Create a deployment.

        Args:
            flow_id: the flow ID to create a deployment for
            name: the name of the deployment
            version: an optional version string for the deployment
            tags: an optional list of tags to apply to the deployment
            storage_document_id: an reference to the storage block document
                used for the deployed flow
            infrastructure_document_id: an reference to the infrastructure block document
                to use for this deployment
            job_variables: A dictionary of dot delimited infrastructure overrides that
                will be applied at runtime; for example `env.CONFIG_KEY=config_value` or
                `namespace='prefect'`. This argument was previously named `infra_overrides`.
                Both arguments are supported for backwards compatibility.

        Raises:
            RequestError: if the deployment was not created for any reason

        Returns:
            the ID of the deployment in the backend
        """

        from prefect.client.schemas.actions import DeploymentCreate

        if parameter_openapi_schema is None:
            parameter_openapi_schema = {}
        deployment_create = DeploymentCreate(
            flow_id=flow_id,
            name=name,
            version=version,
            version_info=version_info,
            parameters=dict(parameters or {}),
            tags=list(tags or []),
            work_queue_name=work_queue_name,
            description=description,
            storage_document_id=storage_document_id,
            path=path,
            entrypoint=entrypoint,
            infrastructure_document_id=infrastructure_document_id,
            job_variables=dict(job_variables or {}),
            parameter_openapi_schema=parameter_openapi_schema,
            paused=paused,
            schedules=schedules or [],
            concurrency_limit=concurrency_limit,
            concurrency_options=concurrency_options,
            pull_steps=pull_steps,
            enforce_parameter_schema=enforce_parameter_schema,
            branch=branch,
            base=base,
            root=root,
        )

        if work_pool_name is not None:
            deployment_create.work_pool_name = work_pool_name

        # Exclude newer fields that are not set to avoid compatibility issues
        exclude = {
            field
            for field in [
                "work_pool_name",
                "work_queue_name",
            ]
            if field not in deployment_create.model_fields_set
        }

        exclude_if_none = [
            "paused",
            "pull_steps",
            "enforce_parameter_schema",
            "version_info",
            "branch",
            "base",
            "root",
        ]

        for field in exclude_if_none:
            if getattr(deployment_create, field) is None:
                exclude.add(field)

        json = deployment_create.model_dump(mode="json", exclude=exclude)

        response = await self.request(
            "POST",
            "/deployments/",
            json=json,
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise RequestError(f"Malformed response: {response}")

        return UUID(deployment_id)

    async def set_deployment_paused_state(
        self, deployment_id: UUID, paused: bool
    ) -> None:
        await self.request(
            "PATCH",
            "/deployments/{id}",
            path_params={"id": deployment_id},
            json={"paused": paused},
        )

    async def update_deployment(
        self,
        deployment_id: UUID,
        deployment: "DeploymentUpdate",
    ) -> None:
        await self.request(
            "PATCH",
            "/deployments/{id}",
            path_params={"id": deployment_id},
            json=deployment.model_dump(
                mode="json",
                exclude_unset=True,
                exclude={"name", "flow_name", "triggers"},
            ),
        )

    async def _create_deployment_from_schema(self, schema: "DeploymentCreate") -> UUID:
        """
        Create a deployment from a prepared `DeploymentCreate` schema.
        """

        # TODO: We are likely to remove this method once we have considered the
        #       packaging interface for deployments further.
        response = await self.request(
            "POST", "/deployments/", json=schema.model_dump(mode="json")
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise RequestError(f"Malformed response: {response}")

        return UUID(deployment_id)

    async def read_deployment(
        self,
        deployment_id: Union[UUID, str],
    ) -> "DeploymentResponse":
        """
        Query the Prefect API for a deployment by id.

        Args:
            deployment_id: the deployment ID of interest

        Returns:
            a [Deployment model][prefect.client.schemas.objects.Deployment] representation of the deployment
        """

        from prefect.client.schemas.responses import DeploymentResponse

        if not isinstance(deployment_id, UUID):
            try:
                deployment_id = UUID(deployment_id)
            except ValueError:
                raise ValueError(f"Invalid deployment ID: {deployment_id}")

        try:
            response = await self.request(
                "GET",
                "/deployments/{id}",
                path_params={"id": deployment_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return DeploymentResponse.model_validate(response.json())

    async def read_deployment_by_name(
        self,
        name: str,
    ) -> "DeploymentResponse":
        """
        Query the Prefect API for a deployment by name.

        Args:
            name: A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>

        Raises:
            ObjectNotFound: If request returns 404
            RequestError: If request fails

        Returns:
            a Deployment model representation of the deployment
        """
        from prefect.client.schemas.responses import DeploymentResponse

        try:
            flow_name, deployment_name = name.split("/")
            response = await self.request(
                "GET",
                "/deployments/name/{flow_name}/{deployment_name}",
                path_params={
                    "flow_name": flow_name,
                    "deployment_name": deployment_name,
                },
            )
        except (HTTPStatusError, ValueError) as e:
            if isinstance(e, HTTPStatusError) and e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            elif isinstance(e, ValueError):
                raise ValueError(
                    f"Invalid deployment name format: {name}. Expected format: <FLOW_NAME>/<DEPLOYMENT_NAME>"
                ) from e
            else:
                raise

        return DeploymentResponse.model_validate(response.json())

    async def read_deployments(
        self,
        *,
        flow_filter: "FlowFilter | None" = None,
        flow_run_filter: "FlowRunFilter | None" = None,
        task_run_filter: "TaskRunFilter | None" = None,
        deployment_filter: "DeploymentFilter | None" = None,
        work_pool_filter: "WorkPoolFilter | None" = None,
        work_queue_filter: "WorkQueueFilter | None" = None,
        limit: int | None = None,
        sort: "DeploymentSort | None" = None,
        offset: int = 0,
    ) -> list["DeploymentResponse"]:
        """
        Query the Prefect API for deployments. Only deployments matching all
        the provided criteria will be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            work_pool_filter: filter criteria for work pools
            work_queue_filter: filter criteria for work pool queues
            limit: a limit for the deployment query
            offset: an offset for the deployment query

        Returns:
            a list of Deployment model representations
                of the deployments
        """
        from prefect.client.schemas.responses import DeploymentResponse

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
            "limit": limit,
            "offset": offset,
            "sort": sort,
        }

        response = await self.request("POST", "/deployments/filter", json=body)
        return DeploymentResponse.model_validate_list(response.json())

    async def delete_deployment(
        self,
        deployment_id: UUID,
    ) -> None:
        """
        Delete deployment by id.

        Args:
            deployment_id: The deployment id of interest.
        Raises:
            ObjectNotFound: If request returns 404
            RequestError: If requests fails
        """
        try:
            await self.request(
                "DELETE",
                "/deployments/{id}",
                path_params={"id": deployment_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def create_deployment_schedules(
        self,
        deployment_id: UUID,
        schedules: list[tuple["SCHEDULE_TYPES", bool]],
    ) -> list["DeploymentSchedule"]:
        """
        Create deployment schedules.

        Args:
            deployment_id: the deployment ID
            schedules: a list of tuples containing the schedule to create
                       and whether or not it should be active.

        Raises:
            RequestError: if the schedules were not created for any reason

        Returns:
            the list of schedules created in the backend
        """
        from prefect.client.schemas.actions import DeploymentScheduleCreate
        from prefect.client.schemas.objects import DeploymentSchedule

        deployment_schedule_create = [
            DeploymentScheduleCreate(schedule=schedule[0], active=schedule[1])
            for schedule in schedules
        ]

        json = [
            deployment_schedule_create.model_dump(mode="json")
            for deployment_schedule_create in deployment_schedule_create
        ]
        response = await self.request(
            "POST",
            "/deployments/{id}/schedules",
            path_params={"id": deployment_id},
            json=json,
        )
        return DeploymentSchedule.model_validate_list(response.json())

    async def read_deployment_schedules(
        self,
        deployment_id: UUID,
    ) -> list["DeploymentSchedule"]:
        """
        Query the Prefect API for a deployment's schedules.

        Args:
            deployment_id: the deployment ID

        Returns:
            a list of DeploymentSchedule model representations of the deployment schedules
        """
        from prefect.client.schemas.objects import DeploymentSchedule

        try:
            response = await self.request(
                "GET",
                "/deployments/{id}/schedules",
                path_params={"id": deployment_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return DeploymentSchedule.model_validate_list(response.json())

    async def update_deployment_schedule(
        self,
        deployment_id: UUID,
        schedule_id: UUID,
        active: bool | None = None,
        schedule: "SCHEDULE_TYPES | None" = None,
    ) -> None:
        """
        Update a deployment schedule by ID.

        Args:
            deployment_id: the deployment ID
            schedule_id: the deployment schedule ID of interest
            active: whether or not the schedule should be active
            schedule: the cron, rrule, or interval schedule this deployment schedule should use
        """
        from prefect.client.schemas.actions import DeploymentScheduleUpdate

        kwargs: dict[str, Any] = {}
        if active is not None:
            kwargs["active"] = active
        if schedule is not None:
            kwargs["schedule"] = schedule

        deployment_schedule_update = DeploymentScheduleUpdate(**kwargs)
        json = deployment_schedule_update.model_dump(mode="json", exclude_unset=True)

        try:
            await self.request(
                "PATCH",
                "/deployments/{id}/schedules/{schedule_id}",
                path_params={"id": deployment_id, "schedule_id": schedule_id},
                json=json,
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_deployment_schedule(
        self,
        deployment_id: UUID,
        schedule_id: UUID,
    ) -> None:
        """
        Delete a deployment schedule.

        Args:
            deployment_id: the deployment ID
            schedule_id: the ID of the deployment schedule to delete.

        Raises:
            RequestError: if the schedules were not deleted for any reason
        """
        try:
            await self.request(
                "DELETE",
                "/deployments/{id}/schedules/{schedule_id}",
                path_params={"id": deployment_id, "schedule_id": schedule_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def get_scheduled_flow_runs_for_deployments(
        self,
        deployment_ids: list[UUID],
        scheduled_before: "datetime.datetime | None" = None,
        limit: int | None = None,
    ) -> list["FlowRun"]:
        from prefect.client.schemas.objects import FlowRun

        body: dict[str, Any] = dict(deployment_ids=[str(id) for id in deployment_ids])
        if scheduled_before:
            body["scheduled_before"] = str(scheduled_before)
        if limit:
            body["limit"] = limit

        response = await self.request(
            "POST",
            "/deployments/get_scheduled_flow_runs",
            json=body,
        )

        return FlowRun.model_validate_list(response.json())

    async def create_flow_run_from_deployment(
        self,
        deployment_id: UUID,
        *,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        state: State[Any] | None = None,
        name: str | None = None,
        tags: Iterable[str] | None = None,
        idempotency_key: str | None = None,
        parent_task_run_id: UUID | None = None,
        work_queue_name: str | None = None,
        job_variables: dict[str, Any] | None = None,
        labels: "KeyValueLabelsField | None" = None,
    ) -> "FlowRun":
        """
        Create a flow run for a deployment.

        Args:
            deployment_id: The deployment ID to create the flow run from
            parameters: Parameter overrides for this flow run. Merged with the
                deployment defaults
            context: Optional run context data
            state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.
            name: An optional name for the flow run. If not provided, the server will
                generate a name.
            tags: An optional iterable of tags to apply to the flow run; these tags
                are merged with the deployment's tags.
            idempotency_key: Optional idempotency key for creation of the flow run.
                If the key matches the key of an existing flow run, the existing run will
                be returned instead of creating a new one.
            parent_task_run_id: if a subflow run is being created, the placeholder task
                run identifier in the parent flow
            work_queue_name: An optional work queue name to add this run to. If not provided,
                will default to the deployment's set work queue.  If one is provided that does not
                exist, a new work queue will be created within the deployment's work pool.
            job_variables: Optional variables that will be supplied to the flow run job.

        Raises:
            RequestError: if the Prefect API does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        from prefect.client.schemas.actions import DeploymentFlowRunCreate
        from prefect.client.schemas.objects import FlowRun
        from prefect.states import Scheduled, to_state_create

        parameters = parameters or {}
        context = context or {}
        state = state or Scheduled()
        tags = tags or []
        labels = labels or {}

        flow_run_create = DeploymentFlowRunCreate(
            parameters=parameters,
            context=context,
            state=to_state_create(state),
            tags=list(tags),
            name=name,
            idempotency_key=idempotency_key,
            parent_task_run_id=parent_task_run_id,
            job_variables=job_variables,
            labels=labels,
        )

        # done separately to avoid including this field in payloads sent to older API versions
        if work_queue_name:
            flow_run_create.work_queue_name = work_queue_name

        response = await self.request(
            "POST",
            "/deployments/{id}/create_flow_run",
            path_params={"id": deployment_id},
            json=flow_run_create.model_dump(mode="json", exclude_unset=True),
        )
        return FlowRun.model_validate(response.json())

    async def create_deployment_branch(
        self,
        deployment_id: UUID,
        branch: str,
        options: "DeploymentBranchingOptions | None" = None,
        overrides: "DeploymentUpdate | None" = None,
    ) -> UUID:
        from prefect.client.schemas.actions import DeploymentBranch
        from prefect.client.schemas.objects import DeploymentBranchingOptions

        response = await self.request(
            "POST",
            "/deployments/{id}/branch",
            path_params={"id": deployment_id},
            json=DeploymentBranch(
                branch=branch,
                options=options or DeploymentBranchingOptions(),
                overrides=overrides,
            ).model_dump(mode="json", exclude_unset=True),
        )
        return UUID(response.json().get("id"))
