from typing import TYPE_CHECKING, Any, Dict, Iterable, List
from uuid import UUID
from functools import wraps

import pydantic
import httpx

import prefect
from prefect.orion import schemas
from prefect.orion.schemas.data import DataDocument
from prefect.orion.api.server import app as orion_app

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task


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
        response = await self._client.post(route, **kwargs)
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    async def get(self, route: str, **kwargs) -> httpx.Response:
        response = await self._client.get(route, **kwargs)
        response.raise_for_status()
        return response

    # API methods ----------------------------------------------------------------------

    async def hello(self) -> httpx.Response:
        return await self.post("/hello")

    async def create_flow(self, flow: "Flow") -> UUID:
        flow_data = schemas.actions.FlowCreate(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = await self.post("/flows/", json=flow_data.dict(json_compatible=True))

        flow_id = response.json().get("id")
        if not flow_id:
            raise Exception(f"Malformed response: {response}")

        # Return the id of the created flow
        return UUID(flow_id)

    async def read_flow(self, flow_id: UUID) -> schemas.core.Flow:
        response = await self.get(f"/flows/{flow_id}")
        return schemas.core.Flow.parse_obj(response.json())

    async def create_flow_run(
        self,
        flow: "Flow",
        parameters: Dict[str, Any] = None,
        context: dict = None,
        extra_tags: Iterable[str] = None,
        parent_task_run_id: UUID = None,
        state: schemas.states.State = None,
    ) -> UUID:
        tags = set(flow.tags).union(extra_tags or [])
        parameters = parameters or {}
        context = context or {}

        # Retrieve the flow id
        flow_id = await self.create_flow(flow)

        flow_run_data = schemas.actions.FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            parameters=parameters,
            context=context,
            tags=list(tags),
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

    async def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        response = await self.get(f"/flow_runs/{flow_run_id}")
        return schemas.core.FlowRun.parse_obj(response.json())

    async def persist_data(
        self,
        data: bytes,
    ) -> DataDocument:
        response = await self.post("/data/persist", content=data)
        return DataDocument.parse_obj(response.json())

    async def retrieve_data(
        self,
        orion_datadoc: DataDocument,
    ) -> bytes:
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
    ) -> schemas.responses.SetStateResponse:
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
            json=state_data_json,
        )
        return schemas.responses.SetStateResponse.parse_obj(response.json())

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

    async def set_task_run_state(
        self,
        task_run_id: UUID,
        state: schemas.states.State,
    ) -> schemas.responses.SetStateResponse:
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
            json=state_data_json,
        )
        return schemas.responses.SetStateResponse.parse_obj(response.json())

    async def read_task_run_states(
        self, task_run_id: UUID
    ) -> List[schemas.states.State]:
        response = await self.get(
            "/task_run_states/", params=dict(task_run_id=task_run_id)
        )
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._client.__aexit__(*exc_info)

    def __enter__(self):
        raise RuntimeError(
            "The Orion client is only usable from an async context and must be entered "
            "with 'async with ...'"
        )
