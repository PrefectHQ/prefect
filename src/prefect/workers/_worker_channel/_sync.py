from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from logging import Logger
from typing import Any
from uuid import UUID

import anyio
import anyio.abc
import httpx

from prefect._internal.uuid7 import uuid7
from prefect._internal.websockets import websocket_connect
from prefect.client.base import ServerType
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate, WorkPoolUpdate
from prefect.client.schemas.objects import WorkerMetadata, WorkPool
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.workers._cleanup import WorkerCleanupExecutor
from prefect.workers._worker_channel._protocol import WorkerChannelProtocolHandler
from prefect.workers._worker_channel._state import (
    WorkerChannelRetryableError,
    WorkerChannelSession,
    WorkerChannelState,
    WorkerChannelTerminalError,
)
from prefect.workers._worker_channel._transport import (
    ConnectFactory,
    WorkerChannelTransport,
)


class WorkPoolWorkerChannel:
    def __init__(
        self,
        *,
        client: PrefectClient,
        api_url: str | None,
        work_pool_name: str,
        worker_name: str,
        worker_type: str,
        heartbeat_interval_seconds: int,
        work_queue_names: list[str],
        create_pool_if_not_found: bool,
        default_base_job_template: dict[str, Any],
        worker_metadata: Callable[[], Awaitable[WorkerMetadata | None]],
        work_pool_is_available: Callable[[], bool],
        logger: Logger,
        base_job_template: dict[str, Any] | None = None,
        on_worker_id: Callable[[UUID], None] | None = None,
        on_work_pool_snapshot: Callable[[WorkPool], None] | None = None,
        cleanup_executor: WorkerCleanupExecutor | None = None,
        connect_factory: ConnectFactory = websocket_connect,
        reconnect_base_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
        setup_timeout_seconds: float | None = None,
    ):
        self._client = client
        self.work_pool_name = work_pool_name
        self.worker_name = worker_name
        self.worker_type = worker_type
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.work_queue_names = work_queue_names
        self.create_pool_if_not_found = create_pool_if_not_found
        self.base_job_template = base_job_template
        self.default_base_job_template = default_base_job_template
        self.worker_channel_base_job_template = (
            base_job_template
            if base_job_template is not None
            else default_base_job_template
        )
        self._worker_metadata = worker_metadata
        self._work_pool_is_available = work_pool_is_available
        self._logger = logger
        self._cleanup_executor = cleanup_executor

        self.consumer_id = uuid7()
        self.state = WorkerChannelState()
        self._transport = WorkerChannelTransport(
            api_url=api_url,
            work_pool_name=work_pool_name,
            logger=logger,
            connect_factory=connect_factory,
            reconnect_base_seconds=reconnect_base_seconds,
            reconnect_max_seconds=reconnect_max_seconds,
            setup_timeout_seconds=setup_timeout_seconds,
        )
        self._protocol = WorkerChannelProtocolHandler(
            consumer_id=self.consumer_id,
            worker_name=worker_name,
            worker_type=worker_type,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            work_queue_names=work_queue_names,
            create_pool_if_not_found=create_pool_if_not_found,
            default_base_job_template=self.worker_channel_base_job_template,
            worker_metadata=worker_metadata,
            classify_closed_connection=self._transport.classify_closed_connection,
            logger=logger,
            on_worker_id=on_worker_id,
            on_work_pool_snapshot=on_work_pool_snapshot,
            cleanup_executor=cleanup_executor,
        )
        self._websocket_started = False
        self._run_scope: anyio.CancelScope | None = None

    @property
    def url(self) -> str | None:
        return self._transport.url

    @property
    def rest_fallback_enabled(self) -> bool:
        return self.state.rest_fallback_enabled

    @property
    def worker_id(self) -> UUID | None:
        return self._protocol.worker_id

    @property
    def worker_metadata_sent(self) -> bool:
        return self._protocol.worker_metadata_sent

    def set_client(self, client: PrefectClient) -> None:
        self._client = client

    def stop(self) -> None:
        if self._run_scope is not None:
            self._run_scope.cancel()

    async def sync(self, task_group: anyio.abc.TaskGroup | None) -> None:
        if self.state.healthy:
            return

        if task_group is not None:
            channel_started = await self._start_websocket(task_group)
        else:
            channel_started = False
            if self.url is None:
                self.state.mark_terminal("endpoint_unavailable")

        if channel_started:
            return

        await self._sync_rest_work_pool()
        await self._send_rest_worker_heartbeat()

    async def _start_websocket(self, task_group: anyio.abc.TaskGroup) -> bool:
        if self._websocket_started:
            return self.state.healthy

        if self.url is None:
            self.state.mark_terminal("endpoint_unavailable")
            return False

        self._websocket_started = True
        session: WorkerChannelSession | None = None
        try:
            self.state.mark_connecting()
            session = await self._transport.connect_with_timeout(
                self._protocol.handshake
            )
            self._transport.mark_healthy_once()
            self.state.mark_healthy()
            task_group.start_soon(self._run, session)
            return True
        except WorkerChannelTerminalError as exc:
            self.state.mark_terminal(exc.reason)
            self._logger.debug("Worker channel disabled: %s", exc)
            return False
        except WorkerChannelRetryableError as exc:
            self.state.mark_unhealthy(exc.reason)
            self._logger.debug(
                "Worker channel unhealthy, REST fallback is active: %s", exc
            )
            task_group.start_soon(self._run)
            return False
        except BaseException:
            if session is not None:
                await self._transport.close_session(session)
            raise

    async def _send_rest_worker_heartbeat(self) -> UUID | None:
        if not self.state.rest_fallback_enabled:
            self._logger.debug(
                "Skipping REST worker heartbeat because the worker channel is healthy."
            )
            return None

        if not self._work_pool_is_available():
            self._logger.debug("Worker has no work pool; skipping heartbeat.")
            return None

        should_get_worker_id = self._should_get_worker_id()

        params: dict[str, Any] = {
            "work_pool_name": self.work_pool_name,
            "worker_name": self.worker_name,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "get_worker_id": should_get_worker_id,
        }
        if (
            self._client.server_type == ServerType.CLOUD
            and not self._protocol.worker_metadata_sent
        ):
            worker_metadata = await self._worker_metadata()
            if worker_metadata:
                params["worker_metadata"] = worker_metadata

        worker_id = None
        try:
            worker_id = await self._client.send_worker_heartbeat(**params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 422 and should_get_worker_id:
                self._logger.warning(
                    "Failed to retrieve worker ID from the Prefect API server."
                )
                params["get_worker_id"] = False
                worker_id = await self._client.send_worker_heartbeat(**params)
            else:
                raise

        if "worker_metadata" in params:
            self._protocol.record_worker_metadata_sent()

        if should_get_worker_id and worker_id is None:
            self._logger.warning(
                "Failed to retrieve worker ID from the Prefect API server."
            )

        if worker_id:
            self._protocol.record_worker_id(worker_id)

        return worker_id

    async def _run(self, initial_session: WorkerChannelSession | None = None) -> None:
        with anyio.CancelScope() as scope:
            self._run_scope = scope
            try:
                async with AsyncExitStack() as stack:
                    if self._cleanup_executor is not None:
                        await stack.enter_async_context(self._cleanup_executor)

                    try:
                        if self.url is None:
                            self.state.mark_terminal("endpoint_unavailable")
                            return

                        self._websocket_started = True
                        reconnect_attempt = 0
                        session = initial_session

                        while not self.state.terminal:
                            try:
                                if session is None:
                                    self.state.mark_connecting()
                                    session = (
                                        await self._transport.connect_with_timeout(
                                            self._protocol.handshake
                                        )
                                    )
                                reconnect_attempt = 0
                                self._transport.mark_healthy_once()
                                self.state.mark_healthy()
                                await self._protocol.run_session(session)
                            except WorkerChannelTerminalError as exc:
                                self.state.mark_terminal(exc.reason)
                                self._logger.debug("Worker channel disabled: %s", exc)
                                return
                            except WorkerChannelRetryableError as exc:
                                self.state.mark_unhealthy(exc.reason)
                                self._logger.debug(
                                    "Worker channel unhealthy, REST fallback is "
                                    "active: %s",
                                    exc,
                                )
                            except BaseException:
                                raise
                            finally:
                                if session is not None:
                                    await self._transport.close_session(session)
                                    session = None

                            reconnect_attempt += 1
                            await anyio.sleep(
                                self._transport.reconnect_delay(reconnect_attempt)
                            )
                    finally:
                        if self._cleanup_executor is not None:
                            self._cleanup_executor.cancel()
            finally:
                if self._run_scope is scope:
                    self._run_scope = None

    async def _sync_rest_work_pool(self) -> None:
        try:
            work_pool = await self._client.read_work_pool(
                work_pool_name=self.work_pool_name
            )

        except ObjectNotFound:
            if self.create_pool_if_not_found:
                wp = WorkPoolCreate(
                    name=self.work_pool_name,
                    type=self.worker_type,
                )
                if self.base_job_template is not None:
                    wp.base_job_template = self.base_job_template

                try:
                    work_pool = await self._client.create_work_pool(work_pool=wp)
                    self._logger.info(
                        f"Work pool {self.work_pool_name!r} created."
                    )
                except ObjectAlreadyExists:
                    # Another worker created the pool between our read and
                    # create. Re-read so we can continue with the existing
                    # pool rather than failing setup.
                    self._logger.debug(
                        "Work pool %r was created concurrently by another "
                        "worker; re-reading.",
                        self.work_pool_name,
                    )
                    work_pool = await self._client.read_work_pool(
                        work_pool_name=self.work_pool_name
                    )
            else:
                self._logger.warning(f"Work pool {self.work_pool_name!r} not found!")
                if self.base_job_template is not None:
                    self._logger.warning(
                        "Ignoring supplied base job template because the work pool"
                        " already exists"
                    )
                return

        if not work_pool.base_job_template:
            await self._set_work_pool_template(
                work_pool, self.default_base_job_template
            )
            work_pool.base_job_template = self.default_base_job_template

        self._protocol.handle_work_pool_snapshot(work_pool)

    async def _set_work_pool_template(
        self, work_pool: WorkPool, job_template: dict[str, Any]
    ) -> None:
        await self._client.update_work_pool(
            work_pool_name=work_pool.name,
            work_pool=WorkPoolUpdate(
                base_job_template=job_template,
            ),
        )

    def _should_get_worker_id(self) -> bool:
        return (
            self._client.server_type == ServerType.CLOUD
            and self._protocol.worker_id is None
        )
