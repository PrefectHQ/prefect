import uuid
from unittest import mock
from unittest.mock import AsyncMock

from pydantic import SecretStr

from prefect.blocks.notifications import PagerDutyWebHook
from prefect.blocks.system import Secret
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.flows import flow


async def test_async_blocks_instrumented(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    block_name = f"top-secret-{uuid.uuid4()}"
    secret = Secret(value=SecretStr("I'm hidden!"))
    document_id = await secret.save(block_name, overwrite=True)
    secret = await Secret.load(block_name)
    secret.get()

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1

    load_event = asserting_events_worker._client.events[0]
    assert load_event.event == "prefect.block.secret.loaded"
    assert load_event.resource.id == f"prefect.block-document.{document_id}"
    assert load_event.resource["prefect.resource.name"] == block_name
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"


def test_sync_blocks_instrumented(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    document_id = None
    block_name = f"top-secret-{uuid.uuid4()}"

    @flow
    def test_flow():
        nonlocal document_id
        secret = Secret(value=SecretStr("I'm hidden!"))
        document_id = secret.save(block_name, overwrite=True)
        secret = Secret.load(block_name)
        secret.get()

    test_flow()

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1

    load_event = asserting_events_worker._client.events[0]
    assert load_event.event == "prefect.block.secret.loaded"
    assert load_event.resource.id == f"prefect.block-document.{document_id}"
    assert load_event.resource["prefect.resource.name"] == block_name
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"


def test_notifications_notify_instrumented_sync(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    with mock.patch("apprise.Apprise", autospec=True) as AppriseMock:
        apprise_instance_mock = AppriseMock.return_value
        apprise_instance_mock.async_notify = AsyncMock()

        document_id = None
        block_name = f"pager-duty-events-{uuid.uuid4()}"

        @flow
        def test_flow():
            nonlocal document_id
            block = PagerDutyWebHook(
                integration_key=SecretStr("integration_key"),
                api_key=SecretStr("api_key"),
            )
            document_id = block.save(block_name, overwrite=True)

            pgduty = PagerDutyWebHook.load(block_name)
            pgduty.notify("Oh, we're you sleeping?")

        test_flow()

        asserting_events_worker.drain()

        assert isinstance(asserting_events_worker._client, AssertingEventsClient)
        assert len(asserting_events_worker._client.events) == 1

        load_event = asserting_events_worker._client.events[0]
        assert load_event.event == "prefect.block.pager-duty-webhook.loaded"
        assert load_event.resource.id == f"prefect.block-document.{document_id}"
        assert load_event.resource["prefect.resource.name"] == block_name
        assert load_event.related[0].id == "prefect.block-type.pager-duty-webhook"
        assert load_event.related[0].role == "block-type"


async def test_notifications_notify_instrumented_async(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    with mock.patch("apprise.Apprise", autospec=True) as AppriseMock:
        apprise_instance_mock = AppriseMock.return_value
        apprise_instance_mock.async_notify = AsyncMock()

        block_name = f"pager-duty-events-{uuid.uuid4()}"
        block = PagerDutyWebHook(
            integration_key=SecretStr("integration_key"), api_key=SecretStr("api_key")
        )
        document_id = await block.save(block_name, overwrite=True)

        pgduty = await PagerDutyWebHook.load(block_name)
        await pgduty.notify("Oh, we're you sleeping?")

        await asserting_events_worker.drain()

        assert isinstance(asserting_events_worker._client, AssertingEventsClient)
        assert len(asserting_events_worker._client.events) == 1

        load_event = asserting_events_worker._client.events[0]
        assert load_event.event == "prefect.block.pager-duty-webhook.loaded"
        assert load_event.resource.id == f"prefect.block-document.{document_id}"
        assert load_event.resource["prefect.resource.name"] == block_name
        assert load_event.related[0].id == "prefect.block-type.pager-duty-webhook"
        assert load_event.related[0].role == "block-type"
