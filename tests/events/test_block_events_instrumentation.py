import time

from pydantic import SecretStr

from prefect.blocks.system import Secret
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker


async def test_async_blocks_instrumented(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    secret = Secret(value=SecretStr("I'm hidden!"))
    await secret.save("top-secret", overwrite=True)
    secret = await Secret.load("top-secret")
    secret.get()

    time.sleep(0.1)

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 3

    save_event = asserting_events_worker._client.events[0]
    assert save_event.resource.id == "prefect.block-document.top-secret.save"
    assert save_event.related[0].id == "prefect.block-type.secret"
    assert save_event.related[0].role == "block-type"

    load_event = asserting_events_worker._client.events[1]
    assert load_event.resource.id == "prefect.block-document.top-secret.load"
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"

    get_event = asserting_events_worker._client.events[2]
    assert get_event.resource.id == "prefect.block-document.top-secret.get"
    assert get_event.related[0].id == "prefect.block-type.secret"
    assert get_event.related[0].role == "block-type"


def test_sync_blocks_instrumented(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    secret = Secret(value=SecretStr("I'm hidden!"))
    secret.save("top-secret", overwrite=True)
    secret = Secret.load("top-secret")
    secret.get()

    time.sleep(0.1)

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 3

    save_event = asserting_events_worker._client.events[0]
    assert save_event.resource.id == "prefect.block-document.top-secret.save"
    assert save_event.related[0].id == "prefect.block-type.secret"
    assert save_event.related[0].role == "block-type"

    load_event = asserting_events_worker._client.events[1]
    assert load_event.resource.id == "prefect.block-document.top-secret.load"
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"

    get_event = asserting_events_worker._client.events[2]
    assert get_event.resource.id == "prefect.block-document.top-secret.get"
    assert get_event.related[0].id == "prefect.block-type.secret"
    assert get_event.related[0].role == "block-type"
