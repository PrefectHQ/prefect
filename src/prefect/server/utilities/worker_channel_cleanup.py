from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from prefect.logging import get_logger
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueWakeup,
    WorkerCleanupQueue,
)
from prefect.types import DateTime
from prefect.types._datetime import now

if TYPE_CHECKING:
    from prefect.server.utilities.worker_channel import WorkerChannelConnection

logger: logging.Logger = get_logger("prefect.server.utilities.worker_channel")

_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS = 1.0


@dataclass(frozen=True)
class WorkerCleanupInFlight:
    message_id: UUID
    reservation_token: str
    lease_expires_at: DateTime


class WorkerCleanupConnectionRegistry:
    def __init__(self) -> None:
        self._connections_by_work_pool_id: defaultdict[
            UUID, list[WorkerChannelConnection]
        ] = defaultdict(list)
        self._dispatch_locks: defaultdict[UUID, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )
        self._dispatch_events_by_work_pool_id: dict[UUID, asyncio.Event] = {}
        self._dispatch_loops_by_work_pool_id: dict[UUID, asyncio.AbstractEventLoop] = {}
        self._dispatch_tasks_by_work_pool_id: dict[UUID, asyncio.Task[None]] = {}
        self._exiting_dispatch_tasks_by_work_pool_id: dict[
            UUID, asyncio.Task[None]
        ] = {}
        self._cleanup_in_flight_by_worker: defaultdict[
            tuple[UUID, UUID, str], dict[str, WorkerCleanupInFlight]
        ] = defaultdict(dict)
        self._cleanup_dispatching_by_worker: set[tuple[UUID, UUID, str]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def register(
        self, connection: WorkerChannelConnection
    ) -> AsyncIterator[None]:
        async with self._lock:
            self._prune_expired_cleanup_reservations_for_work_pool_locked(
                connection.work_pool_id
            )
            self._connections_by_work_pool_id[connection.work_pool_id].append(
                connection
            )
            assert connection._cleanup_queue is not None
            self._ensure_cleanup_dispatcher_locked(
                work_pool_id=connection.work_pool_id,
                cleanup_queue=connection._cleanup_queue,
            )

        try:
            yield
        finally:
            event_to_wake: asyncio.Event | None = None
            loop_to_wake: asyncio.AbstractEventLoop | None = None
            async with self._lock:
                connections = self._connections_by_work_pool_id.get(
                    connection.work_pool_id
                )
                if connections is not None:
                    try:
                        connections.remove(connection)
                    except ValueError:
                        pass
                    else:
                        if not connections:
                            self._connections_by_work_pool_id.pop(
                                connection.work_pool_id, None
                            )
                            event_to_wake = self._dispatch_events_by_work_pool_id.get(
                                connection.work_pool_id, None
                            )
                            loop_to_wake = self._dispatch_loops_by_work_pool_id.get(
                                connection.work_pool_id, None
                            )

            if event_to_wake is not None:
                self._set_dispatch_event(event_to_wake, loop_to_wake)

    async def has_cleanup_capacity(
        self, connection: WorkerChannelConnection, max_cleanup_concurrency: int
    ) -> bool:
        async with self._lock:
            in_flight = self._cleanup_in_flight_for_connection_locked(connection)
            self._prune_expired_cleanup_reservations_locked(in_flight)
            self._drop_empty_cleanup_in_flight_locked(connection, in_flight)
            return len(in_flight) < max_cleanup_concurrency

    async def track_cleanup_reservation(
        self,
        connection: WorkerChannelConnection,
        in_flight: WorkerCleanupInFlight,
        max_cleanup_concurrency: int,
    ) -> bool:
        async with self._lock:
            current_in_flight = self._cleanup_in_flight_for_connection_locked(
                connection
            )
            self._prune_expired_cleanup_reservations_locked(current_in_flight)
            if len(current_in_flight) >= max_cleanup_concurrency:
                self._drop_empty_cleanup_in_flight_locked(connection, current_in_flight)
                return False

            current_in_flight[in_flight.reservation_token] = in_flight
            return True

    async def update_cleanup_lease(
        self,
        connection: WorkerChannelConnection,
        *,
        reservation_token: str,
        lease_expires_at: DateTime,
    ) -> bool:
        async with self._lock:
            current_in_flight = self._cleanup_in_flight_for_connection_locked(
                connection
            )
            in_flight = current_in_flight.get(reservation_token)
            if in_flight is None:
                self._drop_empty_cleanup_in_flight_locked(connection, current_in_flight)
                return False

            current_in_flight[reservation_token] = WorkerCleanupInFlight(
                message_id=in_flight.message_id,
                reservation_token=in_flight.reservation_token,
                lease_expires_at=lease_expires_at,
            )
            return True

    async def forget_cleanup_reservation(
        self,
        connection: WorkerChannelConnection,
        *,
        message_id: UUID,
        reservation_token: str,
    ) -> bool:
        async with self._lock:
            key = self._worker_key(connection)
            current_in_flight = self._cleanup_in_flight_by_worker.get(key)
            if current_in_flight is None:
                return False

            in_flight = current_in_flight.get(reservation_token)
            if in_flight is None or in_flight.message_id != message_id:
                return False

            current_in_flight.pop(reservation_token)
            if not current_in_flight:
                self._cleanup_in_flight_by_worker.pop(key, None)
            return True

    async def dispatch_available(
        self,
        *,
        work_pool_id: UUID,
        cleanup_queue: WorkerCleanupQueue,
    ) -> None:
        while True:
            async with self._dispatch_locks[work_pool_id]:
                async with self._lock:
                    self._prune_expired_cleanup_reservations_for_work_pool_locked(
                        work_pool_id
                    )
                candidates = await self._eligible_connections(work_pool_id)

            if not candidates:
                return

            dispatched = False
            for allow_fallback_to_any_queue in (False, True):
                for connection in candidates:
                    if not await self._claim_cleanup_dispatch(connection):
                        continue
                    try:
                        if await connection.dispatch_one_cleanup_message(
                            cleanup_queue=cleanup_queue,
                            allow_fallback_to_any_queue=allow_fallback_to_any_queue,
                        ):
                            await self._mark_cleanup_dispatched(connection)
                            dispatched = True
                            break
                    finally:
                        await self._release_cleanup_dispatch_claim(connection)
                if dispatched:
                    break

            if not dispatched:
                return

    def wake_dispatcher(self, work_pool_id: UUID) -> None:
        event = self._dispatch_events_by_work_pool_id.get(work_pool_id)
        loop = self._dispatch_loops_by_work_pool_id.get(work_pool_id)
        if event is not None:
            self._set_dispatch_event(event, loop)

    def _ensure_cleanup_dispatcher_locked(
        self,
        *,
        work_pool_id: UUID,
        cleanup_queue: WorkerCleanupQueue,
    ) -> None:
        task = self._dispatch_tasks_by_work_pool_id.get(work_pool_id)
        if task is not None and not task.done():
            if (
                self._exiting_dispatch_tasks_by_work_pool_id.get(work_pool_id)
                is not task
            ):
                self.wake_dispatcher(work_pool_id)
                return

        if task is not None:
            self._exiting_dispatch_tasks_by_work_pool_id.pop(work_pool_id, None)
            if task.done():
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("Worker channel cleanup dispatcher failed")

        loop = asyncio.get_running_loop()
        event = asyncio.Event()
        self._dispatch_events_by_work_pool_id[work_pool_id] = event
        self._dispatch_loops_by_work_pool_id[work_pool_id] = loop
        self._dispatch_tasks_by_work_pool_id[work_pool_id] = asyncio.create_task(
            self._dispatch_loop(
                work_pool_id=work_pool_id,
                cleanup_queue=cleanup_queue,
            )
        )
        logger.debug(
            "Worker channel cleanup dispatcher started: work_pool_id=%s",
            work_pool_id,
        )
        event.set()

    @staticmethod
    def _set_dispatch_event(
        event: asyncio.Event, loop: asyncio.AbstractEventLoop | None
    ) -> None:
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(event.set)
            return
        event.set()

    async def _dispatch_loop(
        self,
        *,
        work_pool_id: UUID,
        cleanup_queue: WorkerCleanupQueue,
    ) -> None:
        try:
            wakeup_sequence = 0

            while True:
                async with self._lock:
                    has_connections = bool(
                        self._connections_by_work_pool_id.get(work_pool_id)
                    )
                    event = self._dispatch_events_by_work_pool_id.get(work_pool_id)
                    if not has_connections or event is None:
                        current_task = asyncio.current_task()
                        if (
                            current_task is not None
                            and self._dispatch_tasks_by_work_pool_id.get(work_pool_id)
                            is current_task
                        ):
                            self._exiting_dispatch_tasks_by_work_pool_id[
                                work_pool_id
                            ] = current_task
                        logger.debug(
                            "Worker channel cleanup dispatcher exiting: "
                            "work_pool_id=%s reason=no_connections",
                            work_pool_id,
                        )
                        return

                try:
                    event.clear()
                    await self.dispatch_available(
                        work_pool_id=work_pool_id,
                        cleanup_queue=cleanup_queue,
                    )

                    wakeup = await self._wait_for_dispatch_wakeup(
                        work_pool_id=work_pool_id,
                        cleanup_queue=cleanup_queue,
                        after=wakeup_sequence,
                        event=event,
                    )
                    if wakeup is not None:
                        wakeup_sequence = wakeup.sequence
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Worker channel cleanup dispatch failed")
                    await asyncio.sleep(_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS)
        finally:
            current_task = asyncio.current_task()
            async with self._lock:
                if (
                    self._dispatch_tasks_by_work_pool_id.get(work_pool_id)
                    is current_task
                ):
                    self._dispatch_tasks_by_work_pool_id.pop(work_pool_id, None)
                    self._exiting_dispatch_tasks_by_work_pool_id.pop(work_pool_id, None)
                    if not self._connections_by_work_pool_id.get(work_pool_id):
                        self._dispatch_events_by_work_pool_id.pop(work_pool_id, None)
                        self._dispatch_loops_by_work_pool_id.pop(work_pool_id, None)
                        self._dispatch_locks.pop(work_pool_id, None)
                elif (
                    self._exiting_dispatch_tasks_by_work_pool_id.get(work_pool_id)
                    is current_task
                ):
                    self._exiting_dispatch_tasks_by_work_pool_id.pop(work_pool_id, None)

    async def _wait_for_dispatch_wakeup(
        self,
        *,
        work_pool_id: UUID,
        cleanup_queue: WorkerCleanupQueue,
        after: int,
        event: asyncio.Event,
    ) -> CleanupQueueWakeup | None:
        queue_task = asyncio.create_task(
            cleanup_queue.wait_for_wakeup(
                work_pool_id,
                after=after,
                timeout=_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS,
            )
        )
        event_task = asyncio.create_task(event.wait())
        done, pending = await asyncio.wait(
            {queue_task, event_task}, return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        if queue_task in done:
            return queue_task.result()
        return None

    async def _eligible_connections(
        self, work_pool_id: UUID
    ) -> tuple[WorkerChannelConnection, ...]:
        async with self._lock:
            connections = tuple(self._connections_by_work_pool_id.get(work_pool_id, ()))
            dispatching = set(self._cleanup_dispatching_by_worker)

        eligible = []
        for connection in connections:
            if self._worker_key(connection) in dispatching:
                continue
            if await connection.has_cleanup_capacity():
                eligible.append(connection)
        return tuple(eligible)

    async def _claim_cleanup_dispatch(
        self, connection: WorkerChannelConnection
    ) -> bool:
        async with self._lock:
            key = self._worker_key(connection)
            if key in self._cleanup_dispatching_by_worker:
                return False
            self._cleanup_dispatching_by_worker.add(key)
            return True

    async def _release_cleanup_dispatch_claim(
        self, connection: WorkerChannelConnection
    ) -> None:
        async with self._lock:
            self._cleanup_dispatching_by_worker.discard(self._worker_key(connection))

    async def _mark_cleanup_dispatched(
        self, connection: WorkerChannelConnection
    ) -> None:
        async with self._lock:
            connections = self._connections_by_work_pool_id.get(connection.work_pool_id)
            if connections is None or len(connections) < 2:
                return

            try:
                index = connections.index(connection)
            except ValueError:
                return

            connections.append(connections.pop(index))

    def _cleanup_in_flight_for_connection_locked(
        self, connection: WorkerChannelConnection
    ) -> dict[str, WorkerCleanupInFlight]:
        return self._cleanup_in_flight_by_worker[self._worker_key(connection)]

    @staticmethod
    def _worker_key(connection: WorkerChannelConnection) -> tuple[UUID, UUID, str]:
        return (connection.work_pool_id, connection.consumer_id, connection.worker_name)

    def _drop_empty_cleanup_in_flight_locked(
        self,
        connection: WorkerChannelConnection,
        in_flight: dict[str, WorkerCleanupInFlight],
    ) -> None:
        if not in_flight:
            self._cleanup_in_flight_by_worker.pop(self._worker_key(connection), None)

    @staticmethod
    def _prune_expired_cleanup_reservations_locked(
        in_flight: dict[str, WorkerCleanupInFlight],
    ) -> None:
        current_time = now("UTC")
        expired_tokens = [
            token
            for token, reservation in in_flight.items()
            if reservation.lease_expires_at <= current_time
        ]
        for token in expired_tokens:
            in_flight.pop(token, None)

    def _prune_expired_cleanup_reservations_for_work_pool_locked(
        self, work_pool_id: UUID
    ) -> None:
        for key, in_flight in tuple(self._cleanup_in_flight_by_worker.items()):
            if key[0] != work_pool_id:
                continue
            self._prune_expired_cleanup_reservations_locked(in_flight)
            if not in_flight:
                self._cleanup_in_flight_by_worker.pop(key, None)


WORKER_CLEANUP_CONNECTION_REGISTRY = WorkerCleanupConnectionRegistry()


__all__ = [
    "WORKER_CLEANUP_CONNECTION_REGISTRY",
    "WorkerCleanupConnectionRegistry",
    "WorkerCleanupInFlight",
]
