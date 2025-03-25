from __future__ import annotations

import asyncio
import atexit
import threading
import uuid
from typing import (
    TYPE_CHECKING,
    Callable,
)

import anyio
from cachetools import TTLCache
from typing_extensions import Self

from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.threads import get_global_loop
from prefect.client.schemas.objects import (
    TERMINAL_STATES,
)
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.logging import get_logger

if TYPE_CHECKING:
    import logging


class FlowRunWaiter:
    """
    A service used for waiting for a flow run to finish.

    This service listens for flow run events and provides a way to wait for a specific
    flow run to finish. This is useful for waiting for a flow run to finish before
    continuing execution.

    The service is a singleton and must be started before use. The service will
    automatically start when the first instance is created. A single websocket
    connection is used to listen for flow run events.

    The service can be used to wait for a flow run to finish by calling
    `FlowRunWaiter.wait_for_flow_run` with the flow run ID to wait for. The method
    will return when the flow run has finished or the timeout has elapsed.

    The service will automatically stop when the Python process exits or when the
    global loop thread is stopped.

    Example:
    ```python
    import asyncio
    from uuid import uuid4

    from prefect import flow
    from prefect.flow_engine import run_flow_async
    from prefect.flow_runs import FlowRunWaiter


    @flow
    async def test_flow():
        await asyncio.sleep(5)
        print("Done!")


    async def main():
        flow_run_id = uuid4()
        asyncio.create_flow(run_flow_async(flow=test_flow, flow_run_id=flow_run_id))

        await FlowRunWaiter.wait_for_flow_run(flow_run_id)
        print("Flow run finished")


    if __name__ == "__main__":
        asyncio.run(main())
    ```
    """

    _instance: Self | None = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.logger: "logging.Logger" = get_logger("FlowRunWaiter")
        self._consumer_task: asyncio.Task[None] | None = None
        self._observed_completed_flow_runs: TTLCache[uuid.UUID, bool] = TTLCache(
            maxsize=10000, ttl=600
        )
        self._completion_events: dict[uuid.UUID, asyncio.Event] = {}
        self._completion_callbacks: dict[uuid.UUID, Callable[[], None]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._observed_completed_flow_runs_lock = threading.Lock()
        self._completion_events_lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """
        Start the FlowRunWaiter service.
        """
        if self._started:
            return
        self.logger.debug("Starting FlowRunWaiter")
        loop_thread = get_global_loop()

        if not asyncio.get_running_loop() == loop_thread.loop:
            raise RuntimeError("FlowRunWaiter must run on the global loop thread.")

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
                        f"prefect.flow-run.{state.name.title()}"
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
                    flow_run_id = uuid.UUID(
                        event.resource["prefect.resource.id"].replace(
                            "prefect.flow-run.", ""
                        )
                    )

                    with self._observed_completed_flow_runs_lock:
                        # Cache the flow run ID for a short period of time to avoid
                        # unnecessary waits
                        self._observed_completed_flow_runs[flow_run_id] = True
                    with self._completion_events_lock:
                        # Set the event for the flow run ID if it is in the cache
                        # so the waiter can wake up the waiting coroutine
                        if flow_run_id in self._completion_events:
                            self._completion_events[flow_run_id].set()
                        if flow_run_id in self._completion_callbacks:
                            self._completion_callbacks[flow_run_id]()
                except Exception as exc:
                    self.logger.error(f"Error processing event: {exc}")

    def stop(self) -> None:
        """
        Stop the FlowRunWaiter service.
        """
        self.logger.debug("Stopping FlowRunWaiter")
        if self._consumer_task:
            self._consumer_task.cancel()
            self._consumer_task = None
        self.__class__._instance = None
        self._started = False

    @classmethod
    async def wait_for_flow_run(
        cls, flow_run_id: uuid.UUID, timeout: float | None = None
    ) -> None:
        """
        Wait for a flow run to finish.

        Note this relies on a websocket connection to receive events from the server
        and will not work with an ephemeral server.

        Args:
            flow_run_id: The ID of the flow run to wait for.
            timeout: The maximum time to wait for the flow run to
                finish. Defaults to None.
        """
        instance = cls.instance()
        with instance._observed_completed_flow_runs_lock:
            if flow_run_id in instance._observed_completed_flow_runs:
                return

        # Need to create event in loop thread to ensure it can be set
        # from the loop thread
        finished_event = await from_async.wait_for_call_in_loop_thread(
            create_call(asyncio.Event)
        )
        with instance._completion_events_lock:
            # Cache the event for the flow run ID so the consumer can set it
            # when the event is received
            instance._completion_events[flow_run_id] = finished_event

        try:
            # Now check one more time whether the flow run arrived before we start to
            # wait on it, in case it came in while we were setting up the event above.
            with instance._observed_completed_flow_runs_lock:
                if flow_run_id in instance._observed_completed_flow_runs:
                    return

            with anyio.move_on_after(delay=timeout):
                await from_async.wait_for_call_in_loop_thread(
                    create_call(finished_event.wait)
                )
        finally:
            with instance._completion_events_lock:
                # Remove the event from the cache after it has been waited on
                instance._completion_events.pop(flow_run_id, None)

    @classmethod
    def add_done_callback(
        cls, flow_run_id: uuid.UUID, callback: Callable[[], None]
    ) -> None:
        """
        Add a callback to be called when a flow run finishes.

        Args:
            flow_run_id: The ID of the flow run to wait for.
            callback: The callback to call when the flow run finishes.
        """
        instance = cls.instance()
        with instance._observed_completed_flow_runs_lock:
            if flow_run_id in instance._observed_completed_flow_runs:
                callback()
                return

        with instance._completion_events_lock:
            # Cache the event for the flow run ID so the consumer can set it
            # when the event is received
            instance._completion_callbacks[flow_run_id] = callback

    @classmethod
    def instance(cls) -> Self:
        """
        Get the singleton instance of FlowRunWaiter.
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
