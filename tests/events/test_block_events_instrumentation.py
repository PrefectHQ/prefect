import time

from pydantic import SecretStr

from prefect.blocks.system import Secret
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker


async def test_blocks_instrumented(events_worker: EventsWorker):
    secret = Secret(value=SecretStr("I'm hidden!"))
    await secret.save("top-secret", overwrite=True)
    secret = await Secret.load("top-secret")
    secret.get()

    time.sleep(0.1)

    assert isinstance(events_worker._client, AssertingEventsClient)
    assert len(events_worker._client.events) == 3

    save_event = events_worker._client.events[0]
    assert save_event.resource.id == "prefect.block-document.anonymous.save"
    assert save_event.related[0].id == "prefect.block-type.secret"
    assert save_event.related[0].role == "block-type"

    load_event = events_worker._client.events[1]
    assert load_event.resource.id == "prefect.block-document.top-secret.load"
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"

    get_event = events_worker._client.events[2]
    assert get_event.resource.id == "prefect.block-document.top-secret.get"
    assert get_event.related[0].id == "prefect.block-type.secret"
    assert get_event.related[0].role == "block-type"
