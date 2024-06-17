from unittest import mock

from pydantic import SecretStr

from prefect.blocks.notifications import PagerDutyWebHook
from prefect.blocks.system import Secret
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.flows import flow
from prefect.testing.utilities import AsyncMock


async def test_async_blocks_instrumented(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    secret = Secret(value=SecretStr("I'm hidden!"))
    document_id = await secret.save("top-secret", overwrite=True)
    secret = await Secret.load("top-secret")
    secret.get()

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1

    load_event = asserting_events_worker._client.events[0]
    assert load_event.event == "prefect.block.secret.loaded"
    assert load_event.resource.id == f"prefect.block-document.{document_id}"
    assert load_event.resource["prefect.resource.name"] == "top-secret"
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"


def test_sync_blocks_instrumented(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    document_id = None

    @flow
    def test_flow():
        nonlocal document_id
        secret = Secret(value=SecretStr("I'm hidden!"))
        document_id = secret.save("top-secret", overwrite=True)
        secret = Secret.load("top-secret")
        secret.get()

    test_flow()

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1

    load_event = asserting_events_worker._client.events[0]
    assert load_event.event == "prefect.block.secret.loaded"
    assert load_event.resource.id == f"prefect.block-document.{document_id}"
    assert load_event.resource["prefect.resource.name"] == "top-secret"
    assert load_event.related[0].id == "prefect.block-type.secret"
    assert load_event.related[0].role == "block-type"


def test_notifications_notify_instrumented_sync(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    with mock.patch("apprise.Apprise", autospec=True) as AppriseMock:
        apprise_instance_mock = AppriseMock.return_value
        apprise_instance_mock.async_notify = AsyncMock()

        document_id = None

        @flow
        def test_flow():
            nonlocal document_id
            block = PagerDutyWebHook(
                integration_key=SecretStr("integration_key"),
                api_key=SecretStr("api_key"),
            )
            document_id = block.save("pager-duty-events", overwrite=True)

            pgduty = PagerDutyWebHook.load("pager-duty-events")
            pgduty.notify("Oh, we're you sleeping?")

        test_flow()

        asserting_events_worker.drain()

        assert isinstance(asserting_events_worker._client, AssertingEventsClient)
        assert len(asserting_events_worker._client.events) == 1

        load_event = asserting_events_worker._client.events[0]
        assert load_event.event == "prefect.block.pager-duty-webhook.loaded"
        assert load_event.resource.id == f"prefect.block-document.{document_id}"
        assert load_event.resource["prefect.resource.name"] == "pager-duty-events"
        assert load_event.related[0].id == "prefect.block-type.pager-duty-webhook"
        assert load_event.related[0].role == "block-type"


async def test_notifications_notify_instrumented_async(
    asserting_events_worker: EventsWorker, reset_worker_events
):
    with mock.patch("apprise.Apprise", autospec=True) as AppriseMock:
        apprise_instance_mock = AppriseMock.return_value
        apprise_instance_mock.async_notify = AsyncMock()

        block = PagerDutyWebHook(
            integration_key=SecretStr("integration_key"), api_key=SecretStr("api_key")
        )
        document_id = await block.save("pager-duty-events", overwrite=True)

        pgduty = await PagerDutyWebHook.load("pager-duty-events")
        await pgduty.notify("Oh, we're you sleeping?")

        await asserting_events_worker.drain()

        assert isinstance(asserting_events_worker._client, AssertingEventsClient)
        assert len(asserting_events_worker._client.events) == 1

        load_event = asserting_events_worker._client.events[0]
        assert load_event.event == "prefect.block.pager-duty-webhook.loaded"
        assert load_event.resource.id == f"prefect.block-document.{document_id}"
        assert load_event.resource["prefect.resource.name"] == "pager-duty-events"
        assert load_event.related[0].id == "prefect.block-type.pager-duty-webhook"
        assert load_event.related[0].role == "block-type"
