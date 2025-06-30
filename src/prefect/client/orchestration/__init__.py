from __future__ import annotations
import asyncio
import base64
import datetime
import ssl
from collections.abc import Iterable
from contextlib import AsyncExitStack
from logging import Logger
from typing import TYPE_CHECKING, Any, Literal, NoReturn, Optional, Union, overload
from uuid import UUID

import certifi
import httpcore
import httpx

import pydantic
from asgi_lifespan import LifespanManager
from packaging import version
from starlette import status
from typing_extensions import ParamSpec, Self, TypeVar

from prefect.client.orchestration._artifacts.client import (
    ArtifactClient,
    ArtifactAsyncClient,
    ArtifactCollectionClient,
    ArtifactCollectionAsyncClient,
)

from prefect.client.orchestration._concurrency_limits.client import (
    ConcurrencyLimitAsyncClient,
    ConcurrencyLimitClient,
)

from prefect.client.orchestration._logs.client import (
    LogClient,
    LogAsyncClient,
)
from prefect.client.orchestration._variables.client import (
    VariableClient,
    VariableAsyncClient,
)

from prefect.client.orchestration._deployments.client import (
    DeploymentClient,
    DeploymentAsyncClient,
)
from prefect.client.orchestration._automations.client import (
    AutomationClient,
    AutomationAsyncClient,
)

from prefect.client.orchestration._work_pools.client import (
    WorkPoolClient,
    WorkPoolAsyncClient,
)

from prefect._experimental.sla.client import SlaClient, SlaAsyncClient

from prefect.client.orchestration._flows.client import (
    FlowClient,
    FlowAsyncClient,
)
from prefect.client.orchestration._flow_runs.client import (
    FlowRunClient,
    FlowRunAsyncClient,
)

from prefect.client.orchestration._blocks_documents.client import (
    BlocksDocumentClient,
    BlocksDocumentAsyncClient,
)

from prefect.client.orchestration._blocks_schemas.client import (
    BlocksSchemaClient,
    BlocksSchemaAsyncClient,
)

from prefect.client.orchestration._blocks_types.client import (
    BlocksTypeClient,
    BlocksTypeAsyncClient,
)

import prefect
import prefect.exceptions
from prefect.logging.loggers import get_run_logger
import prefect.states
from prefect.client.constants import SERVER_API_VERSION
from prefect.client.schemas import FlowRun, OrchestrationResult, TaskRun
from prefect.client.schemas.actions import (
    TaskRunCreate,
    TaskRunUpdate,
    WorkQueueCreate,
    WorkQueueUpdate,
)
from prefect.client.schemas.filters import (
    DeploymentFilter,
    FlowFilter,
    FlowRunFilter,
    TaskRunFilter,
    WorkQueueFilter,
    WorkQueueFilterName,
)
from prefect.client.schemas.objects import (
    TaskRunResult,
    FlowRunResult,
    Parameter,
    Constant,
    TaskRunPolicy,
    WorkQueue,
    WorkQueueStatusDetail,
)

from prefect.client.schemas.sorting import (
    TaskRunSort,
)
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_ENABLE_HTTP2,
    PREFECT_API_KEY,
    PREFECT_API_REQUEST_TIMEOUT,
    PREFECT_API_SSL_CERT_FILE,
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_API_URL,
    PREFECT_CLIENT_CSRF_SUPPORT_ENABLED,
    PREFECT_CLOUD_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    PREFECT_TESTING_UNIT_TEST_MODE,
)
from prefect.types._datetime import now

if TYPE_CHECKING:
    from prefect.tasks import Task as TaskObject

from prefect.client.base import (
    ASGIApp,
    PrefectHttpxAsyncClient,
    PrefectHttpxSyncClient,
    ServerType,
    app_lifespan_context,
)

P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)
T = TypeVar("T")

# Cache for TypeAdapter instances to avoid repeated instantiation
_TYPE_ADAPTER_CACHE: dict[type, pydantic.TypeAdapter[Any]] = {}


def _get_type_adapter(type_: type) -> pydantic.TypeAdapter[Any]:
    """Get or create a cached TypeAdapter for the given type."""
    if type_ not in _TYPE_ADAPTER_CACHE:
        _TYPE_ADAPTER_CACHE[type_] = pydantic.TypeAdapter(type_)
    return _TYPE_ADAPTER_CACHE[type_]


@overload
def get_client(
    httpx_settings: Optional[dict[str, Any]],
    sync_client: Literal[False],
) -> "PrefectClient": ...


@overload
def get_client(*, httpx_settings: Optional[dict[str, Any]]) -> "PrefectClient": ...


@overload
def get_client(*, sync_client: Literal[False] = False) -> "PrefectClient": ...


@overload
def get_client(
    httpx_settings: Optional[dict[str, Any]], sync_client: Literal[True]
) -> "SyncPrefectClient": ...


@overload
def get_client(*, sync_client: Literal[True]) -> "SyncPrefectClient": ...


def get_client(
    httpx_settings: Optional[dict[str, Any]] = None, sync_client: bool = False
) -> Union["SyncPrefectClient", "PrefectClient"]:
    """
    Retrieve a HTTP client for communicating with the Prefect REST API.

    The client must be context managed; for example:

    ```python
    async with get_client() as client:
        await client.hello()
    ```

    To return a synchronous client, pass sync_client=True:

    ```python
    with get_client(sync_client=True) as client:
        client.hello()
    ```
    """
    import prefect.context

    # try to load clients from a client context, if possible
    # only load clients that match the provided config / loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if sync_client:
        if client_ctx := prefect.context.SyncClientContext.get():
            if (
                client_ctx.client
                and getattr(client_ctx, "_httpx_settings", None) == httpx_settings
            ):
                return client_ctx.client
    else:
        if client_ctx := prefect.context.AsyncClientContext.get():
            if (
                client_ctx.client
                and getattr(client_ctx, "_httpx_settings", None) == httpx_settings
                and loop in (getattr(client_ctx.client, "_loop", None), None)
            ):
                return client_ctx.client

    api: str = PREFECT_API_URL.value()
    server_type = None

    if not api and PREFECT_SERVER_ALLOW_EPHEMERAL_MODE:
        # create an ephemeral API if none was provided
        from prefect.server.api.server import SubprocessASGIServer

        server = SubprocessASGIServer()
        server.start()
        assert server.server_process is not None, "Server process did not start"

        api = server.api_url
        server_type = ServerType.EPHEMERAL
    elif not api and not PREFECT_SERVER_ALLOW_EPHEMERAL_MODE:
        raise ValueError(
            "No Prefect API URL provided. Please set PREFECT_API_URL to the address of a running Prefect server."
        )

    if sync_client:
        return SyncPrefectClient(
            api,
            auth_string=PREFECT_API_AUTH_STRING.value(),
            api_key=PREFECT_API_KEY.value(),
            httpx_settings=httpx_settings,
            server_type=server_type,
        )
    else:
        return PrefectClient(
            api,
            auth_string=PREFECT_API_AUTH_STRING.value(),
            api_key=PREFECT_API_KEY.value(),
            httpx_settings=httpx_settings,
            server_type=server_type,
        )


class PrefectClient(
    ArtifactAsyncClient,
    ArtifactCollectionAsyncClient,
    LogAsyncClient,
    VariableAsyncClient,
    ConcurrencyLimitAsyncClient,
    DeploymentAsyncClient,
    AutomationAsyncClient,
    SlaAsyncClient,
    FlowRunAsyncClient,
    FlowAsyncClient,
    BlocksDocumentAsyncClient,
    BlocksSchemaAsyncClient,
    BlocksTypeAsyncClient,
    WorkPoolAsyncClient,
):
    """
    An asynchronous client for interacting with the [Prefect REST API](/api-ref/rest-api/).

    Args:
        api: the REST API URL or FastAPI application to connect to
        api_key: An optional API key for authentication.
        api_version: The API version this client is compatible with.
        httpx_settings: An optional dictionary of settings to pass to the underlying
            `httpx.AsyncClient`

    Examples:

        Say hello to a Prefect REST API

        ```python
        async with get_client() as client:
            response = await client.hello()

        print(response.json())
        👋
        ```
    """

    def __init__(
        self,
        api: Union[str, ASGIApp],
        *,
        auth_string: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        httpx_settings: Optional[dict[str, Any]] = None,
        server_type: Optional[ServerType] = None,
    ) -> None:
        httpx_settings = httpx_settings.copy() if httpx_settings else {}
        httpx_settings.setdefault("headers", {})

        if PREFECT_API_TLS_INSECURE_SKIP_VERIFY:
            # Create an unverified context for insecure connections
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            httpx_settings.setdefault("verify", ctx)
        else:
            cert_file = PREFECT_API_SSL_CERT_FILE.value()
            if not cert_file:
                cert_file = certifi.where()
            # Create a verified context with the certificate file
            ctx = ssl.create_default_context(cafile=cert_file)
            httpx_settings.setdefault("verify", ctx)

        if api_version is None:
            api_version = SERVER_API_VERSION
        httpx_settings["headers"].setdefault("X-PREFECT-API-VERSION", api_version)
        # Prioritize auth_string if provided, otherwise use api_key
        if auth_string:
            token = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
            httpx_settings["headers"]["Authorization"] = (
                f"Basic {token}"  # Overwrite if exists
            )
        elif api_key:
            httpx_settings["headers"]["Authorization"] = (
                f"Bearer {api_key}"  # Set if auth_string is not present
            )

        # Context management
        self._context_stack: int = 0
        self._exit_stack = AsyncExitStack()
        self._ephemeral_app: Optional[ASGIApp] = None
        self.manage_lifespan = True
        self.server_type: ServerType

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

            # See https://www.python-httpx.org/advanced/#pool-limit-configuration
            httpx_settings.setdefault(
                "limits",
                httpx.Limits(
                    # We see instability when allowing the client to open many connections at once.
                    # Limiting concurrency results in more stable performance.
                    max_connections=16,
                    max_keepalive_connections=8,
                    # The Prefect Cloud LB will keep connections alive for 30s.
                    # Only allow the client to keep connections alive for 25s.
                    keepalive_expiry=25,
                ),
            )

            # See https://www.python-httpx.org/http2/
            # Enabling HTTP/2 support on the client does not necessarily mean that your requests
            # and responses will be transported over HTTP/2, since both the client and the server
            # need to support HTTP/2. If you connect to a server that only supports HTTP/1.1 the
            # client will use a standard HTTP/1.1 connection instead.
            httpx_settings.setdefault("http2", PREFECT_API_ENABLE_HTTP2.value())

            if server_type:
                self.server_type = server_type
            else:
                self.server_type = (
                    ServerType.CLOUD
                    if api.startswith(PREFECT_CLOUD_API_URL.value())
                    else ServerType.SERVER
                )

        # Connect to an in-process application
        else:
            self._ephemeral_app = api
            self.server_type = ServerType.EPHEMERAL

            # When using an ephemeral server, server-side exceptions can be raised
            # client-side breaking all of our response error code handling. To work
            # around this, we create an ASGI transport with application exceptions
            # disabled instead of using the application directly.
            # refs:
            # - https://github.com/PrefectHQ/prefect/pull/9637
            # - https://github.com/encode/starlette/blob/d3a11205ed35f8e5a58a711db0ff59c86fa7bb31/starlette/middleware/errors.py#L184
            # - https://github.com/tiangolo/fastapi/blob/8cc967a7605d3883bd04ceb5d25cc94ae079612f/fastapi/applications.py#L163-L164
            httpx_settings.setdefault(
                "transport",
                httpx.ASGITransport(
                    app=self._ephemeral_app, raise_app_exceptions=False
                ),
            )
            httpx_settings.setdefault("base_url", "http://ephemeral-prefect/api")

        # See https://www.python-httpx.org/advanced/#timeout-configuration
        httpx_settings.setdefault(
            "timeout",
            httpx.Timeout(
                connect=PREFECT_API_REQUEST_TIMEOUT.value(),
                read=PREFECT_API_REQUEST_TIMEOUT.value(),
                write=PREFECT_API_REQUEST_TIMEOUT.value(),
                pool=PREFECT_API_REQUEST_TIMEOUT.value(),
            ),
        )

        if not PREFECT_TESTING_UNIT_TEST_MODE:
            httpx_settings.setdefault("follow_redirects", True)

        enable_csrf_support = (
            self.server_type != ServerType.CLOUD
            and PREFECT_CLIENT_CSRF_SUPPORT_ENABLED.value()
        )

        self._client = PrefectHttpxAsyncClient(
            **httpx_settings, enable_csrf_support=enable_csrf_support
        )
        self._loop = None

        # See https://www.python-httpx.org/advanced/#custom-transports
        #
        # If we're using an HTTP/S client (not the ephemeral client), adjust the
        # transport to add retries _after_ it is instantiated. If we alter the transport
        # before instantiation, the transport will not be aware of proxies unless we
        # reproduce all of the logic to make it so.
        #
        # Only alter the transport to set our default of 3 retries, don't modify any
        # transport a user may have provided via httpx_settings.
        #
        # Making liberal use of getattr and isinstance checks here to avoid any
        # surprises if the internals of httpx or httpcore change on us
        if isinstance(api, str) and not httpx_settings.get("transport"):
            transport_for_url = getattr(self._client, "_transport_for_url", None)
            if callable(transport_for_url):
                server_transport = transport_for_url(httpx.URL(api))
                if isinstance(server_transport, httpx.AsyncHTTPTransport):
                    pool = getattr(server_transport, "_pool", None)
                    if isinstance(pool, httpcore.AsyncConnectionPool):
                        setattr(pool, "_retries", 3)

        self.logger: Logger = get_logger("client")

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
            await self._client.get("/health")
            return None
        except Exception as exc:
            return exc

    async def hello(self) -> httpx.Response:
        """
        Send a GET request to /hello for testing purposes.
        """
        return await self._client.get("/hello")

    async def create_work_queue(
        self,
        name: str,
        description: Optional[str] = None,
        is_paused: Optional[bool] = None,
        concurrency_limit: Optional[int] = None,
        priority: Optional[int] = None,
        work_pool_name: Optional[str] = None,
    ) -> WorkQueue:
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
            prefect.exceptions.ObjectAlreadyExists: If request returns 409
            httpx.RequestError: If request fails

        Returns:
            The created work queue
        """
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
                response = await self._client.post(
                    f"/work_pools/{work_pool_name}/queues", json=data
                )
            else:
                response = await self._client.post("/work_queues/", json=data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_409_CONFLICT:
                raise prefect.exceptions.ObjectAlreadyExists(http_exc=e) from e
            elif e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueue.model_validate(response.json())

    async def read_work_queue_by_name(
        self,
        name: str,
        work_pool_name: Optional[str] = None,
    ) -> WorkQueue:
        """
        Read a work queue by name.

        Args:
            name (str): a unique name for the work queue
            work_pool_name (str, optional): the name of the work pool
                the queue belongs to.

        Raises:
            prefect.exceptions.ObjectNotFound: if no work queue is found
            httpx.HTTPStatusError: other status errors

        Returns:
            WorkQueue: a work queue API object
        """
        try:
            if work_pool_name is not None:
                response = await self._client.get(
                    f"/work_pools/{work_pool_name}/queues/{name}"
                )
            else:
                response = await self._client.get(f"/work_queues/name/{name}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

        return WorkQueue.model_validate(response.json())

    async def update_work_queue(self, id: UUID, **kwargs: Any) -> None:
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

        data = WorkQueueUpdate(**kwargs).model_dump(mode="json", exclude_unset=True)
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
        scheduled_before: Optional[datetime.datetime] = None,
    ) -> list[FlowRun]:
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
            List[FlowRun]: a list of FlowRun objects read from the queue
        """
        if scheduled_before is None:
            scheduled_before = now("UTC")

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
        return _get_type_adapter(list[FlowRun]).validate_python(response.json())

    async def read_work_queue(
        self,
        id: UUID,
    ) -> WorkQueue:
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
        return WorkQueue.model_validate(response.json())

    async def read_work_queue_status(
        self,
        id: UUID,
    ) -> WorkQueueStatusDetail:
        """
        Read a work queue status.

        Args:
            id: the id of the work queue to load

        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        Returns:
            WorkQueueStatus: an instantiated WorkQueueStatus object
        """
        try:
            response = await self._client.get(f"/work_queues/{id}/status")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise
        return WorkQueueStatusDetail.model_validate(response.json())

    async def match_work_queues(
        self,
        prefixes: list[str],
        work_pool_name: Optional[str] = None,
    ) -> list[WorkQueue]:
        """
        Query the Prefect API for work queues with names with a specific prefix.

        Args:
            prefixes: a list of strings used to match work queue name prefixes
            work_pool_name: an optional work pool name to scope the query to

        Returns:
            a list of WorkQueue model representations
                of the work queues
        """
        page_length = 100
        current_page = 0
        work_queues: list[WorkQueue] = []

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
        id: UUID,
    ) -> None:
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

    async def set_task_run_name(self, task_run_id: UUID, name: str) -> httpx.Response:
        task_run_data = TaskRunUpdate(name=name)
        return await self._client.patch(
            f"/task_runs/{task_run_id}",
            json=task_run_data.model_dump(mode="json", exclude_unset=True),
        )

    async def create_task_run(
        self,
        task: "TaskObject[P, R]",
        flow_run_id: Optional[UUID],
        dynamic_key: str,
        id: Optional[UUID] = None,
        name: Optional[str] = None,
        extra_tags: Optional[Iterable[str]] = None,
        state: Optional[prefect.states.State[R]] = None,
        task_inputs: Optional[
            dict[
                str,
                list[Union[TaskRunResult, FlowRunResult, Parameter, Constant]],
            ]
        ] = None,
    ) -> TaskRun:
        """
        Create a task run

        Args:
            task: The Task to run
            flow_run_id: The flow run id with which to associate the task run
            dynamic_key: A key unique to this particular run of a Task within the flow
            id: An optional ID for the task run. If not provided, one will be generated
                server-side.
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
            state = prefect.states.Pending()

        retry_delay = task.retry_delay_seconds
        if isinstance(retry_delay, list):
            retry_delay = [int(rd) for rd in retry_delay]
        elif isinstance(retry_delay, float):
            retry_delay = int(retry_delay)

        task_run_data = TaskRunCreate(
            id=id,
            name=name,
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=str(dynamic_key),
            tags=list(tags),
            task_version=task.version,
            empirical_policy=TaskRunPolicy(
                retries=task.retries,
                retry_delay=retry_delay,
                retry_jitter_factor=task.retry_jitter_factor,
            ),
            state=prefect.states.to_state_create(state),
            task_inputs=task_inputs or {},
        )
        content = task_run_data.model_dump_json(exclude={"id"} if id is None else None)

        response = await self._client.post("/task_runs/", content=content)
        return TaskRun.model_validate(response.json())

    async def read_task_run(self, task_run_id: UUID) -> TaskRun:
        """
        Query the Prefect API for a task run by id.

        Args:
            task_run_id: the task run ID of interest

        Returns:
            a Task Run model representation of the task run
        """
        try:
            response = await self._client.get(f"/task_runs/{task_run_id}")
            return TaskRun.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_task_runs(
        self,
        *,
        flow_filter: Optional[FlowFilter] = None,
        flow_run_filter: Optional[FlowRunFilter] = None,
        task_run_filter: Optional[TaskRunFilter] = None,
        deployment_filter: Optional[DeploymentFilter] = None,
        sort: Optional[TaskRunSort] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[TaskRun]:
        """
        Query the Prefect API for task runs. Only task runs matching all criteria will
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
            a list of Task Run model representations
                of the task runs
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
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }
        response = await self._client.post("/task_runs/filter", json=body)
        return _get_type_adapter(list[TaskRun]).validate_python(response.json())

    async def delete_task_run(self, task_run_id: UUID) -> None:
        """
        Delete a task run by id.

        Args:
            task_run_id: the task run ID of interest
        Raises:
            prefect.exceptions.ObjectNotFound: If request returns 404
            httpx.RequestError: If requests fails
        """
        try:
            await self._client.delete(f"/task_runs/{task_run_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def set_task_run_state(
        self,
        task_run_id: UUID,
        state: prefect.states.State[T],
        force: bool = False,
    ) -> OrchestrationResult[T]:
        """
        Set the state of a task run.

        Args:
            task_run_id: the id of the task run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Prefect API to accept the state

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        state_create = prefect.states.to_state_create(state)
        state_create.state_details.task_run_id = task_run_id
        response = await self._client.post(
            f"/task_runs/{task_run_id}/set_state",
            json=dict(state=state_create.model_dump(mode="json"), force=force),
        )
        result: OrchestrationResult[T] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    async def read_task_run_states(
        self, task_run_id: UUID
    ) -> list[prefect.states.State]:
        """
        Query for the states of a task run

        Args:
            task_run_id: the id of the task run

        Returns:
            a list of State model representations of the task run states
        """
        response = await self._client.get(
            "/task_run_states/", params=dict(task_run_id=str(task_run_id))
        )
        return _get_type_adapter(list[prefect.states.State]).validate_python(
            response.json()
        )

    async def read_work_queues(
        self,
        work_pool_name: Optional[str] = None,
        work_queue_filter: Optional[WorkQueueFilter] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[WorkQueue]:
        """
        Retrieves queues for a work pool.

        Args:
            work_pool_name: Name of the work pool for which to get queues.
            work_queue_filter: Criteria by which to filter queues.
            limit: Limit for the queue query.
            offset: Limit for the queue query.

        Returns:
            List of queues for the specified work pool.
        """
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
                response = await self._client.post(
                    f"/work_pools/{work_pool_name}/queues/filter",
                    json=json,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == status.HTTP_404_NOT_FOUND:
                    raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
                else:
                    raise
        else:
            response = await self._client.post("/work_queues/filter", json=json)

        return _get_type_adapter(list[WorkQueue]).validate_python(response.json())

    async def read_worker_metadata(self) -> dict[str, Any]:
        """Reads worker metadata stored in Prefect collection registry."""
        response = await self._client.get("collections/views/aggregate-worker-metadata")
        response.raise_for_status()
        return response.json()

    async def api_version(self) -> str:
        res = await self._client.get("/admin/version")
        return res.json()

    def client_version(self) -> str:
        return prefect.__version__

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    async def raise_for_api_version_mismatch(self) -> None:
        # Cloud is always compatible as a server
        if self.server_type == ServerType.CLOUD:
            return

        try:
            api_version = await self.api_version()
        except Exception as e:
            if "Unauthorized" in str(e):
                raise e
            raise RuntimeError(f"Failed to reach API at {self.api_url}") from e

        api_version = version.parse(api_version)
        client_version = version.parse(self.client_version())

        if api_version.major != client_version.major:
            raise RuntimeError(
                f"Found incompatible versions: client: {client_version}, server: {api_version}. "
                "Major versions must match."
            )
        if api_version < client_version:
            warning_message = (
                "Your Prefect server is running an older version of Prefect than your client which may result in unexpected behavior. "
                f"Please upgrade your Prefect server from version {api_version} to version {client_version} or higher."
            )
            try:
                get_run_logger().warning(warning_message)
            except prefect.context.MissingContextError:
                self.logger.warning(warning_message)

    async def __aenter__(self) -> Self:
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

        self._context_stack += 1

        if self._started:
            # allow reentrancy
            return self

        self._loop = asyncio.get_running_loop()
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
                f"{PREFECT_API_DATABASE_CONNECTION_URL.value()}"
            )
        else:
            self.logger.debug(f"Connecting to API at {self.api_url}")

        # Enter the httpx client's context
        await self._exit_stack.enter_async_context(self._client)

        self._started = True

        return self

    async def __aexit__(self, *exc_info: Any) -> Optional[bool]:
        """
        Shutdown the client.
        """

        self._context_stack -= 1
        if self._context_stack > 0:
            return
        self._closed = True
        return await self._exit_stack.__aexit__(*exc_info)

    def __enter__(self) -> NoReturn:
        raise RuntimeError(
            "The `PrefectClient` must be entered with an async context. Use 'async "
            "with PrefectClient(...)' not 'with PrefectClient(...)'"
        )

    def __exit__(self, *_: object) -> NoReturn:
        assert False, "This should never be called but must be defined for __enter__"


class SyncPrefectClient(
    ArtifactClient,
    ArtifactCollectionClient,
    LogClient,
    VariableClient,
    ConcurrencyLimitClient,
    DeploymentClient,
    AutomationClient,
    SlaClient,
    FlowRunClient,
    FlowClient,
    BlocksDocumentClient,
    BlocksSchemaClient,
    BlocksTypeClient,
    WorkPoolClient,
):
    """
    A synchronous client for interacting with the [Prefect REST API](/api-ref/rest-api/).

    Args:
        api: the REST API URL or FastAPI application to connect to
        api_key: An optional API key for authentication.
        api_version: The API version this client is compatible with.
        httpx_settings: An optional dictionary of settings to pass to the underlying
            `httpx.Client`

    Examples:

        Say hello to a Prefect REST API

        ```python
        with get_client(sync_client=True) as client:
            response = client.hello()

        print(response.json())
        👋
        ```
    """

    def __init__(
        self,
        api: Union[str, ASGIApp],
        *,
        auth_string: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        httpx_settings: Optional[dict[str, Any]] = None,
        server_type: Optional[ServerType] = None,
    ) -> None:
        httpx_settings = httpx_settings.copy() if httpx_settings else {}
        httpx_settings.setdefault("headers", {})

        if PREFECT_API_TLS_INSECURE_SKIP_VERIFY:
            # Create an unverified context for insecure connections
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            httpx_settings.setdefault("verify", ctx)
        else:
            cert_file = PREFECT_API_SSL_CERT_FILE.value()
            if not cert_file:
                cert_file = certifi.where()
            # Create a verified context with the certificate file
            ctx = ssl.create_default_context(cafile=cert_file)
            httpx_settings.setdefault("verify", ctx)

        if api_version is None:
            api_version = SERVER_API_VERSION
        httpx_settings["headers"].setdefault("X-PREFECT-API-VERSION", api_version)
        # Prioritize auth_string if provided, otherwise use api_key
        if auth_string:
            token = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
            httpx_settings["headers"]["Authorization"] = (
                f"Basic {token}"  # Overwrite if exists
            )
        elif api_key:
            httpx_settings["headers"]["Authorization"] = (
                f"Bearer {api_key}"  # Set if auth_string is not present
            )

        # Context management
        self._context_stack: int = 0
        self._ephemeral_app: Optional[ASGIApp] = None
        self.manage_lifespan = True
        self.server_type: ServerType

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

            # See https://www.python-httpx.org/advanced/#pool-limit-configuration
            httpx_settings.setdefault(
                "limits",
                httpx.Limits(
                    # We see instability when allowing the client to open many connections at once.
                    # Limiting concurrency results in more stable performance.
                    max_connections=16,
                    max_keepalive_connections=8,
                    # The Prefect Cloud LB will keep connections alive for 30s.
                    # Only allow the client to keep connections alive for 25s.
                    keepalive_expiry=25,
                ),
            )

            # See https://www.python-httpx.org/http2/
            # Enabling HTTP/2 support on the client does not necessarily mean that your requests
            # and responses will be transported over HTTP/2, since both the client and the server
            # need to support HTTP/2. If you connect to a server that only supports HTTP/1.1 the
            # client will use a standard HTTP/1.1 connection instead.
            httpx_settings.setdefault("http2", PREFECT_API_ENABLE_HTTP2.value())

            if server_type:
                self.server_type = server_type
            else:
                self.server_type = (
                    ServerType.CLOUD
                    if api.startswith(PREFECT_CLOUD_API_URL.value())
                    else ServerType.SERVER
                )

        # Connect to an in-process application
        else:
            self._ephemeral_app = api
            self.server_type = ServerType.EPHEMERAL

        # See https://www.python-httpx.org/advanced/#timeout-configuration
        httpx_settings.setdefault(
            "timeout",
            httpx.Timeout(
                connect=PREFECT_API_REQUEST_TIMEOUT.value(),
                read=PREFECT_API_REQUEST_TIMEOUT.value(),
                write=PREFECT_API_REQUEST_TIMEOUT.value(),
                pool=PREFECT_API_REQUEST_TIMEOUT.value(),
            ),
        )

        if not PREFECT_TESTING_UNIT_TEST_MODE:
            httpx_settings.setdefault("follow_redirects", True)

        enable_csrf_support = (
            self.server_type != ServerType.CLOUD
            and PREFECT_CLIENT_CSRF_SUPPORT_ENABLED.value()
        )

        self._client = PrefectHttpxSyncClient(
            **httpx_settings, enable_csrf_support=enable_csrf_support
        )

        # See https://www.python-httpx.org/advanced/#custom-transports
        #
        # If we're using an HTTP/S client (not the ephemeral client), adjust the
        # transport to add retries _after_ it is instantiated. If we alter the transport
        # before instantiation, the transport will not be aware of proxies unless we
        # reproduce all of the logic to make it so.
        #
        # Only alter the transport to set our default of 3 retries, don't modify any
        # transport a user may have provided via httpx_settings.
        #
        # Making liberal use of getattr and isinstance checks here to avoid any
        # surprises if the internals of httpx or httpcore change on us
        if isinstance(api, str) and not httpx_settings.get("transport"):
            transport_for_url = getattr(self._client, "_transport_for_url", None)
            if callable(transport_for_url):
                server_transport = transport_for_url(httpx.URL(api))
                if isinstance(server_transport, httpx.HTTPTransport):
                    pool = getattr(server_transport, "_pool", None)
                    if isinstance(pool, httpcore.ConnectionPool):
                        setattr(pool, "_retries", 3)

        self.logger: Logger = get_logger("client")

    @property
    def api_url(self) -> httpx.URL:
        """
        Get the base URL for the API.
        """
        return self._client.base_url

    # Context management ----------------------------------------------------------------

    def __enter__(self) -> "SyncPrefectClient":
        """
        Start the client.

        If the client is already started, this will raise an exception.

        If the client is already closed, this will raise an exception. Use a new client
        instance instead.
        """
        if self._closed:
            # httpx.Client does not allow reuse so we will not either.
            raise RuntimeError(
                "The client cannot be started again after closing. "
                "Retrieve a new client with `get_client()` instead."
            )

        self._context_stack += 1

        if self._started:
            # allow reentrancy
            return self

        self._client.__enter__()
        self._started = True

        return self

    def __exit__(self, *exc_info: Any) -> None:
        """
        Shutdown the client.
        """
        self._context_stack -= 1
        if self._context_stack > 0:
            return
        self._closed = True
        self._client.__exit__(*exc_info)

    # API methods ----------------------------------------------------------------------

    def api_healthcheck(self) -> Optional[Exception]:
        """
        Attempts to connect to the API and returns the encountered exception if not
        successful.

        If successful, returns `None`.
        """
        try:
            self._client.get("/health")
            return None
        except Exception as exc:
            return exc

    def hello(self) -> httpx.Response:
        """
        Send a GET request to /hello for testing purposes.
        """
        return self._client.get("/hello")

    def api_version(self) -> str:
        res = self._client.get("/admin/version")
        return res.json()

    def client_version(self) -> str:
        return prefect.__version__

    def raise_for_api_version_mismatch(self) -> None:
        # Cloud is always compatible as a server
        if self.server_type == ServerType.CLOUD:
            return

        try:
            api_version = self.api_version()
        except Exception as e:
            if "Unauthorized" in str(e):
                raise e
            raise RuntimeError(f"Failed to reach API at {self.api_url}") from e

        api_version = version.parse(api_version)
        client_version = version.parse(self.client_version())

        if api_version.major != client_version.major:
            raise RuntimeError(
                f"Found incompatible versions: client: {client_version}, server: {api_version}. "
                "Major versions must match."
            )
        if api_version < client_version:
            warning_message = (
                "Your Prefect server is running an older version of Prefect than your client which may result in unexpected behavior. "
                f"Please upgrade your Prefect server from version {api_version} to version {client_version} or higher."
            )
            try:
                get_run_logger().warning(warning_message)
            except prefect.context.MissingContextError:
                self.logger.warning(warning_message)

    def set_task_run_name(self, task_run_id: UUID, name: str) -> httpx.Response:
        task_run_data = TaskRunUpdate(name=name)
        return self._client.patch(
            f"/task_runs/{task_run_id}",
            json=task_run_data.model_dump(mode="json", exclude_unset=True),
        )

    def create_task_run(
        self,
        task: "TaskObject[P, R]",
        flow_run_id: Optional[UUID],
        dynamic_key: str,
        id: Optional[UUID] = None,
        name: Optional[str] = None,
        extra_tags: Optional[Iterable[str]] = None,
        state: Optional[prefect.states.State[R]] = None,
        task_inputs: Optional[
            dict[
                str,
                list[
                    Union[
                        TaskRunResult,
                        FlowRunResult,
                        Parameter,
                        Constant,
                    ]
                ],
            ]
        ] = None,
    ) -> TaskRun:
        """
        Create a task run

        Args:
            task: The Task to run
            flow_run_id: The flow run id with which to associate the task run
            dynamic_key: A key unique to this particular run of a Task within the flow
            id: An optional ID for the task run. If not provided, one will be generated
                server-side.
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
            state = prefect.states.Pending()

        retry_delay = task.retry_delay_seconds
        if isinstance(retry_delay, list):
            retry_delay = [int(rd) for rd in retry_delay]
        elif isinstance(retry_delay, float):
            retry_delay = int(retry_delay)

        task_run_data = TaskRunCreate(
            id=id,
            name=name,
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=dynamic_key,
            tags=list(tags),
            task_version=task.version,
            empirical_policy=TaskRunPolicy(
                retries=task.retries,
                retry_delay=retry_delay,
                retry_jitter_factor=task.retry_jitter_factor,
            ),
            state=prefect.states.to_state_create(state),
            task_inputs=task_inputs or {},
        )

        content = task_run_data.model_dump_json(exclude={"id"} if id is None else None)

        response = self._client.post("/task_runs/", content=content)
        return TaskRun.model_validate(response.json())

    def read_task_run(self, task_run_id: UUID) -> TaskRun:
        """
        Query the Prefect API for a task run by id.

        Args:
            task_run_id: the task run ID of interest

        Returns:
            a Task Run model representation of the task run
        """
        try:
            response = self._client.get(f"/task_runs/{task_run_id}")
            return TaskRun.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise prefect.exceptions.ObjectNotFound(http_exc=e) from e
            else:
                raise

    def read_task_runs(
        self,
        *,
        flow_filter: Optional[FlowFilter] = None,
        flow_run_filter: Optional[FlowRunFilter] = None,
        task_run_filter: Optional[TaskRunFilter] = None,
        deployment_filter: Optional[DeploymentFilter] = None,
        sort: Optional[TaskRunSort] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[TaskRun]:
        """
        Query the Prefect API for task runs. Only task runs matching all criteria will
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
            a list of Task Run model representations
                of the task runs
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
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }
        response = self._client.post("/task_runs/filter", json=body)
        return _get_type_adapter(list[TaskRun]).validate_python(response.json())

    def set_task_run_state(
        self,
        task_run_id: UUID,
        state: prefect.states.State[Any],
        force: bool = False,
    ) -> OrchestrationResult[Any]:
        """
        Set the state of a task run.

        Args:
            task_run_id: the id of the task run
            state: the state to set
            force: if True, disregard orchestration logic when setting the state,
                forcing the Prefect API to accept the state

        Returns:
            an OrchestrationResult model representation of state orchestration output
        """
        state_create = prefect.states.to_state_create(state)
        state_create.state_details.task_run_id = task_run_id
        response = self._client.post(
            f"/task_runs/{task_run_id}/set_state",
            json=dict(state=state_create.model_dump(mode="json"), force=force),
        )
        result: OrchestrationResult[Any] = OrchestrationResult.model_validate(
            response.json()
        )
        return result

    def read_task_run_states(self, task_run_id: UUID) -> list[prefect.states.State]:
        """
        Query for the states of a task run

        Args:
            task_run_id: the id of the task run

        Returns:
            a list of State model representations of the task run states
        """
        response = self._client.get(
            "/task_run_states/", params=dict(task_run_id=str(task_run_id))
        )
        return _get_type_adapter(list[prefect.states.State]).validate_python(
            response.json()
        )
