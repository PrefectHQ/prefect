import asyncio
import atexit
import queue
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional, Type

from prefect._internal.compatibility.experimental import experiment_enabled
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL, PREFECT_CLOUD_API_URL

from .clients import EventsClient, NullEventsClient, PrefectCloudEventsClient
from .schemas import Event


class EventsWorker:
    def __init__(
        self,
        client_type: Type[EventsClient],
        client_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._client_type = client_type
        self._client_kwargs = client_kwargs or {}
        self._client: EventsClient

        self._queue: queue.SimpleQueue[Event] = queue.SimpleQueue()

        self._thread = threading.Thread(
            target=self._start_loop, name="events-worker", daemon=True
        )
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._lock = threading.Lock()

        atexit.register(self.stop)

    def _start_loop(self):
        """Entrypoint for the thread."""
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._main_loop())
        loop.close()

    async def _main_loop(self):
        """Orchestrate the events client and emit any queued events."""
        self._client = self._client_type(**self._client_kwargs)
        async with self._client:
            self._ready_event.set()
            while not self._stop_event.is_set():
                try:
                    event = self._queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.1)
                else:
                    await self._client.emit(event)

    def start(self):
        """Start worker thread if not already started."""
        if not self._thread.is_alive():
            with self._lock:
                self._thread.start()

    def stop(self) -> None:
        """Stop worker thread if started."""
        if self._thread.is_alive():
            with self._lock:
                self._ready_event.clear()
                self._stop_event.set()
                self._thread.join()

    def emit(self, event: Event) -> None:
        """Emit `event` and ensure that the worker thread is running."""
        if not self._thread.is_alive():
            self.start()
        self._queue.put(event)


@asynccontextmanager
async def async_get_events_worker():
    cm = get_events_worker()
    with cm as worker:
        yield worker


@contextmanager
def get_events_worker():
    worker = get_worker_from_run_context()
    manage_lifecycle = False

    if not worker:
        worker = get_worker_from_settings()
        worker.start()
        manage_lifecycle = True

    try:
        yield worker
    finally:
        if manage_lifecycle:
            # The events worker can come from the run context or from settings.
            # In the case of a run context it's assumed that some other code is
            # handling the workers lifecycle and in that case it shouldn't be
            # explicitly stopped here. However if it came from settings then
            # this context manager needs to stop the worker.
            worker.stop()


def get_worker_from_run_context() -> Optional[EventsWorker]:
    import prefect.context

    flow_run_context = prefect.context.FlowRunContext.get()
    if flow_run_context and flow_run_context.events is not None:
        return flow_run_context.events

    return None


def get_worker_from_settings() -> EventsWorker:
    api = PREFECT_API_URL.value()
    if (
        experiment_enabled("events_client")
        and api
        and api.startswith(PREFECT_CLOUD_API_URL.value())
    ):
        return EventsWorker(
            PrefectCloudEventsClient,
            {
                "api_url": PREFECT_CLOUD_API_URL.value(),
                "api_key": PREFECT_API_KEY.value(),
            },
        )
    else:
        return EventsWorker(NullEventsClient)
