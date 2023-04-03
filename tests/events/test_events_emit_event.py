from uuid import UUID

from prefect.events import emit_event
from prefect.events.worker import EventsWorker
from prefect.server.utilities.schemas import DateTimeTZ


def test_emits_simple_event(asserting_events_worker: EventsWorker, reset_worker_events):
    emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
    )

    asserting_events_worker.drain()

    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "vogon.poetry.read"
    assert event.resource.id == "vogon.poem.oh-freddled-gruntbuggly"


def test_emits_complex_event(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
        occurred=DateTimeTZ(2023, 3, 1, 12, 39, 28),
        related=[
            {
                "prefect.resource.id": "vogon.ship.the-business-end",
                "prefect.resource.role": "locale",
            }
        ],
        payload={"text": "Oh freddled gruntbuggly..."},
        id=UUID(int=1),
    )

    asserting_events_worker.drain()

    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "vogon.poetry.read"
    assert event.resource.id == "vogon.poem.oh-freddled-gruntbuggly"
    assert event.occurred == DateTimeTZ(2023, 3, 1, 12, 39, 28)
    assert len(event.related) == 1
    assert event.related[0].id == "vogon.ship.the-business-end"
    assert event.related[0].role == "locale"
    assert event.payload == {"text": "Oh freddled gruntbuggly..."}
    assert event.id == UUID(int=1)
