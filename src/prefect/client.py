"""
Client implementation for communicating with the Orion Server.
"""
from functools import wraps
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple, Union
from uuid import UUID

import anyio
import httpx
import httpx._types as httpx_types
import pydantic

import prefect
from prefect import exceptions
from prefect.orion import schemas
from prefect.orion.api.server import app as orion_app
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Scheduled
from prefect.utilities.settings import NOTSET, NotSetType, drop_unset

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task

UseHttpxDefault = NotSetType
USE_HTTPX_DEFAULT = NOTSET

NoUpdate = NotSetType
NO_UPDATE = NOTSET


def inject_client(fn):
    """
    Simple helper to provide a context managed client to a function

    The decorated function _must_ take a `client` kwarg and if a client is passed when
    called it will be used instead of creating a new one, but it will not be context
    managed as it is assumed that the caller is managing the context.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if "client" in kwargs:
            return await fn(*args, **kwargs)
        else:
            client = OrionClient()
            async with client:
                return await fn(*args, client=client, **kwargs)

    return wrapper


class OrionClient:
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
            httpx_settings.setdefault("base_url", "http://orion")

        self._client = httpx.AsyncClient(**httpx_settings)

    async def post(self, route: str, **kwargs) -> httpx.Response:
        # TODO: This function (and other httpx mirrors) should replicate the types like
        #       `OrionClient.get` for usability
        response = await self._client.post(route, **kwargs)
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    async def patch(self, route: str, **kwargs) -> httpx.Response:
        response = await self._client.patch(route, **kwargs)
        response.raise_for_status()
        return response

    async def get(
        self,
        route: httpx_types.URLTypes,
        *,
        params: Union[httpx_types.QueryParamTypes, UseHttpxDefault] = USE_HTTPX_DEFAULT,
        headers: Union[httpx_types.HeaderTypes, UseHttpxDefault] = USE_HTTPX_DEFAULT,
        cookies: Union[httpx_types.CookieTypes, UseHttpxDefault] = USE_HTTPX_DEFAULT,
        auth: Union[httpx_types.AuthTypes, UseHttpxDefault] = USE_HTTPX_DEFAULT,
        allow_redirects: Union[bool, UseHttpxDefault] = USE_HTTPX_DEFAULT,
        timeout: Union[httpx_types.TimeoutTypes, UseHttpxDefault] = USE_HTTPX_DEFAULT,
    ) -> httpx.Response:
        """
        Send a `GET` request

        Extends `httpx.AsyncClient.get` to accept JSON bodies

        **Parameters**: See `httpx.request`.
        """
        response = await self._client.get(
            route,
            **drop_unset(
                params=params,
                headers=headers,
                cookies=cookies,
                auth=auth,
                allow_redirects=allow_redirects,
                timeout=timeout,
            ),
        )
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    # API methods ----------------------------------------------------------------------

    async def hello(self) -> httpx.Response:
        return await self.get("/hello")

    async def create_flow(self, flow: "Flow") -> UUID:
        flow_data = schemas.actions.FlowCreate(name=flow.name)
        response = await self.post("/flows/", json=flow_data.dict(json_compatible=True))

        flow_id = response.json().get("id")
        if not flow_id:
            raise Exception(f"Malformed response: {response}")

        # Return the id of the created flow
        return UUID(flow_id)

    async def read_flow(self, flow_id: UUID) -> schemas.core.Flow:
        response = await self.get(f"/flows/{flow_id}")
        return schemas.core.Flow.parse_obj(response.json())

    async def read_flows(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
    ) -> List[schemas.core.Flow]:
        body = {}
        if flow_filter:
            body["flows"] = flow_filter.dict(json_compatible=True)

        response = await self.post(f"/flows/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.Flow], response.json())

    async def read_flow_by_name(
        self,
        flow_name: str,
    ) -> schemas.core.Flow:
        response = await self.get(f"/flows/name/{flow_name}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def create_flow_run_from_deployment(
        self,
        deployment: schemas.core.Deployment,
        *,
        parameters: Dict[str, Any] = None,
        context: dict = None,
        state: schemas.states.State = None,
    ) -> UUID:
        """
        Create a flow run for a deployment

        Args:
            - deployment: The deployment model to create the flow run from
            - parameters: Parameter overrides for this flow run. Merged with the
                deployment defaults
            - context: Optional run context data
            - state: The initial state for the run. If not provided, defaults to
                `Scheduled` for now. Should always be a `Scheduled` type.

        Returns:
            - UUID: The flow run id
        """
        parameters = parameters or {}
        context = context or {}
        state = state or Scheduled()

        flow_run_data = schemas.actions.FlowRunCreate(
            flow_id=deployment.flow_id,
            deployment_id=deployment.id,
            flow_version=None,  # Not yet determined
            parameters=parameters,
            context=context,
            state=state,
        )

        response = await self.post(
            "/flow_runs/", json=flow_run_data.dict(json_compatible=True)
        )
        flow_run_id = response.json().get("id")
        if not flow_run_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(flow_run_id)

    async def create_flow_run(
        self,
        flow: "Flow",
        parameters: Dict[str, Any] = None,
        context: dict = None,
        tags: Iterable[str] = None,
        parent_task_run_id: UUID = None,
        state: schemas.states.State = None,
    ) -> UUID:
        parameters = parameters or {}
        context = context or {}

        if state is None:
            state = schemas.states.Pending()

        # Retrieve the flow id
        flow_id = await self.create_flow(flow)

        flow_run_data = schemas.actions.FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            parameters=parameters,
            context=context,
            tags=list(tags or []),
            parent_task_run_id=parent_task_run_id,
            state=state,
        )

        response = await self.post(
            "/flow_runs/", json=flow_run_data.dict(json_compatible=True)
        )
        flow_run_id = response.json().get("id")
        if not flow_run_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(flow_run_id)

    async def update_flow_run(
        self,
        flow_run_id: UUID,
        flow_version: Union[str, NoUpdate] = NO_UPDATE,
        parameters: Union[Dict[str, Any], NoUpdate] = NO_UPDATE,
    ) -> None:

        flow_run_data = schemas.actions.FlowRunUpdate(
            **drop_unset(flow_version=flow_version, parameters=parameters)
        )

        await self.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.dict(json_compatible=True, exclude_unset=True),
        )

    async def create_deployment(
        self,
        flow_id: UUID,
        name: str,
        flow_data: DataDocument,
        schedule: schemas.schedules.SCHEDULE_TYPES = None,
        tags: List[str] = None,
    ) -> UUID:
        deployment_create = schemas.actions.DeploymentCreate(
            flow_id=flow_id,
            name=name,
            schedule=schedule,
            flow_data=flow_data,
            tags=list(tags or []),
        )

        response = await self.post(
            "/deployments/", json=deployment_create.dict(json_compatible=True)
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(deployment_id)

    async def read_deployment(
        self,
        deployment_id: UUID,
    ) -> schemas.core.Deployment:
        response = await self.get(f"/deployments/{deployment_id}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def read_deployment_by_name(
        self,
        name: str,
    ) -> schemas.core.Deployment:
        response = await self.get(f"/deployments/name/{name}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def read_deployments(self) -> schemas.core.Deployment:
        response = await self.post(f"/deployments/filter")
        return pydantic.parse_obj_as(List[schemas.core.Deployment], response.json())

    async def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        response = await self.get(f"/flow_runs/{flow_run_id}")
        return schemas.core.FlowRun.parse_obj(response.json())

    async def read_flow_runs(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
    ) -> List[schemas.core.FlowRun]:
        body = {}
        if flow_filter:
            body["flows"] = flow_filter.dict(json_compatible=True)
        if flow_run_filter:
            body["flow_runs"] = flow_run_filter.dict(json_compatible=True)
        if task_run_filter:
            body["task_runs"] = task_run_filter.dict(json_compatible=True)

        response = await self.post(f"/flow_runs/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.FlowRun], response.json())

    async def persist_data(
        self,
        data: bytes,
    ) -> DataDocument:
        response = await self.post("/data/persist", content=data)
        orion_doc = DataDocument.parse_obj(response.json())
        orion_doc._cache_data(data)
        return orion_doc

    async def retrieve_data(
        self,
        orion_datadoc: DataDocument,
    ) -> bytes:
        if orion_datadoc.has_cached_data():
            return orion_datadoc.decode()

        response = await self.post(
            "/data/retrieve", json=orion_datadoc.dict(json_compatible=True)
        )
        return response.content

    async def persist_object(self, obj: Any, encoder: str = "cloudpickle"):
        datadoc = DataDocument.encode(encoding=encoder, data=obj)
        return await self.persist_data(datadoc.json().encode())

    async def retrieve_object(self, orion_datadoc: DataDocument) -> Any:
        datadoc = DataDocument.parse_raw(await self.retrieve_data(orion_datadoc))
        return datadoc.decode()

    async def set_flow_run_state(
        self,
        flow_run_id: UUID,
        state: schemas.states.State,
        force: bool = False,
    ) -> OrchestrationResult:
        state_data = schemas.actions.StateCreate(
            type=state.type,
            message=state.message,
            data=state.data,
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
        response = await self.get(
            "/flow_run_states/", params=dict(flow_run_id=flow_run_id)
        )
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

    async def create_task_run(
        self,
        task: "Task",
        flow_run_id: UUID,
        extra_tags: Iterable[str] = None,
        state: schemas.states.State = None,
    ) -> UUID:
        tags = set(task.tags).union(extra_tags or [])

        if state is None:
            state = schemas.states.Pending()

        task_run_data = schemas.actions.TaskRunCreate(
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=task.dynamic_key,
            tags=list(tags),
            empirical_policy=schemas.core.TaskRunPolicy(
                max_retries=task.retries,
                retry_delay_seconds=task.retry_delay_seconds,
            ),
            state=state,
        )

        response = await self.post(
            "/task_runs/", json=task_run_data.dict(json_compatible=True)
        )
        task_run_id = response.json().get("id")
        if not task_run_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(task_run_id)

    async def read_task_run(self, task_run_id: UUID) -> schemas.core.TaskRun:
        response = await self.get(f"/task_runs/{task_run_id}")
        return schemas.core.TaskRun.parse_obj(response.json())

    async def propose_state(
        self,
        state: schemas.states.State,
        task_run_id: UUID = None,
        flow_run_id: UUID = None,
    ) -> schemas.states.State:

        # Determine if working with a task run or flow run
        if not task_run_id and not flow_run_id:
            raise ValueError("You must provide either a `task_run_id` or `flow_run_id`")

        # Exchange the user data document for an orion data document
        if state.data:
            state.data = await self.persist_data(state.data.json().encode())

        # Attempt to set the state
        if task_run_id:
            response = await self.set_task_run_state(task_run_id, state)
        elif flow_run_id:
            response = await self.set_flow_run_state(flow_run_id, state)
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
            print(
                f"Received wait instruction for {response.details.delay_seconds}s: "
                f"{response.details.reason}"
            )
            await anyio.sleep(response.details.delay_seconds)
            return await self.propose_state(
                state, task_run_id=task_run_id, flow_run_id=flow_run_id
            )

        elif response.status == schemas.responses.SetStateStatus.REJECT:
            server_state = response.state

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
    ) -> OrchestrationResult:
        state_data = schemas.actions.StateCreate(
            type=state.type,
            message=state.message,
            data=state.data,
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
        response = await self.get(
            "/task_run_states", params=dict(task_run_id=task_run_id)
        )
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

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
