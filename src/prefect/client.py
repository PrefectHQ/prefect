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
import copy
import datetime
import sys
import threading
import warnings
from collections import defaultdict
from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    ContextManager,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)
from uuid import UUID

import anyio
import httpx
import pendulum
import pydantic
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from httpx import HTTPStatusError, Response
from typing_extensions import Self

import prefect
import prefect.exceptions
import prefect.orion.schemas as schemas
import prefect.settings
from prefect.exceptions import PrefectHTTPStatusError
from prefect.logging import get_logger
from prefect.orion.api.server import ORION_API_VERSION, create_app
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.actions import LogCreate, WorkQueueCreate, WorkQueueUpdate
from prefect.orion.schemas.core import (
    BlockDocument,
    BlockSchema,
    BlockType,
    QueueFilter,
    TaskRun,
)
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.filters import LogFilter
from prefect.orion.schemas.states import Scheduled
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_REQUEST_TIMEOUT,
    PREFECT_API_URL,
    PREFECT_ORION_DATABASE_CONNECTION_URL,
)
from prefect.utilities.asyncutils import asyncnullcontext

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


def get_client(httpx_settings: dict = None) -> "OrionClient":
    ctx = prefect.context.get_settings_context()
    return OrionClient(
        PREFECT_API_URL.value() or create_app(ctx.settings, ephemeral=True),
        api_key=PREFECT_API_KEY.value(),
        httpx_settings=httpx_settings,
    )


# Datastores for lifespan management, keys should be a tuple of thread and app identities.
APP_LIFESPANS: Dict[Tuple[int, int], LifespanManager] = {}
APP_LIFESPANS_REF_COUNTS: Dict[Tuple[int, int], int] = {}
# Blocks concurrent access to the above dicts per thread. The index should be the thread identity.
APP_LIFESPANS_LOCKS: Dict[int, anyio.Lock] = defaultdict(anyio.Lock)


@asynccontextmanager
async def app_lifespan_context(app: FastAPI) -> ContextManager[None]:
    """
    A context manager that calls startup/shutdown hooks for the given application.

    Lifespan contexts are cached per application to avoid calling the lifespan hooks
    more than once if the context is entered in nested code. A no-op context will be
    returned if the context for the given application is already being managed.

    This manager is robust to concurrent access within the event loop. For example,
    if you have concurrent contexts for the same application, it is guaranteed that
    startup hooks will be called before their context starts and shutdown hooks will
    only be called after their context exits.

    A reference count is used to support nested use of clients without running
    lifespan hooks excessively. The first client context entered will create and enter
    a lifespan context. Each subsequent client will increment a reference count but will
    not create a new lifespan context. When each client context exits, the reference
    count is decremented. When the last client context exits, the lifespan will be
    closed.

    In simple nested cases, the first client context will be the one to exit the
    lifespan. However, if client contexts are entered concurrently they may not exit
    in a consistent order. If the first client context was responsible for closing
    the lifespan, it would have to wait until all other client contexts to exit to
    avoid firing shutdown hooks while the application is in use. Waiting for the other
    clients to exit can introduce deadlocks, so, instead, the first client will exit
    without closing the lifespan context and reference counts will be used to ensure
    the lifespan is closed once all of the clients are done.
    """
    # TODO: A deadlock has been observed during multithreaded use of clients while this
    #       lifespan context is being used. This has only been reproduced on Python 3.7
    #       and while we hope to discourage using multiple event loops in threads, this
    #       bug may emerge again.
    #       See https://github.com/PrefectHQ/orion/pull/1696
    thread_id = threading.get_ident()

    # The id of the application is used instead of the hash so each application instance
    # is managed independently even if they share the same settings. We include the
    # thread id since applications are managed separately per thread.
    key = (thread_id, id(app))

    # On exception, this will be populated with exception details
    exc_info = (None, None, None)

    # Get a lock unique to this thread since anyio locks are not threadsafe
    lock = APP_LIFESPANS_LOCKS[thread_id]

    async with lock:
        if key in APP_LIFESPANS:
            # The lifespan is already being managed, just increment the reference count
            APP_LIFESPANS_REF_COUNTS[key] += 1
        else:
            # Create a new lifespan manager
            APP_LIFESPANS[key] = context = LifespanManager(
                app, startup_timeout=30, shutdown_timeout=30
            )
            APP_LIFESPANS_REF_COUNTS[key] = 1

            # Ensure we enter the context before releasing the lock so startup hooks
            # are complete before another client can be used
            await context.__aenter__()

    try:
        yield
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        # If we do not shield against anyio cancellation, the lock will return
        # immediately and the code in its context will not run, leaving the lifespan
        # open
        with anyio.CancelScope(shield=True):
            async with lock:
                # After the consumer exits the context, decrement the reference count
                APP_LIFESPANS_REF_COUNTS[key] -= 1

                # If this the last context to exit, close the lifespan
                if APP_LIFESPANS_REF_COUNTS[key] <= 0:
                    APP_LIFESPANS_REF_COUNTS.pop(key)
                    context = APP_LIFESPANS.pop(key)
                    await context.__aexit__(*exc_info)


class PrefectResponse(httpx.Response):
    """
    A Prefect wrapper for the `httpx.Response` class.

    Provides more informative error messages.
    """

    def raise_for_status(self) -> None:
        """
        Raise an exception if the response contains an HTTPStatusError.

        The `PrefectHTTPStatusError` contains useful additional information that
        is not contained in the `HTTPStatusError`.
        """
        try:
            return super().raise_for_status()
        except HTTPStatusError as exc:
            raise PrefectHTTPStatusError.from_httpx_error(exc) from exc.__cause__

    @classmethod
    def from_httpx_response(cls: Type[Self], response: httpx.Response) -> Self:
        """
        Create a `PrefectReponse` from an `httpx.Response`.

        By changing the `__class__` attribute of the Response, we change the method
        resolution order to look for methods defined in PrefectResponse, while leaving
        everything else about the original Response instance intact.
        """
        new_response = copy.copy(response)
        new_response.__class__ = cls
        return new_response


class PrefectHttpxClient(httpx.AsyncClient):
    """
    A Prefect wrapper for the async httpx client with support for CloudFlare-style
    rate limiting.

    Additionally, this client will always call `raise_for_status` on responses.

    For more details on rate limit headers, see:
    - https://support.cloudflare.com/hc/en-us/articles/115001635128-Configuring-Rate-Limiting-from-UI
    """

    RETRY_MAX = 5

    async def send(self, *args, **kwargs) -> Response:
        retry_count = 0
        response = PrefectResponse.from_httpx_response(
            await super().send(*args, **kwargs)
        )
        while (
            response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            and retry_count < self.RETRY_MAX
        ):
            retry_count += 1

            # Respect the "Retry-After" header, falling back to an exponential back-off
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                retry_seconds = float(retry_after)
            else:
                retry_seconds = 2**retry_count

            await anyio.sleep(retry_seconds)
            response = await super().send(*args, **kwargs)

        # Always raise bad responses
        # NOTE: We may want to remove this and handle responses per route in the
        #       `OrionClient`

        response.raise_for_status()

        return response


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
        self.manage_lifespan = True

        # Only set if this client started the lifespan of the application
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

        self._client = PrefectHttpxClient(
            **httpx_settings,
        )
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
        return await self._client.get("/hello")

    async def using_ephemeral_app(self) -> bool:
        return self._ephemeral_app is not None

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
        return await self.create_flow_from_name(flow.name)

    async def create_flow_from_name(self, flow_name: str) -> UUID:
        """
        Create a flow in Orion.

        Args:
            flow_name: the name of the new flow

        Raises:
            httpx.RequestError: if a flow was not created for any reason

        Returns:
            the ID of the flow in the backend
        """
        flow_data = schemas.actions.FlowCreate(name=flow_name)
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
        sort: schemas.sorting.FlowSort = None,
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
            sort: sort criteria for the flows
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
            "sort": sort,
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
        return schemas.core.Flow.parse_obj(response.json())

    async def create_flow_run_from_deployment(
        self,
        deployment_id: UUID,
        *,
        parameters: Dict[str, Any] = None,
        context: dict = None,
        state: schemas.states.State = None,
        name: str = None,
        tags: Iterable[str] = None,
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
        tags = tags or []

        flow_run_create = schemas.actions.DeploymentFlowRunCreate(
            parameters=parameters,
            context=context,
            state=state,
            tags=tags,
            name=name,
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
            empirical_policy=schemas.core.FlowRunPolicy(
                retries=flow.retries,
                retry_delay=flow.retry_delay_seconds,
            ),
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
        flow_version: Optional[str] = None,
        parameters: Optional[dict] = None,
        name: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        empirical_policy: Optional[schemas.core.FlowRunPolicy] = None,
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
        if tags is not None:
            params["tags"] = tags
        if empirical_policy is not None:
            params["empirical_policy"] = empirical_policy

        flow_run_data = schemas.actions.FlowRunUpdate(**params)

        return await self._client.patch(
            f"/flow_runs/{flow_run_id}",
            json=flow_run_data.dict(json_compatible=True, exclude_unset=True),
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
            await self._client.delete(f"/flow_runs/{flow_run_id}"),
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

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
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
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
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def create_work_queue(
        self, name: str, tags: List[str] = None
    ) -> schemas.core.WorkQueue:
        """
        Create a work queue.

        Args:
            name: a unique name for the work queue
            tags: DEPRECATED: an optional list of tags to filter on; only work scheduled with these tags
                will be included in the queue

        Raises:
            prefect.exceptions.ObjectAlreadyExists: If request returns 409
            httpx.RequestError: If request fails

        Returns:
            UUID: The UUID of the newly created workflow
        """
        if tags:
            warnings.warn(
                "The use of tags for creating work queue filters is deprecated.",
                DeprecationWarning,
            )
            filter = QueueFilter(tags=tags)
        else:
            filter = None
        data = WorkQueueCreate(name=name, filter=filter).dict(json_compatible=True)
        try:
            response = await self._client.post("/work_queues/", json=data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_409_CONFLICT:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        return schemas.core.WorkQueue.parse_obj(response.json())

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
        try:
            response = await self._client.get(f"/work_queues/name/{name}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

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
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
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
        if scheduled_before is None:
            scheduled_before = pendulum.now()

        try:
            response = await self._client.post(
                f"/work_queues/{id}/get_runs",
                json={
                    "limit": limit,
                    "scheduled_before": scheduled_before.isoformat(),
                },
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
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
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
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
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def create_block_type(
        self, block_type: schemas.actions.BlockTypeCreate
    ) -> BlockType:
        """
        Create a block type in Orion.
        """
        try:
            response = await self._client.post(
                "/block_types/",
                json=block_type.dict(
                    json_compatible=True, exclude_unset=True, exclude={"id"}
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_409_CONFLICT:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        return BlockType.parse_obj(response.json())

    async def create_block_schema(
        self, block_schema: schemas.actions.BlockSchemaCreate
    ) -> BlockSchema:
        """
        Create a block schema in Orion.
        """
        try:
            response = await self._client.post(
                "/block_schemas/",
                json=block_schema.dict(
                    json_compatible=True,
                    exclude_unset=True,
                    include={"type", "block_type_id", "fields"},
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_409_CONFLICT:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        return BlockSchema.parse_obj(response.json())

    async def create_block_document(
        self,
        block_document: schemas.actions.BlockDocumentCreate,
        include_secrets: bool = True,
    ) -> BlockDocument:
        """
        Create a block document in Orion. This data is used to configure a
        corresponding Block.

        Args:
            include_secrets (bool): whether to include secret values
                on the stored Block, corresponding to Pydantic's `SecretStr` and
                `SecretBytes` fields. Note Blocks may not work as expected if
                this is set to `False`.
        """
        try:
            response = await self._client.post(
                "/block_documents/",
                json=block_document.dict(
                    json_compatible=True,
                    include_secrets=include_secrets,
                    exclude_unset=True,
                    exclude={"id", "block_schema", "block_type"},
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_409_CONFLICT:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            else:
                raise
        return BlockDocument.parse_obj(response.json())

    async def update_block_document(
        self,
        block_document_id: UUID,
        block_document: schemas.actions.BlockDocumentUpdate,
    ):
        """
        Update a block document in Orion.
        """
        try:
            await self._client.patch(
                f"/block_documents/{block_document_id}",
                json=block_document.dict(
                    json_compatible=True,
                    exclude_unset=True,
                    include={"data"},
                    include_secrets=True,
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_block_document(self, block_document_id: UUID):
        """
        Delete a block document.
        """
        try:
            await self._client.delete(f"/block_documents/{block_document_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_block_type_by_slug(self, slug: str) -> BlockType:
        """
        Read a block type by its slug.
        """
        try:
            response = await self._client.get(f"/block_types/slug/{slug}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return BlockType.parse_obj(response.json())

    async def read_block_schema_by_checksum(
        self, checksum: str
    ) -> schemas.core.BlockSchema:
        """
        Look up a block schema checksum
        """
        try:
            response = await self._client.get(f"/block_schemas/checksum/{checksum}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return schemas.core.BlockSchema.parse_obj(response.json())

    async def update_block_type(
        self, block_type_id: UUID, block_type: schemas.actions.BlockTypeUpdate
    ):
        """
        Update a block document in Orion.
        """
        try:
            await self._client.patch(
                f"/block_types/{block_type_id}",
                json=block_type.dict(
                    json_compatible=True,
                    exclude_unset=True,
                    include={
                        "logo_url",
                        "documentation_url",
                        "description",
                        "code_example",
                    },
                    include_secrets=True,
                ),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_block_type(self, block_type_id: UUID):
        """
        Delete a block type.
        """
        try:
            await self._client.delete(f"/block_types/{block_type_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_block_types(self) -> List[schemas.core.BlockType]:
        """
        Read all block types
        Raises:
            httpx.RequestError

        Returns:
            List of BlockTypes.
        """
        response = await self._client.post(f"/block_types/filter", json={})
        return pydantic.parse_obj_as(List[schemas.core.BlockType], response.json())

    async def read_block_schemas(self) -> List[schemas.core.BlockSchema]:
        """
        Read all block schemas
        Raises:
            httpx.RequestError

        Returns:
            A BlockSchema.
        """
        response = await self._client.post(f"/block_schemas/filter", json={})
        return pydantic.parse_obj_as(List[schemas.core.BlockSchema], response.json())

    async def read_block_document(
        self,
        block_document_id: UUID,
        include_secrets: bool = True,
    ):
        """
        Read the block document with the specified ID.

        Args:
            block_document_id: the block document id
            include_secrets (bool): whether to include secret values
                on the Block, corresponding to Pydantic's `SecretStr` and
                `SecretBytes` fields. These fields are automatically obfuscated
                by Pydantic, but users can additionally choose not to receive
                their values from the API. Note that any business logic on the
                Block may not work if this is `False`.

        Raises:
            httpx.RequestError: if the block document was not found for any reason

        Returns:
            A block document or None.
        """
        try:
            response = await self._client.get(
                f"/block_documents/{block_document_id}",
                params=dict(include_secrets=include_secrets),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return BlockDocument.parse_obj(response.json())

    async def read_block_document_by_name(
        self,
        name: str,
        block_type_slug: str,
        include_secrets: bool = True,
    ):
        """
        Read the block document with the specified name that corresponds to a
        specific block type name.

        Args:
            name: The block document name.
            block_type_slug: The block type slug.
            include_secrets (bool): whether to include secret values
                on the Block, corresponding to Pydantic's `SecretStr` and
                `SecretBytes` fields. These fields are automatically obfuscated
                by Pydantic, but users can additionally choose not to receive
                their values from the API. Note that any business logic on the
                Block may not work if this is `False`.

        Raises:
            httpx.RequestError: if the block document was not found for any reason

        Returns:
            A block document or None.
        """
        try:
            response = await self._client.get(
                f"/block_types/slug/{block_type_slug}/block_documents/name/{name}",
                params=dict(include_secrets=include_secrets),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return BlockDocument.parse_obj(response.json())

    async def read_block_documents(
        self,
        block_schema_type: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include_secrets: bool = True,
    ):
        """
        Read block documents

        Args:
            block_schema_type: an optional block schema type
            offset: an offset
            limit: the number of blocks to return
            include_secrets (bool): whether to include secret values
                on the Block, corresponding to Pydantic's `SecretStr` and
                `SecretBytes` fields. These fields are automatically obfuscated
                by Pydantic, but users can additionally choose not to receive
                their values from the API. Note that any business logic on the
                Block may not work if this is `False`.

        Returns:
            A list of block documents
        """
        response = await self._client.post(
            f"/block_documents/filter",
            json=dict(
                block_schema_type=block_schema_type,
                offset=offset,
                limit=limit,
                include_secrets=include_secrets,
            ),
        )
        return pydantic.parse_obj_as(List[BlockDocument], response.json())

    async def create_deployment(
        self,
        flow_id: UUID,
        name: str,
        version: str = None,
        schedule: schemas.schedules.SCHEDULE_TYPES = None,
        parameters: Dict[str, Any] = None,
        description: str = None,
        work_queue_name: str = None,
        tags: List[str] = None,
        storage_document_id: UUID = None,
        manifest_path: str = None,
        path: str = None,
        entrypoint: str = None,
        infrastructure_document_id: UUID = None,
        infra_overrides: Dict[str, Any] = None,
        parameter_openapi_schema: dict = None,
    ) -> UUID:
        """
        Create a deployment.

        Args:
            flow_id: the flow ID to create a deployment for
            name: the name of the deployment
            version: an optional version string for the deployment
            schedule: an optional schedule to apply to the deployment
            tags: an optional list of tags to apply to the deployment
            storage_document_id: an reference to the storage block document
                used for the deployed flow
            infrastructure_document_id: an reference to the infrastructure block document
                to use for this deployment

        Raises:
            httpx.RequestError: if the deployment was not created for any reason

        Returns:
            the ID of the deployment in the backend
        """
        deployment_create = schemas.actions.DeploymentCreate(
            flow_id=flow_id,
            name=name,
            version=version,
            schedule=schedule,
            parameters=dict(parameters or {}),
            tags=list(tags or []),
            work_queue_name=work_queue_name,
            description=description,
            storage_document_id=storage_document_id,
            path=path,
            entrypoint=entrypoint,
            manifest_path=manifest_path,  # for backwards compat
            infrastructure_document_id=infrastructure_document_id,
            infra_overrides=infra_overrides or {},
            parameter_openapi_schema=parameter_openapi_schema,
        )

        response = await self._client.post(
            "/deployments/", json=deployment_create.dict(json_compatible=True)
        )
        deployment_id = response.json().get("id")
        if not deployment_id:
            raise httpx.RequestError(f"Malformed response: {response}")

        return UUID(deployment_id)

    async def update_deployment(
        self,
        deployment,
        schedule: schemas.schedules.SCHEDULE_TYPES = None,
        is_schedule_active: bool = None,
    ):
        deployment_create = schemas.actions.DeploymentUpdate(
            version=deployment.version,
            schedule=schedule if schedule is not None else deployment.schedule,
            is_schedule_active=is_schedule_active
            if is_schedule_active is not None
            else deployment.is_schedule_active,
            description=deployment.description,
            work_queue_name=deployment.work_queue_name,
            tags=deployment.tags,
            manifest_path=deployment.manifest_path,
            path=deployment.path,
            entrypoint=deployment.entrypoint,
            parameters=deployment.parameters,
            storage_document_id=deployment.storage_document_id,
            infrastructure_document_id=deployment.infrastructure_document_id,
            infra_overrides=deployment.infra_overrides,
        )

        response = await self._client.patch(
            f"/deployments/{deployment.id}",
            json=deployment_create.dict(json_compatible=True),
        )

    async def _create_deployment_from_schema(
        self, schema: schemas.actions.DeploymentCreate
    ) -> UUID:
        """
        Create a deployment from a prepared `DeploymentCreate` schema.
        """
        # TODO: We are likely to remove this method once we have considered the
        #       packaging interface for deployments further.
        response = await self._client.post(
            "/deployments/", json=schema.dict(json_compatible=True)
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
            name: A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            a [Deployment model][prefect.orion.schemas.core.Deployment] representation of the deployment
        """
        try:
            response = await self._client.get(f"/deployments/name/{name}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
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

    async def delete_deployment(
        self,
        deployment_id: UUID,
    ):
        """
        Delete deployment by id.

        Args:
            deployment_id: The deployment id of interest.
        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """
        try:
            await self._client.delete(f"/deployments/{deployment_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        """
        Query Orion for a flow run by id.

        Args:
            flow_run_id: the flow run ID of interest

        Returns:
            a [Flow Run model][prefect.orion.schemas.core.FlowRun] representation of the flow run
        """
        try:
            response = await self._client.get(f"/flow_runs/{flow_run_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
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

    async def set_flow_run_state(
        self,
        flow_run_id: UUID,
        state: schemas.states.State,
        force: bool = False,
        backend_state_data: schemas.data.DataDocument = None,
    ) -> OrchestrationResult:
        """
        Set the state of a flow run.

        Args:
            flow_run_id: the id of the flow run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Orion API to accept the state
            backend_state_data: an optional data document representing the state's data,
                if provided it will override `state.data`

        Returns:
            a [OrchestrationResult model][prefect.orion.orchestration.rules.OrchestrationResult]
                representation of state orchestration output
        """
        state_data = schemas.actions.StateCreate(
            type=state.type,
            name=state.name,
            message=state.message,
            data=backend_state_data or state.data,
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
    ) -> TaskRun:
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
            The created task run.
        """
        tags = set(task.tags).union(extra_tags or [])

        if state is None:
            state = schemas.states.Pending()

        task_run_data = schemas.actions.TaskRunCreate(
            name=name,
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=dynamic_key,
            tags=list(tags),
            task_version=task.version,
            empirical_policy=schemas.core.TaskRunPolicy(
                retries=task.retries,
                retry_delay=task.retry_delay_seconds,
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

    async def set_task_run_state(
        self,
        task_run_id: UUID,
        state: schemas.states.State,
        force: bool = False,
        backend_state_data: schemas.data.DataDocument = None,
    ) -> OrchestrationResult:
        """
        Set the state of a task run.

        Args:
            task_run_id: the id of the task run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Orion API to accept the state
            backend_state_data: an optional orion data document representing the state's data,
                if provided it will override `state.data`

        Returns:
            a [OrchestrationResult model][prefect.orion.orchestration.rules.OrchestrationResult]
                representation of state orchestration output
        """
        state_data = schemas.actions.StateCreate(
            name=state.name,
            type=state.type,
            message=state.message,
            data=backend_state_data or state.data,
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
                return await resolve_inner(data.decode())

            return data

        return await resolve_inner(datadoc)

    async def __aenter__(self):
        """
        Start the client.

        If the client is already started, this will raise an exception.

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
        if self._ephemeral_app and self.manage_lifespan:
            self._ephemeral_lifespan = await self._exit_stack.enter_async_context(
                app_lifespan_context(self._ephemeral_app)
            )

        if self._ephemeral_app:
            self.logger.debug(
                "Using ephemeral application with database at "
                f"{PREFECT_ORION_DATABASE_CONNECTION_URL.value()}"
            )
        else:
            self.logger.debug(f"Connecting to API at {self.api_url}")

        # Enter the httpx client's context
        await self._exit_stack.enter_async_context(self._client)

        self._started = True

        return self

    async def __aexit__(self, *exc_info):
        """
        Shutdown the client.
        """
        self._closed = True
        return await self._exit_stack.__aexit__(*exc_info)

    def __enter__(self):
        raise RuntimeError(
            "The `OrionClient` must be entered with an async context. Use 'async "
            "with OrionClient(...)' not 'with OrionClient(...)'"
        )

    def __exit__(self, *_):
        assert False, "This should never be called but must be defined for __enter__"
