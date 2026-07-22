from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import anyio
import pytest
from typing_extensions import Self

import prefect.events.subscribers
from prefect.client.schemas.objects import Log
from prefect.events import Event, Resource
from prefect.events.subscribers import FlowRunSubscriber

ORIGINAL_SHOULD_RESUME = FlowRunSubscriber._should_resume

TERMINAL_FLOW_RUN_EVENTS = {
    "prefect.flow-run.Completed",
    "prefect.flow-run.Failed",
    "prefect.flow-run.Crashed",
}


class MockEventSubscriber:
    """Mock event subscriber for testing"""

    def __init__(self, events: list[Event]):
        self.events = events
        self._index = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Event:
        if self._index >= len(self.events):
            raise StopAsyncIteration
        event = self.events[self._index]
        self._index += 1
        return event


class MockLogsSubscriber:
    """Mock logs subscriber for testing"""

    def __init__(self, logs: list[Log]):
        self.logs = logs
        self._index = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Log:
        if self._index >= len(self.logs):
            raise StopAsyncIteration
        log = self.logs[self._index]
        self._index += 1
        return log


@pytest.fixture
def flow_run_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_log1(flow_run_id: UUID) -> Log:
    """A sample log at T+0s"""
    return Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Test log 1",
        timestamp=datetime.now(timezone.utc),
        flow_run_id=flow_run_id,
    )


@pytest.fixture
def sample_log2(flow_run_id: UUID) -> Log:
    """A sample log at T+2s"""
    return Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Test log 2",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=2),
        flow_run_id=flow_run_id,
    )


@pytest.fixture
def sample_event1(flow_run_id: UUID) -> Event:
    """A sample event at T+1s"""
    return Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=1),
        event="prefect.flow-run.Running",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )


@pytest.fixture
def terminal_event(flow_run_id: UUID) -> Event:
    """A terminal event at T+3s"""
    return Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=3),
        event="prefect.flow-run.Completed",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )


@pytest.fixture
def straggler_log(flow_run_id: UUID) -> Log:
    """A log that arrives after terminal event at T+4s"""
    return Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Straggler log",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=4),
        flow_run_id=flow_run_id,
    )


@pytest.fixture
def setup_mocks(monkeypatch):
    """Setup mocks for get_events_subscriber and get_logs_subscriber"""

    def create_mocks(events: list[Event], logs: list[Log]):
        mock_events = MockEventSubscriber(events)
        mock_logs = MockLogsSubscriber(logs)

        def mock_get_events_subscriber(*args, **kwargs):
            return mock_events

        def mock_get_logs_subscriber(*args, **kwargs):
            return mock_logs

        monkeypatch.setattr(
            prefect.events.subscribers,
            "get_events_subscriber",
            mock_get_events_subscriber,
        )
        monkeypatch.setattr(
            prefect.events.subscribers, "get_logs_subscriber", mock_get_logs_subscriber
        )

    return create_mocks


@pytest.fixture(autouse=True)
def default_streams_do_not_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let finite mock streams stop without exercising resume policy.

    Tests that exercise resume, completion, or failure behavior override this.
    """

    async def _do_not_resume(
        self: FlowRunSubscriber, stream_error: Exception | None = None
    ) -> bool:
        return False

    monkeypatch.setattr(FlowRunSubscriber, "_should_resume", _do_not_resume)


def patch_run_terminal_state(
    monkeypatch: pytest.MonkeyPatch, value: bool | None
) -> None:
    """Force `_flow_run_is_terminal` to a fixed result for a test.

    `True` = finished, `False` = still running (resume), `None` = server
    unreachable (give up and record the error).
    """

    async def _terminal(self: FlowRunSubscriber) -> bool | None:
        return value

    monkeypatch.setattr(FlowRunSubscriber, "_should_resume", ORIGINAL_SHOULD_RESUME)
    monkeypatch.setattr(FlowRunSubscriber, "_flow_run_is_terminal", _terminal)


async def test_flow_run_subscriber_basic_interleaving(
    flow_run_id: UUID,
    sample_log1: Log,
    sample_event1: Event,
    sample_log2: Log,
    setup_mocks,
):
    """Test that FlowRunSubscriber interleaves logs and events"""
    setup_mocks([sample_event1], [sample_log1, sample_log2])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 3
    assert any(isinstance(item, Log) and item.message == "Test log 1" for item in items)
    assert any(isinstance(item, Log) and item.message == "Test log 2" for item in items)
    assert any(
        isinstance(item, Event) and item.event == "prefect.flow-run.Running"
        for item in items
    )


async def test_flow_run_subscriber_terminal_event_stops_events(
    flow_run_id: UUID,
    sample_log1: Log,
    sample_event1: Event,
    terminal_event: Event,
    straggler_log: Log,
    setup_mocks,
):
    """Test that terminal events stop event consumption but allow log stragglers"""
    setup_mocks([sample_event1, terminal_event], [sample_log1, straggler_log])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(
        flow_run_id=flow_run_id, straggler_timeout=1
    ) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 4
    assert any(
        isinstance(item, Event) and item.event == "prefect.flow-run.Running"
        for item in items
    )
    assert any(
        isinstance(item, Event) and item.event == "prefect.flow-run.Completed"
        for item in items
    )
    assert any(isinstance(item, Log) and item.message == "Test log 1" for item in items)
    assert any(
        isinstance(item, Log) and item.message == "Straggler log" for item in items
    )


async def test_flow_run_subscriber_straggler_timeout(
    flow_run_id: UUID,
    terminal_event: Event,
    monkeypatch,
):
    """Test that straggler timeout works after terminal event"""

    class SlowMockLogsSubscriber:
        """Mock logs subscriber that delays to simulate stragglers"""

        def __init__(self):
            self._started = False

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Log:
            if not self._started:
                self._started = True
                await asyncio.sleep(10)
            raise StopAsyncIteration

    mock_events = MockEventSubscriber([terminal_event])
    mock_logs = SlowMockLogsSubscriber()

    def mock_get_events_subscriber(*args, **kwargs):
        return mock_events

    def mock_get_logs_subscriber(*args, **kwargs):
        return mock_logs

    monkeypatch.setattr(
        prefect.events.subscribers, "get_events_subscriber", mock_get_events_subscriber
    )
    monkeypatch.setattr(
        prefect.events.subscribers, "get_logs_subscriber", mock_get_logs_subscriber
    )

    items: list[Log | Event] = []
    async with FlowRunSubscriber(
        flow_run_id=flow_run_id, straggler_timeout=0.5
    ) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 1
    assert isinstance(items[0], Event)
    assert items[0].event == "prefect.flow-run.Completed"


async def test_flow_run_subscriber_empty_streams(flow_run_id: UUID, setup_mocks):
    """Test that FlowRunSubscriber handles empty streams"""
    setup_mocks([], [])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 0


async def test_flow_run_subscriber_context_manager_cleanup(
    flow_run_id: UUID, monkeypatch
):
    """Test that FlowRunSubscriber properly cleans up resources"""

    events_entered = False
    events_exited = False
    logs_entered = False
    logs_exited = False

    class TrackingEventSubscriber:
        async def __aenter__(self) -> Self:
            nonlocal events_entered
            events_entered = True
            return self

        async def __aexit__(self, *args) -> None:
            nonlocal events_exited
            events_exited = True

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Event:
            raise StopAsyncIteration

    class TrackingLogsSubscriber:
        async def __aenter__(self) -> Self:
            nonlocal logs_entered
            logs_entered = True
            return self

        async def __aexit__(self, *args) -> None:
            nonlocal logs_exited
            logs_exited = True

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Log:
            raise StopAsyncIteration

    def mock_get_events_subscriber(*args, **kwargs):
        return TrackingEventSubscriber()

    def mock_get_logs_subscriber(*args, **kwargs):
        return TrackingLogsSubscriber()

    monkeypatch.setattr(
        prefect.events.subscribers, "get_events_subscriber", mock_get_events_subscriber
    )
    monkeypatch.setattr(
        prefect.events.subscribers, "get_logs_subscriber", mock_get_logs_subscriber
    )

    async with FlowRunSubscriber(flow_run_id=flow_run_id):
        assert events_entered
        assert logs_entered
        assert not events_exited
        assert not logs_exited

    assert events_exited
    assert logs_exited


async def test_flow_run_subscriber_records_error_when_events_stream_dies(
    flow_run_id: UUID, monkeypatch
):
    """A websocket failure that persists while the server is unreachable is
    recorded, not swallowed."""
    patch_run_terminal_state(monkeypatch, None)

    class DyingEventSubscriber:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Event:
            raise ConnectionError("events websocket died")

    mock_events = DyingEventSubscriber()
    mock_logs = HangingLogsSubscriber()

    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        lambda *args, **kwargs: mock_events,
    )
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_logs_subscriber",
        lambda *args, **kwargs: mock_logs,
    )

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert items == []
    assert subscriber.flow_completed is False
    assert isinstance(subscriber.error, ConnectionError)
    assert str(subscriber.error) == "events websocket died"


async def test_flow_run_subscriber_stops_when_events_close_and_logs_stay_open(
    flow_run_id: UUID, monkeypatch: pytest.MonkeyPatch
):
    """A cleanly closed stream must not strand an idle sibling stream when the
    server is unreachable."""
    patch_run_terminal_state(monkeypatch, None)

    class ClosedEventSubscriber:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Event:
            raise StopAsyncIteration

    class HangingLogsSubscriber:
        """A logs stream that stays connected but never yields or ends."""

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Log:
            await asyncio.Event().wait()  # never returns
            raise AssertionError("unreachable")

    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        lambda *args, **kwargs: ClosedEventSubscriber(),
    )
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_logs_subscriber",
        lambda *args, **kwargs: HangingLogsSubscriber(),
    )

    items: list[Log | Event] = []
    with anyio.fail_after(1):
        async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
            async for item in subscriber:
                items.append(item)

    assert items == []
    assert subscriber.flow_completed is False
    assert isinstance(subscriber.error, ConnectionError)
    assert str(subscriber.error) == "Flow run events stream closed unexpectedly"


async def test_flow_run_subscriber_no_error_on_clean_completion(
    flow_run_id: UUID,
    sample_event1: Event,
    setup_mocks,
):
    """A clean run that reaches a terminal state records no error"""
    terminal_event = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=3),
        event="prefect.flow-run.Completed",
        resource=Resource(
            root={
                "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                "prefect.state-type": "COMPLETED",
            }
        ),
        payload={},
    )
    setup_mocks([sample_event1, terminal_event], [])

    async with FlowRunSubscriber(
        flow_run_id=flow_run_id, straggler_timeout=1
    ) as subscriber:
        async for _ in subscriber:
            pass

    assert subscriber.flow_completed is True
    assert subscriber.error is None


async def test_flow_run_subscriber_only_terminal_events_stop_consumption(
    flow_run_id: UUID, setup_mocks
):
    """Test that only terminal events stop event consumption"""
    non_terminal_event = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc),
        event="prefect.flow-run.Running",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    another_event = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=1),
        event="prefect.flow-run.Pending",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    setup_mocks([non_terminal_event, another_event], [])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 2
    assert all(isinstance(item, Event) for item in items)


async def test_flow_run_subscriber_terminal_event_for_different_flow_run(
    flow_run_id: UUID, setup_mocks
):
    """Test that terminal events for other flow runs don't stop consumption"""
    other_flow_run_id = uuid4()

    event1 = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc),
        event="prefect.flow-run.Running",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    other_terminal = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=1),
        event="prefect.flow-run.Completed",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{other_flow_run_id}"}
        ),
        payload={},
    )

    event2 = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=2),
        event="prefect.flow-run.Pending",
        resource=Resource(
            root={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
        ),
        payload={},
    )

    setup_mocks([event1, other_terminal, event2], [])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 3


class ScriptedEventSubscriber:
    """Yields events in scripted passes. Each pass ends by raising its
    terminator (`StopAsyncIteration` for a clean close, or another exception
    for a hard failure). Re-iterating advances to the next pass, mirroring how
    `FlowRunSubscriber` resumes a dropped subscription."""

    def __init__(self, passes: list[tuple[list[Event], BaseException]]):
        self._passes = passes
        self._pass_index = -1
        self._item_index = 0
        self.reconnect_calls = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def _reconnect(self) -> None:
        self.reconnect_calls += 1

    def __aiter__(self) -> Self:
        self._pass_index += 1
        self._item_index = 0
        return self

    async def __anext__(self) -> Event:
        if self._pass_index >= len(self._passes):
            raise StopAsyncIteration
        items, terminator = self._passes[self._pass_index]
        if self._item_index < len(items):
            event = items[self._item_index]
            self._item_index += 1
            return event
        raise terminator


class HangingLogsSubscriber:
    """A logs stream that stays connected but never yields or ends."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Log:
        await asyncio.Event().wait()  # never returns
        raise AssertionError("unreachable")


async def test_flow_run_subscriber_resumes_after_stream_drop(
    flow_run_id: UUID,
    sample_event1: Event,
    monkeypatch: pytest.MonkeyPatch,
):
    """A dropped stream is resumed while the run is active, recovering the
    terminal event that was missed when the websocket died."""
    patch_run_terminal_state(monkeypatch, False)  # run still active -> resume

    terminal_event = Event(
        id=uuid4(),
        occurred=datetime.now(timezone.utc) + timedelta(seconds=3),
        event="prefect.flow-run.Completed",
        resource=Resource(
            root={
                "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                "prefect.state-type": "COMPLETED",
            }
        ),
        payload={},
    )

    events = ScriptedEventSubscriber(
        [
            ([sample_event1], StopAsyncIteration()),
            ([terminal_event], StopAsyncIteration()),
        ]
    )

    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        lambda *args, **kwargs: events,
    )
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_logs_subscriber",
        lambda *args, **kwargs: HangingLogsSubscriber(),
    )

    items: list[Log | Event] = []
    async with FlowRunSubscriber(
        flow_run_id=flow_run_id, straggler_timeout=1
    ) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert subscriber.flow_completed is True
    assert subscriber.error is None
    assert events.reconnect_calls == 1
    assert [item.event for item in items if isinstance(item, Event)] == [
        "prefect.flow-run.Running",
        "prefect.flow-run.Completed",
    ]


async def test_flow_run_subscriber_reconnects_closed_logs_stream(
    flow_run_id: UUID,
    sample_log1: Log,
    monkeypatch: pytest.MonkeyPatch,
):
    """A cleanly closed logs stream reconnects before consuming again."""
    patch_run_terminal_state(monkeypatch, False)

    class ResumingLogsSubscriber:
        def __init__(self) -> None:
            self._reconnected = False
            self._delivered = False
            self.reconnect_calls = 0

        async def _reconnect(self) -> None:
            self.reconnect_calls += 1
            self._reconnected = True

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Log:
            if not self._reconnected:
                raise StopAsyncIteration
            if not self._delivered:
                self._delivered = True
                return sample_log1
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    logs = ResumingLogsSubscriber()
    subscriber = FlowRunSubscriber(flow_run_id=flow_run_id)
    subscriber._logs_subscriber = logs
    consumer = asyncio.create_task(subscriber._consume_logs())
    with anyio.fail_after(2):
        assert await subscriber._queue.get() == sample_log1

    consumer.cancel()
    await consumer
    assert logs.reconnect_calls == 1


async def test_flow_run_subscriber_stops_without_error_when_run_finished(
    flow_run_id: UUID,
    sample_event1: Event,
    monkeypatch: pytest.MonkeyPatch,
):
    """If a stream ends without a terminal event but the server reports the
    run as finished, the subscriber stops cleanly without an error."""
    patch_run_terminal_state(monkeypatch, True)  # run already finished

    events = ScriptedEventSubscriber([([sample_event1], StopAsyncIteration())])

    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        lambda *args, **kwargs: events,
    )
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_logs_subscriber",
        lambda *args, **kwargs: HangingLogsSubscriber(),
    )

    items: list[Log | Event] = []
    with anyio.fail_after(2):
        async with FlowRunSubscriber(
            flow_run_id=flow_run_id, straggler_timeout=1
        ) as subscriber:
            async for item in subscriber:
                items.append(item)

    assert subscriber.flow_completed is True
    assert subscriber.error is None
    assert [item.event for item in items if isinstance(item, Event)] == [
        "prefect.flow-run.Running",
    ]
