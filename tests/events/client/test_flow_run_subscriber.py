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

TERMINAL_FLOW_RUN_EVENTS = {
    "prefect.flow-run.Completed",
    "prefect.flow-run.Failed",
    "prefect.flow-run.Crashed",
}


class MockEventSubscriber:
    """Mock event subscriber for testing"""

    def __init__(self, events: list[Event], stop_when_exhausted: bool = False):
        self.events = events
        self._index = 0
        self._stop_when_exhausted = stop_when_exhausted

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Event:
        if self._index >= len(self.events):
            if self._stop_when_exhausted:
                raise StopAsyncIteration
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        event = self.events[self._index]
        self._index += 1
        return event


class MockLogsSubscriber:
    """Mock logs subscriber for testing"""

    def __init__(self, logs: list[Log], stop_when_exhausted: bool = False):
        self.logs = logs
        self._index = 0
        self._stop_when_exhausted = stop_when_exhausted

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Log:
        if self._index >= len(self.logs):
            if self._stop_when_exhausted:
                raise StopAsyncIteration
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        log = self.logs[self._index]
        self._index += 1
        return log


class HangingLogsSubscriber:
    """A logs stream that stays connected but never yields or ends."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Log:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


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
            root={
                "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                "prefect.state-type": "COMPLETED",
            }
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

    def create_mocks(
        events: list[Event],
        logs: list[Log],
        stop_when_exhausted: bool = False,
    ):
        mock_events = MockEventSubscriber(events, stop_when_exhausted)
        mock_logs = MockLogsSubscriber(logs, stop_when_exhausted)

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


async def test_flow_run_subscriber_basic_interleaving(
    flow_run_id: UUID,
    sample_log1: Log,
    sample_event1: Event,
    sample_log2: Log,
    terminal_event: Event,
    setup_mocks,
):
    """Test that FlowRunSubscriber interleaves logs and events until completion"""
    setup_mocks([sample_event1, terminal_event], [sample_log1, sample_log2])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 4
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
    """Test that empty streams are treated as premature termination"""
    setup_mocks([], [], stop_when_exhausted=True)

    with pytest.raises(ConnectionError, match="stream closed unexpectedly"):
        async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
            await anext(subscriber)


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


async def test_flow_run_subscriber_reconnects_lower_level_streams_on_clean_close(
    flow_run_id: UUID, monkeypatch: pytest.MonkeyPatch
):
    event_kwargs: dict[str, object] = {}
    log_kwargs: dict[str, object] = {}

    def mock_get_events_subscriber(*args, **kwargs):
        event_kwargs.update(kwargs)
        return MockEventSubscriber([])

    def mock_get_logs_subscriber(*args, **kwargs):
        log_kwargs.update(kwargs)
        return MockLogsSubscriber([])

    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        mock_get_events_subscriber,
    )
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_logs_subscriber",
        mock_get_logs_subscriber,
    )

    async with FlowRunSubscriber(flow_run_id=flow_run_id):
        pass

    assert event_kwargs["reconnect_on_clean_close"] is True
    assert log_kwargs["reconnect_on_clean_close"] is True


async def test_flow_run_subscriber_propagates_non_connection_error(
    flow_run_id: UUID, monkeypatch
):
    """A non-retryable subscriber failure is propagated, not retried."""

    class InvalidEventSubscriber:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args) -> None:
            pass

        def __aiter__(self) -> Self:
            return self

        async def __anext__(self) -> Event:
            raise ValueError("invalid event payload")

    mock_events = InvalidEventSubscriber()
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

    with pytest.raises(ValueError, match="invalid event payload"):
        async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
            await anext(subscriber)


async def test_flow_run_subscriber_stops_when_events_close_and_logs_stay_open(
    flow_run_id: UUID, monkeypatch: pytest.MonkeyPatch
):
    """A cleanly closed stream must not strand an idle sibling stream."""

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

    with (
        anyio.fail_after(1),
        pytest.raises(
            ConnectionError, match="Flow run events stream closed unexpectedly"
        ),
    ):
        async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
            await anext(subscriber)


async def test_flow_run_subscriber_completes_after_terminal_event(
    flow_run_id: UUID,
    sample_event1: Event,
    monkeypatch: pytest.MonkeyPatch,
):
    """A clean run stops after reaching a terminal state."""
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
    monkeypatch.setattr(
        prefect.events.subscribers,
        "get_events_subscriber",
        lambda *args, **kwargs: MockEventSubscriber([sample_event1, terminal_event]),
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

    assert terminal_event in items


async def test_flow_run_subscriber_only_terminal_events_stop_consumption(
    flow_run_id: UUID, terminal_event: Event, setup_mocks
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

    setup_mocks([non_terminal_event, another_event, terminal_event], [])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 3
    assert all(isinstance(item, Event) for item in items)


async def test_flow_run_subscriber_terminal_event_for_different_flow_run(
    flow_run_id: UUID, terminal_event: Event, setup_mocks
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

    setup_mocks([event1, other_terminal, event2, terminal_event], [])

    items: list[Log | Event] = []
    async with FlowRunSubscriber(flow_run_id=flow_run_id) as subscriber:
        async for item in subscriber:
            items.append(item)

    assert len(items) == 4
