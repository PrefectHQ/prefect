"""
Asynchronous client implementation for communicating with the [Orion REST API](/api-ref/rest-api/).

Explore the client by communicating with an in-memory webserver - no setup required:

<div class="termy">
```
$ # start python REPL with native await functionality
$ python -m asyncio
>>> from prefect.client import OrionClient
>>> async with OrionClient() as client:
...     response = await client.hello()
...     print(response.json())
👋
```
</div>
"""
import os
from functools import wraps
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Union
from uuid import UUID

import anyio
import httpx
import pydantic

import prefect
from prefect import exceptions, settings
from prefect.orion import schemas
from prefect.orion.api.server import app as orion_app
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Scheduled
from prefect.utilities.logging import get_logger

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task


def inject_client(fn):
    """
    Simple helper to provide a context managed client to a asynchronous function.

    The decorated function _must_ take a `client` kwarg and if a client is passed when
    called it will be used instead of creating a new one, but it will not be context
    managed as it is assumed that the caller is managing the context.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if "client" in kwargs and kwargs["client"] is not None:
            return await fn(*args, **kwargs)
        else:
            client = OrionClient()
            async with client:
                kwargs["client"] = client
                return await fn(*args, **kwargs)

    return wrapper


class OrionClient:
    """
    An asynchronous client for interacting with the [Orion REST API](/api-ref/rest-api/).

    Args:
        host: the Orion API URL
        httpx_settings: an optional dictionary of settings to pass to the underlying `httpx.AsyncClient`

    Examples:

        Say hello to an Orion server

        >>> async with OrionClient() as client:
        >>>     response = await client.hello()
        >>>
        >>> print(response.json())
        👋
    """

    def __init__(
        self, host: str = prefect.settings.orion_host, httpx_settings: dict = None
    ) -> None:
        httpx_settings = httpx_settings or {}

        if host:
            # Connect to an existing instance
            if "app" in httpx_settings:
                raise ValueError(
                    "Invalid httpx settings: `app` cannot be set with `host`, "
                    "`app` is only for use with ephemeral instances."
                )
            httpx_settings.setdefault("base_url", host)
        else:
            # Connect to an ephemeral app
            httpx_settings.setdefault("app", orion_app)
            httpx_settings.setdefault("base_url", "http://orion/api")

        self._client = httpx.AsyncClient(**httpx_settings)
        self.logger = get_logger("client")

    async def post(self, route: str, **kwargs) -> httpx.Response:
        """
        Send a POST request to the provided route.

        Args:
            route: the path to make the request to
            **kwargs: see [`httpx.request`](https://www.python-httpx.org/api/)

        Raises:
            httpx.HTTPStatusError: if a non-200 status code is returned

        Returns:
            an `httpx.Response` object
        """
        response = await self._client.post(route, **kwargs)
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    async def patch(self, route: str, **kwargs) -> httpx.Response:
        """
        Send a PATCH request to the provided route.

        Args:
            route: the path to make the request to
            **kwargs: see [`httpx.request`](https://www.python-httpx.org/api/)

        Raises:
            httpx.HTTPStatusError: if a non-200 status code is returned

        Returns:
            an `httpx.Response` object
        """
        response = await self._client.patch(route, **kwargs)
        response.raise_for_status()
        return response

    async def get(
        self,
        route: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Send a GET request to the provided route.

        Args:
            route: the path to make the request to
            **kwargs: see [`httpx.request`](https://www.python-httpx.org/api/)

        Raises:
            httpx.HTTPStatusError: if a non-200 status code is returned

        Returns:
            an `httpx.Response` object
        """
        response = await self._client.get(route, **kwargs)
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    # API methods ----------------------------------------------------------------------

    async def hello(self) -> httpx.Response:
        """
        Send a GET request to /hello for testing purposes.
        """
        return await self.get("/admin/hello")

    async def create_flow(self, flow: "Flow") -> UUID:
        """
        Create a flow in Orion.

        Args:
            flow: a [Flow][prefect.flows.Flow] object

        Raises:
            httpx.RequestError: if a flow was not created for any reason

        Returns:
            the ID of the flow in the backend
        """
        flow_data = schemas.actions.FlowCreate(name=flow.name)
        response = await self.post("/flows/", json=flow_data.dict(json_compatible=True))

        flow_id = response.json().get("id")
        if not flow_id:
            raise httpx.RequestError(f"Malformed response: {response}")

        # Return the id of the created flow
        return UUID(flow_id)

    async def read_flow(self, flow_id: UUID) -> schemas.core.Flow:
        """
        Query Orion for a flow by id.

        Args:
            flow_id: the flow ID of interest

        Returns:
            a [Flow model][prefect.orion.schemas.core.Flow] representation of the flow
        """
        response = await self.get(f"/flows/{flow_id}")
        return schemas.core.Flow.parse_obj(response.json())

    async def read_flows(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        limit: int = settings.orion.api.default_limit,
        offset: int = 0,
    ) -> List[schemas.core.Flow]:
        """
        Query Orion for flows. Only flows matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            limit: limit for the flow query
            offset: offset for the flow query

        Returns:
            a list of [Flow model][prefect.orion.schemas.core.Flow] representation
                of the flows
        """
        body = {
            "flows": (flow_filter.dict(json_compatible=True) if flow_filter else None),
            "flow_runs": (
                flow_run_filter.dict(json_compatible=True) if flow_run_filter else None
            ),
            "task_runs": (
                task_run_filter.dict(json_compatible=True) if task_run_filter else None
            ),
            "deployments": (
                deployment_filter.dict(json_compatible=True)
                if deployment_filter
                else None
            ),
            "limit": limit,
            "offset": offset,
        }

        response = await self.post(f"/flows/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.Flow], response.json())

    async def read_flow_by_name(
        self,
        flow_name: str,
    ) -> schemas.core.Flow:
        """
        Query Orion for a flow by name.

        Args:
            flow_name: the name of a flow

        Returns:
            a fully hydrated [Flow model][prefect.orion.schemas.core.Flow]
        """
        response = await self.get(f"/flows/name/{flow_name}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def create_flow_run_from_deployment(
        self,
        deployment: schemas.core.Deployment,
        *,
        parameters: Dict[str, Any] = None,
        context: dict = None,
        state: schemas.states.State = None,
    ) -> schemas.core.FlowRun:
        """
        Create a flow run for a deployment.

        Args:
            deployment: The deployment model to create the flow run from
            parameters: Parameter overrides for this flow run. Merged with the
                deployment defaults
            context: Optional run context data
            state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.

        Raises:
            httpx.RequestError: if Orion does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        parameters = parameters or {}
        context = context or {}
        state = state or Scheduled()

        flow_run_create = schemas.actions.DeploymentFlowRunCreate(
            parameters=parameters,
            context=context,
            state=state,
        )

        response = await self.post(
            f"/deployments/{deployment.id}/create_flow_run",
            json=flow_run_create.dict(json_compatible=True),
        )
        return schemas.core.FlowRun.parse_obj(response.json())

    async def create_flow_run(
        self,
        flow: "Flow",
        name: str = None,
        parameters: Dict[str, Any] = None,
        context: dict = None,
        tags: Iterable[str] = None,
        parent_task_run_id: UUID = None,
        state: schemas.states.State = None,
    ) -> schemas.core.FlowRun:
        """
        Create a flow run for a flow.

        Args:
            flow: The flow model to create the flow run for
            name: An optional name for the flow run
            parameters: Parameter overrides for this flow run.
            context: Optional run context data
            tags: a list of tags to apply to this flow run
            parent_task_run_id: if a subflow run is being created, the placeholder task run ID
                of the parent flow
            state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.

        Raises:
            httpx.RequestError: if Orion does not successfully create a run for any reason

        Returns:
            The flow run model
        """
        parameters = parameters or {}
        context = context or {}

        if state is None:
            state = schemas.states.Pending()

        # Retrieve the flow id
        flow_id = await self.create_flow(flow)

        flow_run_create = schemas.actions.FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            name=name,
            parameters=parameters,
            context=context,
            tags=list(tags or []),
            parent_task_run_id=parent_task_run_id,
            state=state,
        )

        flow_run_create_json = flow_run_create.dict(json_compatible=True)

        response = await self.post("/flow_runs/", json=flow_run_create_json)
        flow_run = schemas.core.FlowRun.parse_obj(response.json())

        # Restore the parameters to the local objects to retain expectations about
        # Python objects
        flow_run.parameters = parameters

        return flow_run

    async def update_flow_run(
        self, flow_run_id: UUID, flow_version: str = None, parameters: dict = None
    ) -> None:
        """
        Update a flow run's details.

        Args:
            flow_run_id: the run ID to update
            flow_version: a new version string for the flow run
            parameters: a dictionary of updated parameter values for the run

        Returns:
            an `httpx.Response` object from the PATCH request
        """
        params = {}
        if flow_version is not None:
            params["flow_version"] = flow_version
        if parameters is not None:
            params["parameters"] = parameters
        flow_run_data = schemas.actions.FlowRunUpdate(**params)

        return await self.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.dict(json_compatible=True, exclude_unset=True),
        )

    async def create_deployment(
        self,
        flow_id: UUID,
        name: str,
        flow_data: DataDocument,
        schedule: schemas.schedules.SCHEDULE_TYPES = None,
        parameters: Dict[str, Any] = None,
        tags: List[str] = None,
    ) -> UUID:
        """
        Create a flow deployment in Orion.

        Args:
            flow_id: the flow ID to create a deployment for
            name: the name of the deployment
            flow_data: a data document that can be resolved into a flow object or script
            schedule: an optional schedule to apply to the deployment
            tags: an optional list of tags to apply to the deployment

        Raises:
            httpx.RequestError: if the deployment was not created for any reason

        Returns:
            the ID of the deployment in the backend
        """
        deployment_create = schemas.actions.DeploymentCreate(
            flow_id=flow_id,
            name=name,
            schedule=schedule,
            flow_data=flow_data,
            parameters=dict(parameters or {}),
            tags=list(tags or []),
        )

        response = await self.post(
            "/deployments/", json=deployment_create.dict(json_compatible=True)
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise httpx.RequestError(f"Malformed response: {response}")

        return UUID(deployment_id)

    async def read_deployment(
        self,
        deployment_id: UUID,
    ) -> schemas.core.Deployment:
        """
        Query Orion for a deployment by id.

        Args:
            deployment_id: the deployment ID of interest

        Returns:
            a [Deployment model][prefect.orion.schemas.core.Deployment] representation of the deployment
        """
        response = await self.get(f"/deployments/{deployment_id}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def read_deployment_by_name(
        self,
        name: str,
    ) -> schemas.core.Deployment:
        """
        Query Orion for a deployment by name.

        Args:
            name: the deployment name of interest

        Returns:
            a [Deployment model][prefect.orion.schemas.core.Deployment] representation of the deployment
        """
        response = await self.get(f"/deployments/name/{name}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def read_deployments(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        limit: int = settings.orion.api.default_limit,
        offset: int = 0,
    ) -> schemas.core.Deployment:
        """
        Query Orion for deployments. Only deployments matching all
        the provided criteria will be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            limit: a limit for the deployment query
            offset: an offset for the deployment query

        Returns:
            a list of [Deployment model][prefect.orion.schemas.core.Deployment] representation
                of the deployments
        """
        body = {
            "flows": (flow_filter.dict(json_compatible=True) if flow_filter else None),
            "flow_runs": (
                flow_run_filter.dict(json_compatible=True) if flow_run_filter else None
            ),
            "task_runs": (
                task_run_filter.dict(json_compatible=True) if task_run_filter else None
            ),
            "deployments": (
                deployment_filter.dict(json_compatible=True)
                if deployment_filter
                else None
            ),
            "limit": limit,
            "offset": offset,
        }
        response = await self.post(f"/deployments/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.Deployment], response.json())

    async def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        """
        Query Orion for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a [Flow Run model][prefect.orion.schemas.core.FlowRun] representation of the flow run
        """
        response = await self.get(f"/flow_runs/{flow_run_id}")
        return schemas.core.FlowRun.parse_obj(response.json())

    async def read_flow_runs(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        sort: schemas.sorting.FlowRunSort = None,
        limit: int = settings.orion.api.default_limit,
        offset: int = 0,
    ) -> List[schemas.core.FlowRun]:
        """
        Query Orion for flow runs. Only flow runs matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            sort: sort criteria for the flow runs
            limit: limit for the flow run query
            offset: offset for the flow run query

        Returns:
            a list of [Flow Run model][prefect.orion.schemas.core.FlowRun] representation
                of the flow runs
        """
        body = {
            "flows": (flow_filter.dict(json_compatible=True) if flow_filter else None),
            "flow_runs": (
                flow_run_filter.dict(json_compatible=True) if flow_run_filter else None
            ),
            "task_runs": (
                task_run_filter.dict(json_compatible=True) if task_run_filter else None
            ),
            "deployments": (
                deployment_filter.dict(json_compatible=True)
                if deployment_filter
                else None
            ),
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }

        response = await self.post(f"/flow_runs/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.FlowRun], response.json())

    async def persist_data(
        self,
        data: bytes,
    ) -> DataDocument:
        """
        Persist data in orion and return the orion data document

        Args:
            data: the data to persist

        Returns:
            orion data document pointing to persisted data
        """
        response = await self.post("/data/persist", content=data)
        orion_doc = DataDocument.parse_obj(response.json())
        return orion_doc

    async def retrieve_data(
        self,
        orion_datadoc: DataDocument,
    ) -> bytes:
        """
        Exchange an orion data document for the data previously persisted.

        Args:
            orion_datadoc: the orion data document to retrieve

        Returns:
            the persisted data in bytes
        """
        if orion_datadoc.has_cached_data():
            return orion_datadoc.decode()

        response = await self.post(
            "/data/retrieve", json=orion_datadoc.dict(json_compatible=True)
        )
        return response.content

    async def persist_object(
        self, obj: Any, encoder: str = "cloudpickle"
    ) -> DataDocument:
        """
        Persist an object in orion and return the orion data document

        Args:
            obj: the object to persist
            encoder: an optional encoder for data document

        Returns:
            orion data document pointing to persisted data
        """
        datadoc = DataDocument.encode(encoding=encoder, data=obj)
        return await self.persist_data(datadoc.json().encode())

    async def retrieve_object(self, orion_datadoc: DataDocument) -> Any:
        """
        Exchange an orion data document for the object previously persisted.

        Args:
            orion_datadoc: the orion data document to retrieve

        Returns:
            the persisted object
        """
        datadoc = DataDocument.parse_raw(await self.retrieve_data(orion_datadoc))
        return datadoc.decode()

    async def set_flow_run_state(
        self,
        flow_run_id: UUID,
        state: schemas.states.State,
        force: bool = False,
        orion_doc: schemas.data.DataDocument = None,
    ) -> OrchestrationResult:
        """
        Set the state of a flow run.

        Args:
            flow_run_id: the id of the flow run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Orion API to accept the state
            orion_doc: an optional orion data document representing the state's data,
                if provided it will override `state.data`

        Returns:
            a [OrchestrationResult model][prefect.orion.orchestration.rules.OrchestrationResult]
                representation of state orchestration output
        """
        state_data = schemas.actions.StateCreate(
            type=state.type,
            name=state.name,
            message=state.message,
            data=orion_doc or state.data,
            state_details=state.state_details,
        )
        state_data.state_details.flow_run_id = flow_run_id

        # Attempt to serialize the given data
        try:
            state_data_json = state_data.dict(json_compatible=True)
        except TypeError:
            # Drop the user data
            state_data.data = None
            state_data_json = state_data.dict(json_compatible=True)

        response = await self.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=dict(state=state_data_json, force=force),
        )
        return OrchestrationResult.parse_obj(response.json())

    async def read_flow_run_states(
        self, flow_run_id: UUID
    ) -> List[schemas.states.State]:
        """
        Query for the states of a flow run

        Args:
            flow_run_id: the id of the flow run

        Returns:
            a list of [State model][prefect.orion.schemas.states.State] representation
                of the flow run states
        """
        response = await self.get(
            "/flow_run_states/", params=dict(flow_run_id=flow_run_id)
        )
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

    async def create_task_run(
        self,
        task: "Task",
        flow_run_id: UUID,
        dynamic_key: str,
        name: str = None,
        extra_tags: Iterable[str] = None,
        state: schemas.states.State = None,
        task_inputs: Dict[
            str,
            List[
                Union[
                    schemas.core.TaskRunResult,
                    schemas.core.Parameter,
                    schemas.core.Constant,
                ]
            ],
        ] = None,
    ) -> UUID:
        """
        Create a task run

        Args:
            task: The Task to run
            flow_run_id: The flow run id with which to associate the task run
            dynamic_key: A key unique to this particular run of a Task within the flow
            name: An optional name for the task run
            extra_tags: an optional list of extra tags to apply to the task run in
                addition to `task.tags`
            state: The initial state for the run. If not provided, defaults to
                `Pending` for now. Should always be a `Scheduled` type.
            task_inputs: the set of inputs passed to the task

        Returns:
            The UUID of the newly created task run
        """
        tags = set(task.tags).union(extra_tags or [])

        if state is None:
            state = schemas.states.Pending()

        task_run_data = schemas.actions.TaskRunCreate(
            name=name or f"{task.name}-{task.task_key[:8]}-{dynamic_key}",
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=dynamic_key,
            tags=list(tags),
            empirical_policy=schemas.core.TaskRunPolicy(
                max_retries=task.retries,
                retry_delay_seconds=task.retry_delay_seconds,
            ),
            state=state,
            task_inputs=task_inputs or {},
        )

        response = await self.post(
            "/task_runs/", json=task_run_data.dict(json_compatible=True)
        )
        return TaskRun.parse_obj(response.json())

    async def read_task_run(self, task_run_id: UUID) -> schemas.core.TaskRun:
        """
        Query Orion for a task run by id.

        Args:
            task_run_id: the task run ID of interest

        Returns:
            a [Task Run model][prefect.orion.schemas.core.TaskRun] representation of the task run
        """
        response = await self.get(f"/task_runs/{task_run_id}")
        return schemas.core.TaskRun.parse_obj(response.json())

    async def read_task_runs(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        sort: schemas.sorting.TaskRunSort = None,
        limit: int = settings.orion.api.default_limit,
        offset: int = 0,
    ) -> List[schemas.core.TaskRun]:
        """
        Query Orion for task runs. Only task runs matching all criteria will
        be returned.

        Args:
            flow_filter: filter criteria for flows
            flow_run_filter: filter criteria for flow runs
            task_run_filter: filter criteria for task runs
            deployment_filter: filter criteria for deployments
            sort: sort criteria for the task runs
            limit: a limit for the task run query
            offset: an offset for the task run query

        Returns:
            a list of [Task Run model][prefect.orion.schemas.core.TaskRun] representation
                of the task runs
        """
        body = {
            "flows": (flow_filter.dict(json_compatible=True) if flow_filter else None),
            "flow_runs": (
                flow_run_filter.dict(json_compatible=True) if flow_run_filter else None
            ),
            "task_runs": (
                task_run_filter.dict(json_compatible=True) if task_run_filter else None
            ),
            "deployments": (
                deployment_filter.dict(json_compatible=True)
                if deployment_filter
                else None
            ),
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }
        response = await self.post(f"/task_runs/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.TaskRun], response.json())

    async def propose_state(
        self,
        state: schemas.states.State,
        task_run_id: UUID = None,
        flow_run_id: UUID = None,
    ) -> schemas.states.State:
        """
        Propose a new state for a flow run or task run, invoking Orion
        orchestration logic.

        If the proposed state is accepted, the provided `state` will be
        augmented with details and returned.

        If the proposed state is rejected, a new state returned by the
        Orion API will be returned.

        If the proposed state results in a WAIT instruction from the Orion
        API, the function will sleep and attempt to propose the state again.

        If the proposed state results in an ABORT instruction from the Orion
        API, an error will be raised.

        Args:
            state: a new state for the task or flow run
            task_run_id: an optional task run id, used when proposing task run states
            flow_run_id: an optional flow run id, used when proposing flow run states

        Returns:
            a [State model][prefect.orion.schemas.states.State] representation of the
                flow or task run state

        Raises:
            ValueError: if neither task_run_id or flow_run_id is provided
            prefect.exceptions.Abort: if an ABORT instruction is received from
                the Orion API
        """

        # Determine if working with a task run or flow run
        if not task_run_id and not flow_run_id:
            raise ValueError("You must provide either a `task_run_id` or `flow_run_id`")

        orion_doc = None
        # Exchange the user data document for an orion data document
        if state.data:
            # persist data reference in Orion
            orion_doc = await self.persist_data(state.data.json().encode())

        # Attempt to set the state
        if task_run_id:
            response = await self.set_task_run_state(
                task_run_id, state, orion_doc=orion_doc
            )
        elif flow_run_id:
            response = await self.set_flow_run_state(
                flow_run_id, state, orion_doc=orion_doc
            )
        else:
            raise ValueError(
                "Neither flow run id or task run id were provided. At least one must "
                "be given."
            )

        # Parse the response to return the new state
        if response.status == schemas.responses.SetStateStatus.ACCEPT:
            # Update the state with the details if provided
            if response.state.state_details:
                state.state_details = response.state.state_details
            return state

        elif response.status == schemas.responses.SetStateStatus.ABORT:
            raise exceptions.Abort(response.details.reason)

        elif response.status == schemas.responses.SetStateStatus.WAIT:
            self.logger.debug(
                f"Received wait instruction for {response.details.delay_seconds}s: "
                f"{response.details.reason}"
            )
            await anyio.sleep(response.details.delay_seconds)
            return await self.propose_state(
                state, task_run_id=task_run_id, flow_run_id=flow_run_id
            )

        elif response.status == schemas.responses.SetStateStatus.REJECT:
            server_state = response.state
            if server_state.data:
                if server_state.data.encoding == "orion":
                    datadoc = DataDocument.parse_raw(
                        await self.retrieve_data(server_state.data)
                    )
                    server_state.data = datadoc

            return server_state

        else:
            raise ValueError(
                f"Received unexpected `SetStateStatus` from server: {response.status!r}"
            )

    async def set_task_run_state(
        self,
        task_run_id: UUID,
        state: schemas.states.State,
        force: bool = False,
        orion_doc: schemas.data.DataDocument = None,
    ) -> OrchestrationResult:
        """
        Set the state of a task run.

        Args:
            task_run_id: the id of the task run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Orion API to accept the state
            orion_doc: an optional orion data document representing the state's data,
                if provided it will override `state.data`

        Returns:
            a [OrchestrationResult model][prefect.orion.orchestration.rules.OrchestrationResult]
                representation of state orchestration output
        """
        state_data = schemas.actions.StateCreate(
            type=state.type,
            message=state.message,
            data=orion_doc or state.data,
            state_details=state.state_details,
        )
        state_data.state_details.task_run_id = task_run_id

        # Attempt to serialize the given data
        try:
            state_data_json = state_data.dict(json_compatible=True)
        except TypeError:
            # Drop the user data
            state_data.data = None
            state_data_json = state_data.dict(json_compatible=True)

        response = await self.post(
            f"/task_runs/{task_run_id}/set_state",
            json=dict(state=state_data_json, force=force),
        )
        return OrchestrationResult.parse_obj(response.json())

    async def read_task_run_states(
        self, task_run_id: UUID
    ) -> List[schemas.states.State]:
        """
        Query for the states of a task run

        Args:
            task_run_id: the id of the task run

        Returns:
            a list of [State model][prefect.orion.schemas.states.State] representation
                of the task run states
        """
        response = await self.get(
            "/task_run_states/", params=dict(task_run_id=task_run_id)
        )
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

    async def resolve_datadoc(self, datadoc: DataDocument) -> Any:
        """
        Recursively decode possibly nested data documents.

        "orion" encoded documents will be retrieved from the server.

        Args:
            datadoc: The data document to resolve

        Returns:
            a decoded object, the innermost data
        """
        if not isinstance(datadoc, DataDocument):
            raise TypeError(
                f"`resolve_datadoc` received invalid type {type(datadoc).__name__}"
            )
        result = datadoc
        while isinstance(result, DataDocument):
            if result.encoding == "orion":
                inner_doc_bytes = await self.retrieve_data(result)
                try:
                    result = DataDocument.parse_raw(inner_doc_bytes)
                except pydantic.ValidationError as exc:
                    raise ValueError(
                        "Expected `orion` encoded document to contain another data "
                        "document but it could not be parsed."
                    ) from exc
            else:
                result = result.decode()
        return result

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._client.__aexit__(*exc_info)

    def __enter__(self):
        raise RuntimeError(
            "The `OrionClient` must be entered with an async context. Use 'async "
            "with OrionClient(...)' not 'with OrionClient(...)'"
        )

    def __exit__(self, *_):
        assert False, "This should never be called but must be defined for __enter__"
