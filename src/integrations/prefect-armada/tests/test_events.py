from contextlib import aclosing

from conftest import FakeEventStream, make_event
from prefect_armada.events import (
    get_job_set_events,
    stream_job_set_events,
    wait_for_job_event,
)


async def test_stream_job_set_events_yields_unmarshalled_events(
    armada_credentials, mock_armada_client
):
    stream = FakeEventStream(
        [make_event("submitted"), make_event("running", message_id="2")]
    )
    mock_armada_client.get_job_events_stream.return_value = stream

    events = [
        event
        async for event in stream_job_set_events(
            armada_credentials=armada_credentials,
            queue="test-queue",
            job_set_id="test-job-set",
        )
    ]

    assert [event.type.value for event in events] == ["submitted", "running"]
    assert mock_armada_client.get_job_events_stream.call_args[1] == {
        "queue": "test-queue",
        "job_set_id": "test-job-set",
        "from_message_id": None,
    }
    mock_armada_client.unwatch_events.assert_called_once_with(stream)


async def test_stream_job_set_events_cancels_the_stream_when_closed(
    armada_credentials, mock_armada_client
):
    stream = FakeEventStream([make_event("submitted"), make_event("running")])
    mock_armada_client.get_job_events_stream.return_value = stream

    async with aclosing(
        stream_job_set_events(
            armada_credentials=armada_credentials,
            queue="test-queue",
            job_set_id="test-job-set",
        )
    ) as events:
        async for _ in events:
            break

    mock_armada_client.unwatch_events.assert_called_once_with(stream)


async def test_get_job_set_events_collects_events(
    armada_credentials, mock_armada_client
):
    mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
        [
            make_event("submitted"),
            make_event("running", message_id="2"),
            make_event("succeeded", message_id="3"),
        ]
    )

    events = await get_job_set_events.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
    )

    assert [event.type.value for event in events] == [
        "submitted",
        "running",
        "succeeded",
    ]


async def test_get_job_set_events_filters_by_type(
    armada_credentials, mock_armada_client
):
    mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
        [
            make_event("submitted"),
            make_event("running", message_id="2"),
            make_event("succeeded", message_id="3"),
        ]
    )

    events = await get_job_set_events.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        event_types=["succeeded"],
    )

    assert [event.type.value for event in events] == ["succeeded"]


async def test_get_job_set_events_stops_at_max_events(
    armada_credentials, mock_armada_client
):
    mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
        [make_event("submitted"), make_event("running", message_id="2")],
        hang=True,
    )

    events = await get_job_set_events.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        max_events=1,
    )

    assert len(events) == 1


async def test_get_job_set_events_stops_at_timeout(
    armada_credentials, mock_armada_client
):
    mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
        [make_event("submitted")], hang=True
    )

    events = await get_job_set_events.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        timeout_seconds=0.1,
    )

    assert len(events) == 1


async def test_wait_for_job_event_matches_the_requested_job(
    armada_credentials, mock_armada_client
):
    mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
        [
            make_event("succeeded", job_id="other-job"),
            make_event("succeeded", job_id="my-job", message_id="2"),
        ]
    )

    event = await wait_for_job_event.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        job_id="my-job",
        event_types=["succeeded", "failed"],
    )

    assert event is not None
    assert event.message.job_id == "my-job"


async def test_wait_for_job_event_returns_none_on_timeout(
    armada_credentials, mock_armada_client
):
    mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
        [make_event("running", job_id="my-job")], hang=True
    )

    event = await wait_for_job_event.fn(
        armada_credentials=armada_credentials,
        queue="test-queue",
        job_set_id="test-job-set",
        job_id="my-job",
        event_types=["succeeded"],
        timeout_seconds=0.1,
    )

    assert event is None
