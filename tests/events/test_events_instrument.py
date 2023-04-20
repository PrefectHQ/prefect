from typing import Optional

import pytest

from prefect.events.clients import AssertingEventsClient
from prefect.events.instrument import (
    ResourceTuple,
    instrument_method_calls_on_class_instances,
)
from prefect.events.worker import EventsWorker


def test_requires_events_methods_to_be_defined():
    with pytest.raises(RuntimeError, match="Class must define '_event_kind'."):

        @instrument_method_calls_on_class_instances
        class Nope:
            pass


@instrument_method_calls_on_class_instances
class InstrumentedClass:
    _events_excluded_methods = ["excluded_method"]
    not_callable = "some value"

    def _event_kind(self):
        return "prefect.instrumented"

    def _event_method_called_resources(self) -> ResourceTuple:
        return (
            {
                "prefect.resource.id": "prefect.instrumented-class",
            },
            [
                {
                    "prefect.resource.id": "prefect.class.InstrumentedClass",
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


async def test_instruments_methods(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    instance = InstrumentedClass()
    instance.sync_method()
    await instance.async_method()

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 2

    sync_event = asserting_events_worker._client.events[0]
    assert sync_event.event == "prefect.instrumented.sync_method.called"
    assert sync_event.resource.id == "prefect.instrumented-class"
    assert sync_event.related[0].id == "prefect.class.InstrumentedClass"
    assert sync_event.related[0].role == "class"

    async_event = asserting_events_worker._client.events[1]
    assert async_event.event == "prefect.instrumented.async_method.called"
    assert async_event.resource.id == "prefect.instrumented-class"
    assert async_event.related[0].id == "prefect.class.InstrumentedClass"
    assert async_event.related[0].role == "class"


async def test_handles_method_failure(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    instance = InstrumentedClass()

    try:
        instance.sync_fail()
    except Exception:
        pass

    try:
        await instance.async_fail()
    except Exception:
        pass

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 2

    sync_event = asserting_events_worker._client.events[0]
    assert sync_event.event == "prefect.instrumented.sync_fail.failed"
    assert sync_event.resource.id == "prefect.instrumented-class"
    assert sync_event.related[0].id == "prefect.class.InstrumentedClass"
    assert sync_event.related[0].role == "class"

    async_event = asserting_events_worker._client.events[1]
    assert async_event.event == "prefect.instrumented.async_fail.failed"
    assert async_event.resource.id == "prefect.instrumented-class"
    assert async_event.related[0].id == "prefect.class.InstrumentedClass"
    assert async_event.related[0].role == "class"


async def test_ignores_excluded_and_private_methods(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    instance = InstrumentedClass()

    instance.excluded_method()
    instance._private_method()
    InstrumentedClass.static_method()

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 0


async def test_instrument_idempotent(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    class AClass:
        def _event_kind(self):
            return "prefect.a-class"

        def _event_method_called_resources(self) -> ResourceTuple:
            return ({"prefect.resource.id": "some-id"}, [])

        def some_method(self):
            pass

    Instrumented = instrument_method_calls_on_class_instances(AClass)
    InstrumentedTwice = instrument_method_calls_on_class_instances(Instrumented)

    instance = InstrumentedTwice()
    instance.some_method()

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 1


async def test_skip_event_no_resources(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    class AClass:
        def _event_kind(self):
            return "prefect.a-class"

        def _event_method_called_resources(self) -> Optional[ResourceTuple]:
            return None

        def some_method(self):
            pass

    Instrumented = instrument_method_calls_on_class_instances(AClass)

    instance = Instrumented()
    instance.some_method()

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)

    assert len(asserting_events_worker._client.events) == 0
