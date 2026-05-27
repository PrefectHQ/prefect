from __future__ import annotations

import asyncio
import base64
import contextvars
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    ClassVar,
    Dict,
    List,
    Optional,
    cast,
)
from urllib.parse import quote
from uuid import UUID

import httpx
import pydantic
from httpx import Request, Response
from starlette import status
from typing_extensions import Self

from prefect.client.base import PrefectHttpxAsyncClient
from prefect.exceptions import ObjectNotFound
from prefect.logging import get_logger
from prefect.server.schemas.actions import DeploymentFlowRunCreate, StateCreate
from prefect.server.schemas.core import WorkPool
from prefect.server.schemas.filters import VariableFilter, VariableFilterName
from prefect.server.schemas.responses import DeploymentResponse, OrchestrationResult
from prefect.settings import get_current_settings
from prefect.types import StrictVariableValue

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


# Per-request headers pushed by `scoped_headers()`; the httpx request hook
# installed in `BaseClient.__init__` merges them into outgoing requests so
# callers can reuse a single shared client across automation actions while
# still tagging each request with automation-specific identifiers.
_request_scoped_headers: contextvars.ContextVar[Optional[Dict[str, str]]] = (
    contextvars.ContextVar("_request_scoped_headers", default=None)
)


async def _apply_scoped_headers(request: Request) -> None:
    extras = _request_scoped_headers.get()
    if not extras:
        return
    for name, value in extras.items():
        request.headers[name] = value


@asynccontextmanager
async def scoped_headers(headers: Dict[str, str]) -> AsyncIterator[None]:
    """Attach headers to every request sent by a shared client in this scope."""
    token = _request_scoped_headers.set(headers)
    try:
        yield
    finally:
        _request_scoped_headers.reset(token)


class _SharedClientMixin:
    """
    Process-level cache of one open client per `(subclass, settings)`.

    Sharing avoids re-running `create_app()`, `setup_logging()` and
    `Settings.hash_key()` on every automation action. Headers that vary per
    call (e.g. automation identifiers) must be applied with `scoped_headers()`
    rather than baked into the cached client.

    The cache assumes a single, long-lived event loop per process: the cached
    httpx clients and the lazily-created `asyncio.Lock` are bound to the loop
    they are first used on. That holds for the Prefect server and for the
    session-scoped test loop. Test suites that spin up per-test loops (e.g. via
    `asyncio.run`) must call `_reset_shared()` between tests so a client built
    on a now-dead loop is never handed back.
    """

    # Set by each subclass in `__init__`.
    _http_client: PrefectHttpxAsyncClient

    # One registry shared by every subclass, keyed by `(cls, id(settings))`.
    # The settings object is stored next to the client and held by a strong
    # reference on purpose: keeping it alive means its `id()` cannot be
    # recycled for a different `Settings` instance while the entry lives, which
    # would otherwise hand back a client built for stale settings. Distinct
    # `temporary_settings()` blocks therefore get distinct entries; tests evict
    # them via `_reset_shared()`.
    _shared_instances: ClassVar[
        Dict[tuple[type, int], tuple[Any, "_SharedClientMixin"]]
    ] = {}
    _shared_lock: ClassVar[Optional[asyncio.Lock]] = None

    @classmethod
    async def shared(cls) -> Self:
        """
        Return a process-cached client for the current settings, lazily
        constructed and left open for the lifetime of the process. Headers that
        vary per call (e.g. automation identifiers) should be set via
        `scoped_headers()`, not passed at construction.
        """
        settings = get_current_settings()
        key = (cls, id(settings))
        cached = _SharedClientMixin._shared_instances.get(key)
        if cached is not None and cached[0] is settings:
            return cast(Self, cached[1])
        # Lazily create the lock. The check-and-set needs no extra guard: there
        # is no `await` between the `is None` test and the assignment, so no
        # other coroutine on this loop can interleave here. Do not add one.
        if _SharedClientMixin._shared_lock is None:
            _SharedClientMixin._shared_lock = asyncio.Lock()
        async with _SharedClientMixin._shared_lock:
            cached = _SharedClientMixin._shared_instances.get(key)
            if cached is not None and cached[0] is settings:
                return cast(Self, cached[1])
            instance = cls()
            await instance._http_client.__aenter__()
            _SharedClientMixin._shared_instances[key] = (settings, instance)
            return instance

    @classmethod
    async def _reset_shared(cls) -> None:
        """Test helper: close and discard every cached shared instance."""
        entries = list(_SharedClientMixin._shared_instances.values())
        _SharedClientMixin._shared_instances.clear()
        for _settings, instance in entries:
            try:
                await instance._http_client.__aexit__(None, None, None)
            except Exception:
                pass


class BaseClient(_SharedClientMixin):
    def __init__(self, additional_headers: dict[str, str] | None = None):
        from prefect.server.api.server import create_app

        additional_headers = additional_headers or {}

        # create_app caches application instances, and invoking it with no arguments
        # will point it to the the currently running server instance
        api_app = create_app()

        settings = get_current_settings()

        # we pull the auth string from _server_ settings because this client is run on the server
        if auth_string_secret := settings.server.api.auth_string:
            if auth_string := auth_string_secret.get_secret_value():
                token = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
                additional_headers.setdefault("Authorization", f"Basic {token}")

        self._http_client = PrefectHttpxAsyncClient(
            transport=httpx.ASGITransport(app=api_app, raise_app_exceptions=False),
            headers={**additional_headers},
            base_url=f"http://prefect-in-memory{settings.server.api.base_path or '/api'}",
            enable_csrf_support=settings.server.api.csrf_protection_enabled,
            raise_on_all_errors=False,
            event_hooks={"request": [_apply_scoped_headers]},
        )

    async def __aenter__(self) -> Self:
        await self._http_client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._http_client.__aexit__(*args)


class OrchestrationClient(BaseClient):
    async def read_deployment_raw(self, deployment_id: UUID) -> Response:
        return await self._http_client.get(f"/deployments/{deployment_id}")

    async def read_deployment(
        self, deployment_id: UUID
    ) -> Optional[DeploymentResponse]:
        try:
            response = await self.read_deployment_raw(deployment_id)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                return None
            raise
        return DeploymentResponse.model_validate(response.json())

    async def read_flow_raw(self, flow_id: UUID) -> Response:
        return await self._http_client.get(f"/flows/{flow_id}")

    async def create_flow_run(
        self, deployment_id: UUID, flow_run_create: DeploymentFlowRunCreate
    ) -> Response:
        return await self._http_client.post(
            f"/deployments/{deployment_id}/create_flow_run",
            json=flow_run_create.model_dump(mode="json"),
        )

    async def read_flow_run_raw(self, flow_run_id: UUID) -> Response:
        return await self._http_client.get(f"/flow_runs/{flow_run_id}")

    async def delete_flow_run(self, flow_run_id: UUID) -> Response:
        return await self._http_client.delete(f"/flow_runs/{flow_run_id}")

    async def read_task_run_raw(self, task_run_id: UUID) -> Response:
        return await self._http_client.get(f"/task_runs/{task_run_id}")

    async def resume_flow_run(self, flow_run_id: UUID) -> OrchestrationResult:
        response = await self._http_client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )
        response.raise_for_status()
        return OrchestrationResult.model_validate(response.json())

    async def pause_deployment(self, deployment_id: UUID) -> Response:
        return await self._http_client.post(
            f"/deployments/{deployment_id}/pause_deployment",
        )

    async def resume_deployment(self, deployment_id: UUID) -> Response:
        return await self._http_client.post(
            f"/deployments/{deployment_id}/resume_deployment",
        )

    async def set_flow_run_state(
        self, flow_run_id: UUID, state: StateCreate, force: bool = False
    ) -> Response:
        return await self._http_client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json={
                "state": state.model_dump(mode="json"),
                "force": force,
            },
        )

    async def pause_work_pool(self, work_pool_name: str) -> Response:
        return await self._http_client.patch(
            f"/work_pools/{quote(work_pool_name)}", json={"is_paused": True}
        )

    async def resume_work_pool(self, work_pool_name: str) -> Response:
        return await self._http_client.patch(
            f"/work_pools/{quote(work_pool_name)}", json={"is_paused": False}
        )

    async def read_work_pool_raw(self, work_pool_id: UUID) -> Response:
        return await self._http_client.post(
            "/work_pools/filter",
            json={"work_pools": {"id": {"any_": [str(work_pool_id)]}}},
        )

    async def read_work_pool(self, work_pool_id: UUID) -> Optional[WorkPool]:
        response = await self.read_work_pool_raw(work_pool_id)
        response.raise_for_status()

        pools = pydantic.TypeAdapter(List[WorkPool]).validate_python(response.json())
        return pools[0] if pools else None

    async def read_work_queue_raw(self, work_queue_id: UUID) -> Response:
        return await self._http_client.get(f"/work_queues/{work_queue_id}")

    async def read_work_queue_status_raw(self, work_queue_id: UUID) -> Response:
        return await self._http_client.get(f"/work_queues/{work_queue_id}/status")

    async def pause_work_queue(self, work_queue_id: UUID) -> Response:
        return await self._http_client.patch(
            f"/work_queues/{work_queue_id}",
            json={"is_paused": True},
        )

    async def resume_work_queue(self, work_queue_id: UUID) -> Response:
        return await self._http_client.patch(
            f"/work_queues/{work_queue_id}",
            json={"is_paused": False},
        )

    async def read_block_document_raw(
        self,
        block_document_id: UUID,
        include_secrets: bool = True,
    ) -> Response:
        return await self._http_client.get(
            f"/block_documents/{block_document_id}",
            params=dict(include_secrets=include_secrets),
        )

    VARIABLE_PAGE_SIZE = 200
    MAX_VARIABLES_PER_WORKSPACE = 1000

    async def read_workspace_variables(
        self, names: Optional[List[str]] = None
    ) -> Dict[str, StrictVariableValue]:
        variables: Dict[str, StrictVariableValue] = {}

        offset = 0

        filter = VariableFilter()

        if names is not None and not names:
            return variables
        elif names is not None:
            filter.name = VariableFilterName(any_=list(set(names)))

        for offset in range(
            0, self.MAX_VARIABLES_PER_WORKSPACE, self.VARIABLE_PAGE_SIZE
        ):
            response = await self._http_client.post(
                "/variables/filter",
                json={
                    "variables": filter.model_dump(),
                    "limit": self.VARIABLE_PAGE_SIZE,
                    "offset": offset,
                },
            )
            if response.status_code >= 300:
                response.raise_for_status()

            results = response.json()
            for variable in results:
                variables[variable["name"]] = variable["value"]

            if len(results) < self.VARIABLE_PAGE_SIZE:
                break

        return variables

    async def read_concurrency_limit_v2_raw(
        self, concurrency_limit_id: UUID
    ) -> Response:
        return await self._http_client.get(
            f"/v2/concurrency_limits/{concurrency_limit_id}"
        )


class WorkPoolsOrchestrationClient(BaseClient):
    async def __aenter__(self) -> Self:
        return self

    async def read_work_pool(self, work_pool_name: str) -> WorkPool:
        """
        Reads information for a given work pool
        Args:
            work_pool_name: The name of the work pool to for which to get
                information.
        Returns:
            Information about the requested work pool.
        """
        try:
            response = await self._http_client.get(f"/work_pools/{work_pool_name}")
            response.raise_for_status()
            return WorkPool.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == status.HTTP_404_NOT_FOUND:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
