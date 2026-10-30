from __future__ import annotations

import asyncio
import atexit
import threading
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self

import anyio
from cachetools import TTLCache

from prefect._internal._observation_delivery import (
    STABLE_CONNECTION_SECONDS,
    ObservationDelivery,
    reconnect_delay,
)
from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.threads import get_global_loop
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    TaskRunFilter,
    TaskRunFilterId,
    TaskRunFilterState,
    TaskRunFilterStateType,
)
from prefect.client.schemas.objects import TERMINAL_STATES
from prefect.client.schemas.sorting import TaskRunSort
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.events.schemas.events import Event
from prefect.logging.loggers import get_logger
from prefect.states import State

if TYPE_CHECKING:
    import logging

# How often to read the task runs being waited on while the events stream is down
TASK_RUN_POLLING_INTERVAL_SECONDS = 10.0


class TaskRunWaiter:
    """
    A service used for waiting for a task run to finish.

    This service listens for task run events and provides a way to wait for a specific
    task run to finish. This is useful for waiting for a task run to finish before
    continuing execution.

    The service is a singleton and must be started before use. The service will
    automatically start when the first instance is created. A single websocket
    connection is used to listen for task run events.

    The service can be used to wait for a task run to finish by calling
    `TaskRunWaiter.wait_for_task_run` with the task run ID to wait for. The method
    will return when the task run has finished or the timeout has elapsed.

    The service will automatically stop when the Python process exits or when the
    global loop thread is stopped.

    Example:
    ```python
    import asyncio
    from uuid import uuid4

    from prefect import task
    from prefect.task_engine import run_task_async
    from prefect.task_runs import TaskRunWaiter


    @task
    async def test_task():
        await asyncio.sleep(5)
        print("Done!")


    async def main():
        task_run_id = uuid4()
        asyncio.create_task(run_task_async(task=test_task, task_run_id=task_run_id))

        await TaskRunWaiter.wait_for_task_run(task_run_id)
        print("Task run finished")


    if __name__ == "__main__":
        asyncio.run(main())
    ```
    """

    _instance: Self | None = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.logger: logging.Logger = get_logger("TaskRunWaiter")
        self._consumer_task: asyncio.Task[None] | None = None
        self._observed_completed_task_runs: TTLCache[uuid.UUID, State[Any] | None] = (
            TTLCache(maxsize=10000, ttl=600)
        )
        self._completion_events: dict[uuid.UUID, asyncio.Event] = {}
        self._completion_callbacks: dict[uuid.UUID, Callable[[], None]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._observed_completed_task_runs_lock = threading.Lock()
        self._completion_events_lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """
        Start the TaskRunWaiter service.
        """
        if self._started:
            return
        self.logger.debug("Starting TaskRunWaiter")
        loop_thread = get_global_loop()

        if not asyncio.get_running_loop() == loop_thread.loop:
            raise RuntimeError("TaskRunWaiter must run on the global loop thread.")

        self._loop = loop_thread.loop
        if TYPE_CHECKING:
            assert self._loop is not None

        self._consumer_task = self._loop.create_task(self._deliver_events())

        loop_thread.add_shutdown_call(create_call(self.stop))
        atexit.register(self.stop)
        self._started = True

    async def _deliver_events(self) -> None:
        """
        Deliver terminal task run events for the lifetime of the service.

        `ObservationDelivery` keeps the events stream alive and polls the task runs
        being waited on while it is down. If it gives up, it is restarted with
        backoff so that waits in this process do not hang.
        """
        loop = asyncio.get_running_loop()
        failed_attempts = 0
        unavailable = asyncio.Event()
        while True:
            unavailable.clear()
            delivery = ObservationDelivery(
                name="TaskRunWaiter",
                logger=self.logger,
                subscriber_factory=lambda: get_events_subscriber(
                    filter=EventFilter(
                        event=EventNameFilter(
                            name=[
                                f"prefect.task-run.{state.name.title()}"
                                for state in TERMINAL_STATES
                            ],
                        )
                    ),
                    reconnection_attempts=0,
                ),
                on_event=self._handle_event,
                check_current_state=self._check_waited_task_runs,
                on_unavailable=lambda _: unavailable.set(),
                polling_interval=TASK_RUN_POLLING_INTERVAL_SECONDS,
            )
            started_at = loop.time()
            try:
                await delivery.start()
                await unavailable.wait()
            finally:
                await delivery.stop()

            if loop.time() - started_at >= STABLE_CONNECTION_SECONDS:
                failed_attempts = 0
            delay = reconnect_delay(failed_attempts)
            failed_attempts += 1
            self.logger.error(
                "TaskRunWaiter lost both the events stream and the API. Restarting"
                " in %.1f seconds.",
                delay,
            )
            await asyncio.sleep(delay)

    def _handle_event(self, event: Event) -> None:
        try:
            self.logger.debug(
                f"Received event: {event.resource['prefect.resource.id']}"
            )
            task_run_id = uuid.UUID(
                event.resource["prefect.resource.id"].replace("prefect.task-run.", "")
            )

            # Extract the state from the event
            # All events should have validated_state since we don't support
            # new clients with old servers
            state_data = State.model_validate(
                {
                    "id": event.id,
                    "timestamp": event.occurred,
                    **event.payload["validated_state"],
                }
            )
            state_data.state_details.task_run_id = task_run_id

            self._mark_task_run_finished(task_run_id, state_data)
        except Exception as exc:
            self.logger.error(f"Error processing event: {exc}")

    async def _check_waited_task_runs(self) -> None:
        """
        Read the task runs being waited on and release any that have finished.

        Used while the events stream is down and after it reconnects, since a new
        subscription only replays recent events.
        """
        with self._completion_events_lock:
            task_run_ids = list(
                self._completion_events.keys() | self._completion_callbacks.keys()
            )
        if not task_run_ids:
            return

        task_run_filter = TaskRunFilter(
            id=TaskRunFilterId(any_=task_run_ids),
            state=TaskRunFilterState(
                type=TaskRunFilterStateType(any_=list(TERMINAL_STATES))
            ),
        )
        async with get_client() as client:
            offset = 0
            while task_runs := await client.read_task_runs(
                task_run_filter=task_run_filter, sort=TaskRunSort.ID_DESC, offset=offset
            ):
                offset += len(task_runs)
                for task_run in task_runs:
                    if task_run.state is not None and task_run.state.is_final():
                        self._mark_task_run_finished(task_run.id, task_run.state)

    def _mark_task_run_finished(
        self, task_run_id: uuid.UUID, state: State[Any]
    ) -> None:
        with self._observed_completed_task_runs_lock:
            # Cache the state for a short period of time to avoid
            # unnecessary waits
            self._observed_completed_task_runs[task_run_id] = state
        with self._completion_events_lock:
            # Set the event for the task run ID if it is in the cache
            # so the waiter can wake up the waiting coroutine
            if task_run_id in self._completion_events:
                self._completion_events[task_run_id].set()
            callback = self._completion_callbacks.pop(task_run_id, None)
        if callback is not None:
            try:
                callback()
            except Exception:
                self.logger.exception(
                    "Error in done callback for task run %s", task_run_id
                )

    def stop(self) -> None:
        """
        Stop the TaskRunWaiter service.
        """
        self.logger.debug("Stopping TaskRunWaiter")
        if self._consumer_task:
            self._consumer_task.cancel()
            self._consumer_task = None
        self.__class__._instance = None
        self._started = False

    @classmethod
    async def wait_for_task_run(
        cls, task_run_id: uuid.UUID, timeout: float | None = None
    ) -> State[Any] | None:
        """
        Wait for a task run to finish and return its final state.

        Note this relies on a websocket connection to receive events from the server
        and will not work with an ephemeral server.

        Args:
            task_run_id: The ID of the task run to wait for.
            timeout: The maximum time to wait for the task run to
                finish. Defaults to None.

        Returns:
            The final state of the task run if available, None otherwise.
        """
        instance = cls.instance()
        with instance._observed_completed_task_runs_lock:
            if task_run_id in instance._observed_completed_task_runs:
                return instance._observed_completed_task_runs[task_run_id]

        # Need to create event in loop thread to ensure it can be set
        # from the loop thread
        finished_event = await from_async.wait_for_call_in_loop_thread(
            create_call(asyncio.Event)
        )
        with instance._completion_events_lock:
            # Cache the event for the task run ID so the consumer can set it
            # when the event is received
            instance._completion_events[task_run_id] = finished_event

        try:
            # Now check one more time whether the task run arrived before we start to
            # wait on it, in case it came in while we were setting up the event above.
            with instance._observed_completed_task_runs_lock:
                if task_run_id in instance._observed_completed_task_runs:
                    return instance._observed_completed_task_runs[task_run_id]

            with anyio.move_on_after(delay=timeout):
                await from_async.wait_for_call_in_loop_thread(
                    create_call(finished_event.wait)
                )

            # After waiting, retrieve the state from the cache
            with instance._observed_completed_task_runs_lock:
                return instance._observed_completed_task_runs.get(task_run_id)
        finally:
            with instance._completion_events_lock:
                # Remove the event from the cache after it has been waited on
                instance._completion_events.pop(task_run_id, None)

    @classmethod
    def add_done_callback(
        cls, task_run_id: uuid.UUID, callback: Callable[[], None]
    ) -> None:
        """
        Add a callback to be called when a task run finishes.

        Args:
            task_run_id: The ID of the task run to wait for.
            callback: The callback to call when the task run finishes.
        """
        instance = cls.instance()
        with instance._observed_completed_task_runs_lock:
            if task_run_id in instance._observed_completed_task_runs:
                callback()
                return

        with instance._completion_events_lock:
            # Cache the event for the task run ID so the consumer can set it
            # when the event is received
            instance._completion_callbacks[task_run_id] = callback

    @classmethod
    def instance(cls) -> Self:
        """
        Get the singleton instance of TaskRunWaiter.
        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls._new_instance()
            return cls._instance

    @classmethod
    def _new_instance(cls):
        instance = cls()

        if threading.get_ident() == get_global_loop().thread.ident:
            instance.start()
        else:
            from_sync.call_soon_in_loop_thread(create_call(instance.start)).result()

        return instance
