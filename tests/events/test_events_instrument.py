import time
from typing import Generator
from unittest import mock

import pytest

from prefect.events.clients import AssertingEventsClient
from prefect.events.instrument import (
    ResourceTuple,
    instrument_method_calls_on_class_instances,
)
from prefect.events.worker import EventsWorker


@pytest.fixture(scope="module")
def events_worker() -> Generator[EventsWorker, None, None]:
    worker = EventsWorker(AssertingEventsClient)

    # Mock `get_worker_from_run_context` so that `get_events_worker` context
    # manager doesn't attempt to manage the lifecycle of this worker.
    with mock.patch(
        "prefect.events.worker.get_worker_from_run_context"
    ) as worker_from_context:
        worker_from_context.return_value = worker

        worker.start()
        yield worker
        worker.stop()


@pytest.fixture(autouse=True)
def reset_worker_events(events_worker: EventsWorker):
    assert isinstance(events_worker._client, AssertingEventsClient)
    events_worker._client.events = []


def test_requires_events_methods_to_be_defined():
    with pytest.raises(RuntimeError, match="Class must define '_event_kind'."):

        @instrument_method_calls_on_class_instances()
        class Nope:
            pass


@instrument_method_calls_on_class_instances(exclude_methods=["excluded_method"])
class InstrumentedClass:
    not_callable = "some value"

    def _event_kind(self):
        return "prefect.instrumented"

    def _event_method_called_resources(self, method_name: str) -> ResourceTuple:
        return (
            {
                "prefect.resource.id": f"prefect.some-class.{method_name}",
            },
            [
                {
                    "prefect.resource.id": f"prefect.class.InstrumentedClass",
                    "prefect.resource.role": "class",
                }
            ],
        )

    def excluded_method(self):
        pass

    def sync_method(self):
        pass

    async def async_method(self):
        pass

    def sync_fail(self):
        raise Exception("Sync method failed.")

    async def async_fail(self):
        raise Exception("Async method failed.")

    def _private_method(self):
        pass

    @staticmethod
    def static_method():
        pass


async def test_instruments_methods(events_worker: EventsWorker):
    assert isinstance(events_worker._client, AssertingEventsClient)

    instance = InstrumentedClass()
    instance.sync_method()
    await instance.async_method()

    time.sleep(0.1)

    assert len(events_worker._client.events) == 2

    sync_event = events_worker._client.events[0]
    assert sync_event.resource.id == "prefect.some-class.sync_method"
    assert sync_event.resource["prefect.result"] == "successful"
    assert sync_event.related[0].id == "prefect.class.InstrumentedClass"
    assert sync_event.related[0].role == "class"

    async_event = events_worker._client.events[1]
    assert async_event.resource.id == "prefect.some-class.async_method"
    assert async_event.resource["prefect.result"] == "successful"
    assert async_event.related[0].id == "prefect.class.InstrumentedClass"
    assert async_event.related[0].role == "class"


async def test_handles_method_failure(events_worker: EventsWorker):
    assert isinstance(events_worker._client, AssertingEventsClient)

    instance = InstrumentedClass()

    try:
        instance.sync_fail()
    except:
        pass

    try:
        await instance.async_fail()
    except:
        pass

    time.sleep(0.1)

    assert len(events_worker._client.events) == 2

    sync_event = events_worker._client.events[0]
    assert sync_event.resource.id == "prefect.some-class.sync_fail"
    assert sync_event.resource["prefect.result"] == "failure"
    assert sync_event.related[0].id == "prefect.class.InstrumentedClass"
    assert sync_event.related[0].role == "class"

    async_event = events_worker._client.events[1]
    assert async_event.resource.id == "prefect.some-class.async_fail"
    assert async_event.resource["prefect.result"] == "failure"
    assert async_event.related[0].id == "prefect.class.InstrumentedClass"
    assert async_event.related[0].role == "class"


async def test_ignores_excluded_and_private_methods(events_worker: EventsWorker):
    assert isinstance(events_worker._client, AssertingEventsClient)

    instance = InstrumentedClass()

    instance.excluded_method()
    instance._private_method()
    InstrumentedClass.static_method()

    time.sleep(0.1)

    assert len(events_worker._client.events) == 0


async def test_instrument_idempotent(events_worker: EventsWorker):
    assert isinstance(events_worker._client, AssertingEventsClient)

    class AClass:
        def _event_kind(self):
            return "prefect.a-class"

        def _event_method_called_resources(self, method_name: str) -> ResourceTuple:
            return ({"prefect.resource.id": "some-id"}, [])

        def some_method(self):
            pass

    Instrumented = instrument_method_calls_on_class_instances()(AClass)
    InstrumentedTwice = instrument_method_calls_on_class_instances()(Instrumented)

    instance = InstrumentedTwice()
    instance.some_method()

    time.sleep(0.1)

    assert len(events_worker._client.events) == 1
