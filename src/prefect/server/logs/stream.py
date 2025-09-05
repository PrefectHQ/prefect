"""
Log streaming for live log distribution via websockets.
"""

from __future__ import annotations

import asyncio
from asyncio import Queue
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    AsyncIterable,
    NoReturn,
)

from prefect.logging import get_logger
from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import LogFilter
from prefect.server.services.base import RunInEphemeralServers, RunInWebservers, Service
from prefect.server.utilities import messaging
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

subscribers: set["Queue[Log]"] = set()
filters: dict["Queue[Log]", LogFilter] = {}

# The maximum number of messages that can be waiting for one subscriber, after which
# new messages will be dropped
SUBSCRIPTION_BACKLOG = 256


@asynccontextmanager
async def subscribed(
    filter: LogFilter,
) -> AsyncGenerator["Queue[Log]", None]:
    """
    Subscribe to a stream of logs matching the given filter.

    Args:
        filter: The log filter to apply

    Yields:
        A queue that will receive matching logs
    """
    queue: "Queue[Log]" = Queue(maxsize=SUBSCRIPTION_BACKLOG)

    subscribers.add(queue)
    filters[queue] = filter

    try:
        yield queue
    finally:
        subscribers.remove(queue)
        del filters[queue]


@asynccontextmanager
async def logs(
    filter: LogFilter,
) -> AsyncGenerator[AsyncIterable[Log | None], None]:
    """
    Create a stream of logs matching the given filter.

    Args:
        filter: The log filter to apply

    Yields:
        An async iterable of logs (or None for timeouts)
    """
    async with subscribed(filter) as queue:

        async def consume() -> AsyncGenerator[Log | None, None]:
            while True:
                # Use a brief timeout to allow for cancellation, especially when a
                # client disconnects. Without a timeout here, a consumer may block
                # forever waiting for a message to be put on the queue, and never notice
                # that their client (like a websocket) has actually disconnected.
                try:
                    log = await asyncio.wait_for(queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    # If the queue is empty, we'll yield to the caller with a None in
                    # order to give it control over what happens next. This helps with
                    # the outbound websocket, where we want to check if the client is
                    # still connected periodically.
                    yield None
                    continue

                yield log

        yield consume()


def log_matches_filter(log: Log, filter: LogFilter) -> bool:
    """
    Check if a log matches the given filter criteria.

    Args:
        log: The log to check
        filter: The filter to apply

    Returns:
        True if the log matches the filter, False otherwise
    """
    # Check level filter
    if filter.level:
        if filter.level.ge_ is not None and log.level < filter.level.ge_:
            return False
        if filter.level.le_ is not None and log.level > filter.level.le_:
            return False

    # Check timestamp filter
    if filter.timestamp:
        if (
            filter.timestamp.before_ is not None
            and log.timestamp > filter.timestamp.before_
        ):
            return False
        if (
            filter.timestamp.after_ is not None
            and log.timestamp < filter.timestamp.after_
        ):
            return False

    # Check flow_run_id filter
    if filter.flow_run_id:
        if filter.flow_run_id.any_ is not None:
            if log.flow_run_id not in filter.flow_run_id.any_:
                return False

    # Check task_run_id filter
    if filter.task_run_id:
        if filter.task_run_id.any_ is not None:
            if log.task_run_id not in filter.task_run_id.any_:
                return False
        if filter.task_run_id.is_null_ is not None:
            is_null = log.task_run_id is None
            if filter.task_run_id.is_null_ != is_null:
                return False

    return True


@asynccontextmanager
async def distributor() -> AsyncGenerator[messaging.MessageHandler, None]:
    """
    Create a message handler that distributes logs to subscribed clients.

    Yields:
        A message handler function
    """

    async def message_handler(message: messaging.Message):
        assert message.data

        try:
            assert message.attributes
        except Exception:
            return

        if subscribers:
            try:
                log = Log.model_validate_json(message.data)
            except Exception as e:
                logger.warning(f"Failed to parse log message: {e}")
                return

            for queue in subscribers:
                filter = filters[queue]
                if not log_matches_filter(log, filter):
                    continue

                try:
                    queue.put_nowait(log)
                except asyncio.QueueFull:
                    continue

    yield message_handler


_distributor_task: asyncio.Task[None] | None = None
_distributor_started: asyncio.Event | None = None


async def start_distributor() -> None:
    """Starts the distributor consumer as a global background task"""
    global _distributor_task
    global _distributor_started
    if _distributor_task:
        return

    _distributor_started = asyncio.Event()
    _distributor_task = asyncio.create_task(run_distributor(_distributor_started))
    await _distributor_started.wait()


async def stop_distributor() -> None:
    """Stops the distributor consumer global background task"""
    global _distributor_task
    global _distributor_started
    if not _distributor_task:
        return

    task = _distributor_task
    _distributor_task = None
    _distributor_started = None

    task.cancel()
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        pass


class LogDistributor(RunInEphemeralServers, RunInWebservers, Service):
    """Service for distributing logs to websocket subscribers"""

    name: str = "LogDistributor"

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        raise NotImplementedError("LogDistributor does not have settings")

    @classmethod
    def environment_variable_name(cls) -> str:
        return "PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED"

    @classmethod
    def enabled(cls) -> bool:
        return get_current_settings().server.logs.stream_out_enabled

    async def start(self) -> NoReturn:
        await start_distributor()
        try:
            # start_distributor should have set _distributor_task
            assert _distributor_task is not None
            await _distributor_task
        except asyncio.CancelledError:
            pass

        # This should never be reached due to the infinite loop above
        raise RuntimeError("LogDistributor service unexpectedly terminated")

    async def stop(self) -> None:
        await stop_distributor()


async def run_distributor(started: asyncio.Event) -> NoReturn:
    """Runs the distributor consumer forever until it is cancelled"""
    global _distributor_started
    async with messaging.ephemeral_subscription(
        topic="logs",
    ) as create_consumer_kwargs:
        started.set()
        async with distributor() as handler:
            consumer = messaging.create_consumer(**create_consumer_kwargs)
            await consumer.run(
                handler=handler,
            )

    # This should never be reached due to the infinite nature of consumer.run()
    raise RuntimeError("Log distributor consumer unexpectedly terminated")
