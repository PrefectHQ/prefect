"""
Asynchronous client implementation for communicating with the [Orion REST API](/api-ref/rest-api/).

Explore the client by communicating with an in-memory webserver - no setup required:

<div class="termy">
```
$ # start python REPL with native await functionality
$ python -m asyncio
>>> from prefect.client import get_client
>>> async with get_client() as client:
...     response = await client.hello()
...     print(response.json())
👋
```
</div>
"""
import datetime
import warnings
from collections import defaultdict
from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union
from uuid import UUID

import anyio
import httpx
import pydantic
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

import prefect
import prefect.exceptions
import prefect.orion.schemas as schemas
import prefect.settings
from prefect.blocks import storage
from prefect.blocks.core import Block, create_block_from_api_block
from prefect.logging import get_logger
from prefect.orion.api.server import ORION_API_VERSION, create_app
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.actions import LogCreate, WorkQueueCreate, WorkQueueUpdate
from prefect.orion.schemas.core import QueueFilter, TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.states import Scheduled
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_REQUEST_TIMEOUT,
    PREFECT_API_URL,
)
from prefect.utilities.asyncio import asyncnullcontext
from prefect.utilities.httpx import PrefectHttpxClient

if TYPE_CHECKING:
    from prefect.flow_runners import FlowRunner
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
    async def with_injected_client(*args, **kwargs):
        client = None

        if "client" in kwargs and kwargs["client"] is not None:
            client = kwargs["client"]
            client_context = asyncnullcontext()
        else:
            kwargs.pop("client", None)  # Remove null values
            client_context = get_client()

        async with client_context as client:
            kwargs.setdefault("client", client)
            return await fn(*args, **kwargs)

    return with_injected_client


def get_client() -> "OrionClient":
    profile = prefect.context.get_profile_context()

    return OrionClient(
        PREFECT_API_URL.value() or create_app(profile.settings, ephemeral=True),
        api_key=PREFECT_API_KEY.value(),
    )


APP_LIFESPANS: Dict[int, LifespanManager] = {}
APP_LIFESPANS_EXIT_EVENTS: Dict[int, List[anyio.Event]] = defaultdict(list)
APP_LIFESPANS_LOCK = anyio.Lock()  # Blocks concurrent access to the above lists


@asynccontextmanager
async def app_lifespan_context(app: FastAPI):
    """
    A context manager that calls startup/shutdown hooks for the given application.

    Lifespan contexts are cached per application to avoid calling the lifespan hooks
    more than once if the context is entered in nested code. A no-op context will be
    returned if the context for the given application is already being managed.

    This manager is robust to concurrent access within the event loop. For example,
    if you have concurrent contexts for the same application, it is guaranteed that
    startup hooks will be called before their context starts and shutdown hooks will
    only be called after their context exits.

    If you have two concurrrent contexts which are used as follows:

    --> Context A is entered (manages a new lifespan)
    -----> Context B is entered (uses the lifespan from A)
    -----> Context A exits
    -----> Context B exits

    Context A will *block* until Context B exits to avoid calling shutdown hooks before
    the context from B is complete. This means that if B depends on work that occurs
    after the exit of A, a deadlock will occur.
    """
    # TODO: We could push contexts onto a stack so the last context that exits is
    #       responsible for closing the lifespan regardless of whether or not it was the
    #       one that entered the lifespan. This would make a deadlock impossible, but
    #       consumers of the context would no longer know if they are the one that is
    #       responsible for closing the lifespan or not.

    # The id is used instead of the hash so each application instance is managed independently
    key = id(app)

    async with APP_LIFESPANS_LOCK:
        if key in APP_LIFESPANS:
            context = asyncnullcontext()
            yield_value = None
            # Create an event to indicate when this dependent exits its context
            exit_event = anyio.Event()
            APP_LIFESPANS_EXIT_EVENTS[key].append(exit_event)
        else:
            yield_value = APP_LIFESPANS[key] = context = LifespanManager(app)
            exit_event = None

    async with context:
        yield yield_value

        # If this the root context that is managing the lifespan, remove the lifespan
        # from the cache before exiting the context so the next request does not
        # get a lifespan that is shutting down.
        if yield_value is not None:
            async with APP_LIFESPANS_LOCK:
                APP_LIFESPANS.pop(key)

                # Do not exit the lifespan context until other all other contexts
                # depending on this lifespan have exited
                for exit_event in APP_LIFESPANS_EXIT_EVENTS[key]:
                    await exit_event.wait()

                APP_LIFESPANS_EXIT_EVENTS[key].clear()

    # After exiting the context, set the exit event
    if exit_event:
        exit_event.set()


class OrionClient:
    """
    An asynchronous client for interacting with the [Orion REST API](/api-ref/rest-api/).

    Args:
        api: the Orion API URL or FastAPI application to connect to
        api_key: An optional API key for authentication.
        api_version: The API version this client is compatible with.
        httpx_settings: An optional dictionary of settings to pass to the underlying
            `httpx.AsyncClient`

    Examples:

        Say hello to an Orion server

        >>> async with get_client() as client:
        >>>     response = await client.hello()
        >>>
        >>> print(response.json())
        👋
    """

    def __init__(
        self,
        api: Union[str, FastAPI],
        *,
        api_key: str = None,
        api_version: str = ORION_API_VERSION,
        httpx_settings: dict = None,
    ) -> None:
        httpx_settings = httpx_settings.copy() if httpx_settings else {}
        httpx_settings.setdefault("headers", {})
        if api_version:
            httpx_settings["headers"].setdefault("X-PREFECT-API-VERSION", api_version)
        if api_key:
            httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("timeout", PREFECT_API_REQUEST_TIMEOUT.value())

        # Context management
        self._exit_stack = AsyncExitStack()
        self._ephemeral_app: Optional[FastAPI] = None
        # Only set if this client is responsible for the lifespan of the application
        self._ephemeral_lifespan: Optional[LifespanManager] = None
        self._closed = False
        self._started = False

        # Connect to an external application
        if isinstance(api, str):
            if httpx_settings.get("app"):
                raise ValueError(
                    "Invalid httpx settings: `app` cannot be set when providing an "
                    "api url. `app` is only for use with ephemeral instances. Provide "
                    "it as the `api` parameter instead."
                )
            httpx_settings.setdefault("base_url", api)

        # Connect to an in-process application
        elif isinstance(api, FastAPI):
            self._ephemeral_app = api
            httpx_settings.setdefault("app", self._ephemeral_app)
            httpx_settings.setdefault("base_url", "http://ephemeral-orion/api")

        else:
            raise TypeError(
                f"Unexpected type {type(api).__name__!r} for argument `api`. Expected 'str' or 'FastAPI'"
            )

        self._client = PrefectHttpxClient(**httpx_settings)
        self.logger = get_logger("client")

    @property
    def api_url(self) -> httpx.URL:
        """
        Get the base URL for the API.
        """
        return self._client.base_url

    # API methods ----------------------------------------------------------------------

    async def api_healthcheck(self) -> Optional[Exception]:
        """
        Attempts to connect to the API and returns the encountered exception if not
        successful.

        If successful, returns `None`.
        """
        try:
            with anyio.fail_after(10):
                await self._client.get("/health")
                return None
        except Exception as exc:
            return exc

    async def hello(self) -> httpx.Response:
        """
        Send a GET request to /hello for testing purposes.
        """
        return await self._client.get("/admin/hello")

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
        response = await self._client.post(
            "/flows/", json=flow_data.dict(json_compatible=True)
        )

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
        response = await self._client.get(f"/flows/{flow_id}")
        return schemas.core.Flow.parse_obj(response.json())

    async def read_flows(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        limit: int = None,
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

        response = await self._client.post(f"/flows/filter", json=body)
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
        response = await self._client.get(f"/flows/name/{flow_name}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def create_flow_run_from_deployment(
        self,
        deployment_id: UUID,
        *,
        parameters: Dict[str, Any] = None,
        context: dict = None,
        state: schemas.states.State = None,
        flow_runner: "FlowRunner" = None,
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
            flow_runner: An optional flow runnner to use to execute this flow run.

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
            flow_runner=flow_runner.to_settings() if flow_runner else None,
        )

        response = await self._client.post(
            f"/deployments/{deployment_id}/create_flow_run",
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
        flow_runner: "FlowRunner" = None,
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
            flow_runner: An optional flow runnner to use to execute this flow run.

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
            flow_runner=flow_runner.to_settings() if flow_runner else None,
        )

        flow_run_create_json = flow_run_create.dict(json_compatible=True)
        response = await self._client.post("/flow_runs/", json=flow_run_create_json)
        flow_run = schemas.core.FlowRun.parse_obj(response.json())

        # Restore the parameters to the local objects to retain expectations about
        # Python objects
        flow_run.parameters = parameters

        return flow_run

    async def update_flow_run(
        self,
        flow_run_id: UUID,
        flow_version: str = None,
        parameters: dict = None,
        name: str = None,
    ) -> None:
        """
        Update a flow run's details.

        Args:
            flow_run_id: the run ID to update
            flow_version: a new version string for the flow run
            parameters: a dictionary of updated parameter values for the run
            name: a new name for the flow run

        Returns:
            an `httpx.Response` object from the PATCH request
        """
        params = {}
        if flow_version is not None:
            params["flow_version"] = flow_version
        if parameters is not None:
            params["parameters"] = parameters
        if name is not None:
            params["name"] = name

        flow_run_data = schemas.actions.FlowRunUpdate(**params)

        return await self._client.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.dict(json_compatible=True, exclude_unset=True),
        )

    async def create_concurrency_limit(
        self,
        tag: str,
        concurrency_limit: int,
    ) -> UUID:
        """
        Create a tag concurrency limit in Orion. These limits govern concurrently
        running tasks.

        Args:
            tag: a tag the concurrency limit is applied to
            concurrency_limit: the maximum number of concurrent task runs for a given tag

        Raises:
            httpx.RequestError: if the concurrency limit was not created for any reason

        Returns:
            the ID of the concurrency limit in the backend
        """

        concurrency_limit_create = schemas.actions.ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=concurrency_limit,
        )
        response = await self._client.post(
            "/concurrency_limits/",
            json=concurrency_limit_create.dict(json_compatible=True),
        )

        concurrency_limit_id = response.json().get("id")

        if not concurrency_limit_id:
            raise httpx.RequestError(f"Malformed response: {response}")

        return UUID(concurrency_limit_id)

    async def read_concurrency_limit_by_tag(
        self,
        tag: str,
    ):
        """
        Read the concurrency limit set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: if the concurrency limit was not created for any reason

        Returns:
            the concurrency limit set on a specific tag
        """
        try:
            response = await self._client.get(
                f"/concurrency_limits/tag/{tag}",
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

        concurrency_limit_id = response.json().get("id")

        if not concurrency_limit_id:
            raise httpx.RequestError(f"Malformed response: {response}")

        concurrency_limit = schemas.core.ConcurrencyLimit.parse_obj(response.json())
        return concurrency_limit

    async def read_concurrency_limits(
        self,
        limit: int,
        offset: int,
    ):
        """
        Lists concurrency limits set on task run tags.

        Args:
            limit: the maximum number of concurrency limits returned
            offset: the concurrency limit query offset

        Returns:
            a list of concurrency limits
        """

        body = {
            "limit": limit,
            "offset": offset,
        }

        response = await self._client.post("/concurrency_limits/filter", json=body)
        return pydantic.parse_obj_as(
            List[schemas.core.ConcurrencyLimit], response.json()
        )

    async def delete_concurrency_limit_by_tag(
        self,
        tag: str,
    ):
        """
        Delete the concurrency limit set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        """
        try:
            await self._client.delete(
                f"/concurrency_limits/tag/{tag}",
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def create_work_queue(
        self,
        name: str,
        tags: List[str] = None,
        deployment_ids: List[UUID] = None,
        flow_runner_types: List[str] = None,
    ) -> UUID:
        """
        Create a work queue.

        Args:
            name: a unique name for the work queue
            tags: an optional list of tags to filter on; only work scheduled with these tags
                will be included in the queue
            deployment_ids: an optional list of deployment IDs to filter on; only work scheduled from these deployments
                will be included in the queue
            flow_runner_types: an optional list of FlowRunner types to filter on; only work scheduled with these FlowRunners
                will be included in the queue

        Raises:
            prefect.exceptions.ObjectAlreadyExists: If request returns 409
            httpx.RequestError: If request fails

        Returns:
            UUID: The UUID of the newly created workflow
        """
        data = WorkQueueCreate(
            name=name,
            filter=QueueFilter(
                tags=tags or None,
                deployment_ids=deployment_ids or None,
                flow_runner_types=flow_runner_types or None,
            ),
        ).dict(json_compatible=True)
        try:
            response = await self._client.post("/work_queues/", json=data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            else:
                raise

        work_queue_id = response.json().get("id")
        if not work_queue_id:
            raise httpx.RequestError(str(response))
        return UUID(work_queue_id)

    async def read_work_queue_by_name(self, name: str) -> schemas.core.WorkQueue:
        """
        Read a work queue by name.

        Args:
            name (str): a unique name for the work queue

        Raises:
            httpx.StatusError: if no work queue is found

        Returns:
            schemas.core.WorkQueue: a work queue API object
        """
        response = await self._client.get(f"/work_queues/name/{name}")
        return schemas.core.WorkQueue.parse_obj(response.json())

    async def update_work_queue(self, id: UUID, **kwargs):
        """
        Update properties of a work queue.

        Args:
            id: the ID of the work queue to update
            **kwargs: the fields to update

        Raises:
            ValueError: if no kwargs are provided
            prefect.exceptions.ObjectNotFound: if request returns 404
            httpx.RequestError: if the request fails

        """
        if not kwargs:
            raise ValueError("No fields provided to update.")

        data = WorkQueueUpdate(**kwargs).dict(json_compatible=True, exclude_unset=True)
        try:
            await self._client.patch(f"/work_queues/{id}", json=data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def get_runs_in_work_queue(
        self,
        id: UUID,
        limit: int = 10,
        scheduled_before: datetime.datetime = None,
    ) -> List[schemas.core.FlowRun]:
        """
        Read flow runs off a work queue.

        Args:
            id: the id of the work queue to read from
            limit: a limit on the number of runs to return
            scheduled_before: a timestamp; only runs scheduled before this time will be returned.
                Defaults to now.

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            List[schemas.core.FlowRun]: a list of FlowRun objects read from the queue
        """
        json_data = {"limit": limit}
        if scheduled_before:
            json_data.update({"scheduled_before": scheduled_before.isoformat()})

        try:
            response = await self._client.post(
                f"/work_queues/{id}/get_runs",
                json=json_data,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return pydantic.parse_obj_as(List[schemas.core.FlowRun], response.json())

    async def read_work_queue(
        self,
        id: UUID,
    ) -> schemas.core.WorkQueue:
        """
        Read a work queue.

        Args:
            id: the id of the work queue to load

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            WorkQueue: an instantiated WorkQueue object
        """
        try:
            response = await self._client.get(f"/work_queues/{id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return schemas.core.WorkQueue.parse_obj(response.json())

    async def read_work_queues(
        self,
        limit: int = None,
        offset: int = 0,
    ) -> List[schemas.core.WorkQueue]:
        """
        Query Orion for work queues.

        Args:
            limit: a limit for the query
            offset: an offset for the query

        Returns:
            a list of [WorkQueue model][prefect.orion.schemas.core.WorkQueue] representations
                of the work queues
        """
        body = {
            "limit": limit,
            "offset": offset,
        }
        response = await self._client.post(f"/work_queues/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.WorkQueue], response.json())

    async def delete_work_queue_by_id(
        self,
        id: UUID,
    ):
        """
        Delete a work queue by its ID.

        Args:
            id: the id of the work queue to delete

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """
        try:
            await self._client.delete(
                f"/work_queues/{id}",
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def create_block(
        self,
        block: prefect.blocks.core.Block,
        block_spec_id: UUID = None,
        name: str = None,
    ) -> Optional[UUID]:
        """
        Create a block in Orion. This data is used to configure a corresponding
        Block.
        """

        api_block = block.to_api_block(name=name, block_spec_id=block_spec_id)

        # Drop fields that are not compliant with `CreateBlock`
        payload = api_block.dict(
            json_compatible=True, exclude={"block_spec", "id"}, exclude_unset=True
        )

        try:
            response = await self._client.post(
                "/blocks/",
                json=payload,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        return UUID(response.json().get("id"))

    async def read_block_specs(self, type: str) -> List[schemas.core.BlockSpec]:
        """
        Read all block specs with the given type

        Args:
            type: The name of the type of block spec

        Raises:
            httpx.RequestError: if the block was not found for any reason

        Returns:
            A hydrated block or None.
        """
        response = await self._client.post(
            f"/block_specs/filter", json={"block_spec_type": type}
        )
        return pydantic.parse_obj_as(List[schemas.core.BlockSpec], response.json())

    async def read_block(self, block_id: UUID):
        """
        Read the block with the specified name that corresponds to a
        specific block spec name and version.

        Args:
            block_id (UUID): the block id

        Raises:
            httpx.RequestError: if the block was not found for any reason

        Returns:
            A hydrated block or None.
        """
        response = await self._client.get(f"/blocks/{block_id}")
        return create_block_from_api_block(response.json())

    async def read_block_by_name(
        self,
        name: str,
        block_spec_name: str,
        block_spec_version: str,
    ):
        """
        Read the block with the specified name that corresponds to a
        specific block spec name and version.

        Args:
            name (str): The block name.
            block_spec_name (str): the block spec name
            block_spec_version (str): the block spec version. If not provided,
                the most recent matching version will be returned.

        Raises:
            httpx.RequestError: if the block was not found for any reason

        Returns:
            A hydrated block or None.
        """
        response = await self._client.get(
            f"/block_specs/{block_spec_name}/versions/{block_spec_version}/block/{name}",
        )
        return create_block_from_api_block(response.json())

    async def read_blocks(
        self,
        block_spec_type: str = None,
        offset: int = None,
        limit: int = None,
        as_json: bool = False,
    ) -> List[Union[prefect.blocks.core.Block, Dict[str, Any]]]:
        """
        Read blocks

        Args:
            block_spec_type (str): an optional block spec type
            offset (int): an offset
            limit (int): the number of blocks to return
            as_json (bool): if False, fully hydrated Blocks are loaded. Otherwise,
                JSON is returned from the API.

        Returns:
            A list of blocks
        """
        response = await self._client.post(
            f"/blocks/filter",
            json=dict(block_spec_type=block_spec_type, offset=offset, limit=limit),
        )
        json_result = response.json()
        if as_json:
            return json_result
        return [create_block_from_api_block(b) for b in json_result]

    async def create_deployment(
        self,
        flow_id: UUID,
        name: str,
        flow_data: DataDocument,
        schedule: schemas.schedules.SCHEDULE_TYPES = None,
        parameters: Dict[str, Any] = None,
        tags: List[str] = None,
        flow_runner: "FlowRunner" = None,
    ) -> UUID:
        """
        Create a flow deployment in Orion.

        Args:
            flow_id: the flow ID to create a deployment for
            name: the name of the deployment
            flow_data: a data document that can be resolved into a flow object or script
            schedule: an optional schedule to apply to the deployment
            tags: an optional list of tags to apply to the deployment
            flow_runner: an optional flow runner to specify for this deployment

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
            flow_runner=flow_runner.to_settings() if flow_runner else None,
        )

        response = await self._client.post(
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
        response = await self._client.get(f"/deployments/{deployment_id}")
        return schemas.core.Deployment.parse_obj(response.json())

    async def read_deployment_by_name(
        self,
        name: str,
    ) -> schemas.core.Deployment:
        """
        Query Orion for a deployment by name.

        Args:
            name: the deployment name of interest

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            a [Deployment model][prefect.orion.schemas.core.Deployment] representation of the deployment
        """
        try:
            response = await self._client.get(f"/deployments/name/{name}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

        return schemas.core.Deployment.parse_obj(response.json())

    async def read_deployments(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        limit: int = None,
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
        response = await self._client.post(f"/deployments/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.Deployment], response.json())

    async def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        """
        Query Orion for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a [Flow Run model][prefect.orion.schemas.core.FlowRun] representation of the flow run
        """
        response = await self._client.get(f"/flow_runs/{flow_run_id}")
        return schemas.core.FlowRun.parse_obj(response.json())

    async def read_flow_runs(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        sort: schemas.sorting.FlowRunSort = None,
        limit: int = None,
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

        response = await self._client.post(f"/flow_runs/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.FlowRun], response.json())

    async def get_default_storage_block(
        self, as_json: bool = False
    ) -> Optional[Union[Block, Dict[str, Any]]]:
        """Returns the default storage block

        Args:
            as_json (bool, optional): if True, the raw JSON from the API is
                returned. This can avoid instantiating a storage block (and any side
                effects) Defaults to False.

        Returns:
            Optional[Block]:
        """
        response = await self._client.post("/blocks/get_default_storage_block")
        if not response.content:
            return None
        if as_json:
            return response.json()
        return create_block_from_api_block(response.json())

    async def set_default_storage_block(self, block_id: UUID):
        try:
            await self._client.post(f"/blocks/{block_id}/set_default_storage_block")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def clear_default_storage_block(self):
        await self._client.post(f"/blocks/clear_default_storage_block")

    async def persist_data(
        self,
        data: bytes,
    ) -> DataDocument:
        """
        Persist data in orion and return the orion data document

        Args:
            data: the data to persist

        Returns:
            Orion data document pointing to persisted data.
        """
        block = await self.get_default_storage_block()
        if not block:
            warnings.warn(
                "No default storage has been set on the server. "
                "Using temporary local storage for results."
            )
            block = storage.TempStorageBlock()
        storage_token = await block.write(data)
        storage_datadoc = DataDocument.encode(
            encoding="blockstorage",
            data={"data": storage_token, "block_id": block._block_id},
        )
        return storage_datadoc

    async def retrieve_data(
        self,
        data_document: DataDocument,
    ) -> bytes:
        """
        Exchange a storage data document for the data previously persisted.

        Args:
            data_document: The data document used to store data.

        Returns:
            The persisted data in bytes.
        """
        block_document = data_document.decode()
        embedded_datadoc = block_document["data"]
        block_id = block_document["block_id"]
        if block_id is not None:
            storage_block = await self.read_block(block_id)
        else:
            storage_block = storage.TempStorageBlock()
        return await storage_block.read(embedded_datadoc)

    async def persist_object(
        self, obj: Any, encoder: str = "cloudpickle"
    ) -> DataDocument:
        """
        Persist an object in orion and return the orion data document

        Args:
            obj: the object to persist
            encoder: An optional encoder for the data document.

        Returns:
            Data document pointing to persisted data.
        """
        datadoc = DataDocument.encode(encoding=encoder, data=obj)
        return await self.persist_data(datadoc.json().encode())

    async def retrieve_object(self, storage_datadoc: DataDocument) -> Any:
        """
        Exchange a data document for the object previously persisted.

        Args:
            storage_datadoc: The storage data document to retrieve.

        Returns:
            the persisted object
        """
        datadoc = DataDocument.parse_raw(await self.retrieve_data(storage_datadoc))
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

        response = await self._client.post(
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
        response = await self._client.get(
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

        response = await self._client.post(
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
        response = await self._client.get(f"/task_runs/{task_run_id}")
        return schemas.core.TaskRun.parse_obj(response.json())

    async def read_task_runs(
        self,
        *,
        flow_filter: schemas.filters.FlowFilter = None,
        flow_run_filter: schemas.filters.FlowRunFilter = None,
        task_run_filter: schemas.filters.TaskRunFilter = None,
        deployment_filter: schemas.filters.DeploymentFilter = None,
        sort: schemas.sorting.TaskRunSort = None,
        limit: int = None,
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
        response = await self._client.post(f"/task_runs/filter", json=body)
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
            raise prefect.exceptions.Abort(response.details.reason)

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
                if server_state.data.encoding == "blockstorage":
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
            name=state.name,
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

        response = await self._client.post(
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
        response = await self._client.get(
            "/task_run_states/", params=dict(task_run_id=task_run_id)
        )
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

    async def create_logs(self, logs: Iterable[Union[LogCreate, dict]]) -> None:
        """
        Create logs for a flow or task run

        Args:
            logs: An iterable of `LogCreate` objects or already json-compatible dicts
        """
        serialized_logs = [
            log.dict(json_compatible=True) if isinstance(log, LogCreate) else log
            for log in logs
        ]
        await self._client.post(f"/logs/", json=serialized_logs)

    async def read_logs(
        self, log_filter: LogFilter = None, limit: int = None, offset: int = None
    ) -> None:
        """
        Read flow and task run logs.
        """
        body = {
            "filter": log_filter.dict(json_compatible=True) if log_filter else None,
            "limit": limit,
            "offset": offset,
        }

        response = await self._client.post(f"/logs/filter", json=body)
        return pydantic.parse_obj_as(List[schemas.core.Log], response.json())

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

        async def resolve_inner(data):
            if isinstance(data, bytes):
                try:
                    data = DataDocument.parse_raw(data)
                except pydantic.ValidationError:
                    return data

            if isinstance(data, DataDocument):
                if data.encoding == "blockstorage":
                    data = await self.retrieve_data(data)
                else:
                    data = data.decode()
                return await resolve_inner(data)

            return data

        return await resolve_inner(datadoc)

    async def __aenter__(self):
        """
        Start the client.

        If the client is already started, entering and exiting this context will have
        no effect.

        If the client is already closed, this will raise an exception. Use a new client
        instance instead.
        """
        if self._closed:
            # httpx.AsyncClient does not allow reuse so we will not either.
            raise RuntimeError(
                "The client cannot be started again after closing. "
                "Retrieve a new client with `get_client()` instead."
            )

        if self._started:
            # httpx.AsyncClient does not allow reentrancy so we will not either.
            raise RuntimeError("The client cannot be started more than once.")

        await self._exit_stack.__aenter__()

        # Enter a lifespan context if using an ephemeral application.
        # See https://github.com/encode/httpx/issues/350
        if self._ephemeral_app:
            self._ephemeral_lifespan = await self._exit_stack.enter_async_context(
                app_lifespan_context(self._ephemeral_app)
            )

        # Enter the httpx client's context
        await self._exit_stack.enter_async_context(self._client)

        self._started = True

        return self

    async def __aexit__(self, *exc_info):
        """
        Shutdown the client.

        If the client has been started multiple times, this will have no effect until
        all of the contexts have been exited.
        """
        self._closed = True
        return await self._exit_stack.aclose()

    def __enter__(self):
        raise RuntimeError(
            "The `OrionClient` must be entered with an async context. Use 'async "
            "with OrionClient(...)' not 'with OrionClient(...)'"
        )

    def __exit__(self, *_):
        assert False, "This should never be called but must be defined for __enter__"
