from __future__ import annotations

import asyncio
import atexit
import threading
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import anyio
from cachetools import TTLCache
from typing_extensions import Self

from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.threads import get_global_loop
from prefect.client.schemas.objects import TERMINAL_STATES
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.logging.loggers import get_logger
from prefect.states import State

if TYPE_CHECKING:
    import logging


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

    _instance: Optional[Self] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.logger: "logging.Logger" = get_logger("TaskRunWaiter")
        self._consumer_task: "asyncio.Task[None] | None" = None
        self._observed_completed_task_runs: TTLCache[
            uuid.UUID, Optional[State[Any]]
        ] = TTLCache(maxsize=10000, ttl=600)
        self._completion_events: Dict[uuid.UUID, asyncio.Event] = {}
        self._completion_callbacks: Dict[uuid.UUID, Callable[[], None]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
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

        consumer_started = asyncio.Event()
        self._consumer_task = self._loop.create_task(
            self._consume_events(consumer_started)
        )
        asyncio.run_coroutine_threadsafe(consumer_started.wait(), self._loop)

        loop_thread.add_shutdown_call(create_call(self.stop))
        atexit.register(self.stop)
        self._started = True

    async def _consume_events(self, consumer_started: asyncio.Event):
        async with get_events_subscriber(
            filter=EventFilter(
                event=EventNameFilter(
                    name=[
                        f"prefect.task-run.{state.name.title()}"
                        for state in TERMINAL_STATES
                    ],
                )
            )
        ) as subscriber:
            consumer_started.set()
            async for event in subscriber:
                try:
                    self.logger.debug(
                        f"Received event: {event.resource['prefect.resource.id']}"
                    )
                    task_run_id = uuid.UUID(
                        event.resource["prefect.resource.id"].replace(
                            "prefect.task-run.", ""
                        )
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

                    with self._observed_completed_task_runs_lock:
                        # Cache the state for a short period of time to avoid
                        # unnecessary waits
                        self._observed_completed_task_runs[task_run_id] = state_data
                    with self._completion_events_lock:
                        # Set the event for the task run ID if it is in the cache
                        # so the waiter can wake up the waiting coroutine
                        if task_run_id in self._completion_events:
                            self._completion_events[task_run_id].set()
                        if task_run_id in self._completion_callbacks:
                            self._completion_callbacks[task_run_id]()
                except Exception as exc:
                    self.logger.error(f"Error processing event: {exc}")

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
        cls, task_run_id: uuid.UUID, timeout: Optional[float] = None
    ) -> Optional[State[Any]]:
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
