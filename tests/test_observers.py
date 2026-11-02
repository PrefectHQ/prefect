import asyncio
import signal
import threading
import uuid
from collections.abc import Awaitable, Callable, Generator
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import cast
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from websockets.exceptions import ConnectionClosedError

from prefect import flow
from prefect._flow_run_suspension import (
    FlowRunSuspensionRequest,
    _FlowRunSuspensionObserverThread,
    is_suspended_flow_run_state,
    observe_flow_run_suspension,
    observe_flow_run_suspension_async,
)
from prefect._internal.observers import (
    FlowRunCancellingObserver,
    FlowRunSuspendingObserver,
)
from prefect._internal.testing import retry_asserts
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.objects import State, StateType
from prefect.events import Event, Resource
from prefect.events.filters import EventAnyResourceFilter, EventFilter, EventNameFilter
from prefect.events.utilities import emit_event
from prefect.exceptions import ObjectNotFound, TerminationSignal
from prefect.states import Running, Scheduled, Suspended
from prefect.types._datetime import DateTime, now


@flow
def test_flow():
    """Simple test flow for observer tests."""


def suspension_event(
    flow_run_id: uuid.UUID,
    state_id: uuid.UUID,
    occurred: DateTime | None = None,
) -> Event:
    """A `Suspended` state change event, whose ID is the ID of the new state."""
    return Event(
        id=state_id,
        occurred=occurred or cast(DateTime, now("UTC")),
        event="prefect.flow-run.Suspended",
        resource=Resource({"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}),
    )


class TestFlowRunCancellingObserver:
    async def test_observer_initialization(self):
        """Test observer initializes with correct parameters."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback, polling_interval=5)

        assert observer.on_cancelling == callback
        assert observer.polling_interval == 5
        assert observer._in_flight_flow_run_ids == set()
        assert observer._is_shutting_down is False

    async def test_observer_validates_event_filter_has_cancelling_event(self):
        """Test observer validates that event_filter includes the Cancelling event."""
        callback = AsyncMock()

        # Valid filter with Cancelling event should work
        valid_filter = EventFilter(
            event=EventNameFilter(name=["prefect.flow-run.Cancelling"]),
            any_resource=EventAnyResourceFilter(id=["prefect.work-pool.test-id"]),
        )
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, event_filter=valid_filter
        )
        assert observer._event_filter == valid_filter

        # Filter without event should raise
        with pytest.raises(
            ValueError, match="must include 'prefect.flow-run.Cancelling'"
        ):
            FlowRunCancellingObserver(
                on_cancelling=callback,
                event_filter=EventFilter(),
            )

        # Filter with wrong event name should raise
        with pytest.raises(
            ValueError, match="must include 'prefect.flow-run.Cancelling'"
        ):
            FlowRunCancellingObserver(
                on_cancelling=callback,
                event_filter=EventFilter(
                    event=EventNameFilter(name=["prefect.flow-run.Running"])
                ),
            )

        # Filter with None event.name should raise
        with pytest.raises(
            ValueError, match="must include 'prefect.flow-run.Cancelling'"
        ):
            FlowRunCancellingObserver(
                on_cancelling=callback,
                event_filter=EventFilter(event=EventNameFilter()),
            )

    async def test_add_remove_in_flight_flow_runs(self):
        """Test tracking of in-flight flow run IDs."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        flow_run_id = uuid.uuid4()

        # Test adding
        observer.add_in_flight_flow_run_id(flow_run_id)
        assert flow_run_id in observer._in_flight_flow_run_ids

        # Test removing
        observer.remove_in_flight_flow_run_id(flow_run_id)
        assert flow_run_id not in observer._in_flight_flow_run_ids

        # Test removing non-existent ID doesn't error
        observer.remove_in_flight_flow_run_id(uuid.uuid4())

    async def test_observer_context_manager_lifecycle(self):
        """Test observer async context manager setup and teardown."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        assert observer._client is None

        async with observer:
            assert observer._client is not None

            # Give the consumer task a moment to start
            await asyncio.sleep(0.1)

        # After exit, shutdown flag should be set
        assert observer._is_shutting_down is True

    async def test_observer_handles_empty_in_flight_list(self):
        """Test observer behavior with no flow runs to track."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback,
            polling_interval=0.1,  # Fast polling for test
        )

        async with observer:
            # Trigger polling check manually
            await observer._check_for_cancelled_flow_runs()

        # Should not call callback with no flow runs
        callback.assert_not_called()

    async def test_polling_with_mocked_flow_runs(self):
        """Test polling correctly identifies cancelling flow runs using mock."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        flow_run_id = uuid.uuid4()

        # Mock the read_flow_runs method to return a cancelling flow run
        mock_flow_run = mock.MagicMock()
        mock_flow_run.id = flow_run_id
        mock_flow_run.state.type = StateType.CANCELLING
        mock_flow_run.state.name = "Cancelling"

        async with observer:
            # Add flow run to tracking
            observer.add_in_flight_flow_run_id(flow_run_id)

            # Mock the client's read_flow_runs:
            # - First call (named cancelling) returns empty
            # - Second call (typed cancelling) returns our mock flow run
            with patch.object(
                observer._client, "read_flow_runs", side_effect=[[], [mock_flow_run]]
            ):
                # Trigger polling check
                await observer._check_for_cancelled_flow_runs()

            # Should call callback once
            callback.assert_called_once_with(flow_run_id)

    async def test_polling_avoids_duplicate_cancellations(self):
        """Test polling doesn't trigger callback multiple times for same flow run."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        flow_run_id = uuid.uuid4()
        mock_flow_run = mock.MagicMock()
        mock_flow_run.id = flow_run_id

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            # First call - should trigger callback
            with patch.object(
                observer._client, "read_flow_runs", side_effect=[[], [mock_flow_run]]
            ):
                await observer._check_for_cancelled_flow_runs()

            assert callback.call_count == 1

            # Second call - the flow run was already dispatched, so it is not
            # read or dispatched again
            with patch.object(
                observer._client, "read_flow_runs", side_effect=[[mock_flow_run]] * 2
            ) as read_flow_runs:
                await observer._check_for_cancelled_flow_runs()

            read_flow_runs.assert_not_called()
            assert callback.call_count == 1  # Still only called once

    async def test_polling_filters_by_in_flight_ids(self):
        """Test polling only checks tracked flow runs."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        flow_run_id_1 = uuid.uuid4()
        flow_run_id_2 = uuid.uuid4()

        # Mock flow run that should be processed
        mock_flow_run_1 = mock.MagicMock()
        mock_flow_run_1.id = flow_run_id_1

        async with observer:
            # Only track first flow run
            observer.add_in_flight_flow_run_id(flow_run_id_1)
            # Don't track second flow run

            # Mock: first query returns empty, second query returns the tracked flow run
            with patch.object(
                observer._client, "read_flow_runs", side_effect=[[], [mock_flow_run_1]]
            ) as mock_read:
                await observer._check_for_cancelled_flow_runs()

                # Verify the filter includes only the tracked flow run
                call_args = mock_read.call_args_list
                # Should be called twice (once for named cancelling, once for typed cancelling)
                assert len(call_args) == 2

                # Check that both calls filter by the tracked flow run ID
                for call in call_args:
                    filter_arg = call[1]["flow_run_filter"]
                    id_filter = filter_arg.id.any_
                    assert flow_run_id_1 in id_filter
                    assert flow_run_id_2 not in id_filter

            # Should call callback for the tracked flow run
            callback.assert_called_once_with(flow_run_id_1)

    async def test_observer_consumes_cancelling_events(self):
        """Test observer consumes websocket events and calls callback."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        flow_run_id = uuid.uuid4()

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            # Give observer time to set up subscription
            await asyncio.sleep(0.1)

            # Emit cancelling event
            emit_event(
                event="prefect.flow-run.Cancelling",
                resource={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"},
                id=uuid.uuid4(),
            )

            # Retry assertion to handle event propagation delays under CI load
            async for attempt in retry_asserts(max_attempts=5, delay=0.5):
                with attempt:
                    callback.assert_called_once_with(flow_run_id)

    async def test_consume_events_ignores_non_in_flight_flow_runs(self):
        """Test that websocket events for flow runs not in the in-flight set are ignored."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        in_flight_id = uuid.uuid4()
        other_id = uuid.uuid4()

        async with observer:
            observer.add_in_flight_flow_run_id(in_flight_id)
            await asyncio.sleep(0.1)

            # Emit events for both in-flight and non-in-flight flow runs
            emit_event(
                event="prefect.flow-run.Cancelling",
                resource={"prefect.resource.id": f"prefect.flow-run.{other_id}"},
                id=uuid.uuid4(),
            )
            emit_event(
                event="prefect.flow-run.Cancelling",
                resource={"prefect.resource.id": f"prefect.flow-run.{in_flight_id}"},
                id=uuid.uuid4(),
            )

            # Retry assertion to handle event propagation delays under CI load
            async for attempt in retry_asserts(max_attempts=5, delay=0.5):
                with attempt:
                    callback.assert_called_once_with(in_flight_id)

    async def test_client_not_initialized_error(self):
        """Test error handling when client is not initialized."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        # Try to check for cancelled flow runs without initializing
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await observer._check_for_cancelled_flow_runs()

    async def test_observer_initialization_with_on_failure(self):
        """Test observer initializes with on_failure callback."""
        on_cancelling = AsyncMock()
        on_failure = mock.MagicMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=on_cancelling,
            on_failure=on_failure,
            polling_interval=5,
        )

        assert observer.on_cancelling == on_cancelling
        assert observer.on_failure == on_failure
        assert observer.polling_interval == 5

    async def test_polling_fallback_detects_cancelling_flow_runs(self):
        """Test that polling fallback actually detects cancelling flow runs
        when the subscriber connection fails."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        flow_run_id = uuid.uuid4()
        mock_flow_run = MagicMock()
        mock_flow_run.id = flow_run_id

        with patch(
            "prefect._internal.observers.get_events_subscriber",
            side_effect=Exception("WebSocket connection failed"),
        ):
            async with observer:
                observer.add_in_flight_flow_run_id(flow_run_id)

                # Use the polling mechanism to check for cancellations
                with patch.object(
                    observer._client,
                    "read_flow_runs",
                    side_effect=[[], [mock_flow_run]],
                ):
                    await observer._check_for_cancelled_flow_runs()

                callback.assert_called_once_with(flow_run_id)


class TestFlowRunSuspendingObserver:
    async def consume(
        self,
        observer: FlowRunSuspendingObserver,
        *events: Event,
    ) -> None:
        """Deliver `events` to the observer as the events stream would."""
        for event in events:
            observer._handle_event(event)

    async def test_observer_validates_event_filter_has_suspended_event(self):
        callback = AsyncMock()

        valid_filter = EventFilter(
            event=EventNameFilter(name=["prefect.flow-run.Suspended"]),
            any_resource=EventAnyResourceFilter(id=["prefect.work-pool.test-id"]),
        )
        observer = FlowRunSuspendingObserver(
            on_suspended=callback, event_filter=valid_filter
        )
        assert observer._event_filter == valid_filter

        with pytest.raises(
            ValueError, match="must include 'prefect.flow-run.Suspended'"
        ):
            FlowRunSuspendingObserver(
                on_suspended=callback,
                event_filter=EventFilter(
                    event=EventNameFilter(name=["prefect.flow-run.Running"])
                ),
            )

    async def test_polling_with_mocked_suspended_flow_runs(self):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(
            on_suspended=callback, polling_interval=0.1
        )

        flow_run_id = uuid.uuid4()
        state = Suspended()
        mock_flow_run = mock.MagicMock()
        mock_flow_run.id = flow_run_id
        mock_flow_run.state = state

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(
                observer._client, "read_flow_runs", return_value=[mock_flow_run]
            ):
                await observer._check_for_suspended_flow_runs()

            callback.assert_called_once_with(flow_run_id, state)

    async def test_watch_flow_run_id_checks_current_state(self):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        state = Suspended()
        flow_run = mock.MagicMock(state=state)

        async with observer:
            with patch.object(
                observer._client,
                "read_flow_run",
                return_value=flow_run,
            ) as read_flow_run:
                await observer.watch_flow_run_id(flow_run_id)

            assert flow_run_id in observer._in_flight_flow_run_ids
            read_flow_run.assert_called_once_with(flow_run_id)
            callback.assert_called_once_with(flow_run_id, state)

    async def test_watch_flow_run_id_retries_initial_check_until_success(self, caplog):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(
            on_suspended=callback, polling_interval=0.01
        )

        flow_run_id = uuid.uuid4()
        state = Suspended()
        flow_run = mock.MagicMock(state=state)
        caplog.set_level("WARNING", logger="prefect.FlowRunSuspendingObserver")

        async with observer:
            with patch.object(
                observer._client,
                "read_flow_run",
                side_effect=[
                    RuntimeError("boom"),
                    RuntimeError("still boom"),
                    flow_run,
                ],
            ) as read_flow_run:
                await observer.watch_flow_run_id(flow_run_id)

            assert flow_run_id in observer._in_flight_flow_run_ids
            assert read_flow_run.call_count == 3
            callback.assert_called_once_with(flow_run_id, state)
            assert "Failed to check current state" in caplog.text

    async def test_event_confirmation_retries_until_transition_visible(
        self, monkeypatch, caplog
    ):
        callback = MagicMock()
        monkeypatch.setattr(
            "prefect._internal.observers.SUSPENSION_CONFIRMATION_WARNING_AFTER", 0
        )
        monkeypatch.setattr(
            "prefect._internal.observers.SUSPENSION_CONFIRMATION_INTERVAL", 0
        )
        caplog.set_level("WARNING", logger="prefect.FlowRunSuspendingObserver")
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        stale_state = Running(
            timestamp=cast(DateTime, now("UTC") - timedelta(seconds=1))
        )
        suspended_state = Suspended()

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(
                observer._client,
                "read_flow_run",
                side_effect=[
                    RuntimeError("temporarily unavailable"),
                    MagicMock(state=stale_state),
                    MagicMock(state=suspended_state),
                ],
            ) as read_flow_run:
                await self.consume(
                    observer, suspension_event(flow_run_id, suspended_state.id)
                )

                async for attempt in retry_asserts():
                    with attempt:
                        callback.assert_called_once_with(flow_run_id, suspended_state)

            assert read_flow_run.await_count == 3
            assert "continuing to retry" in caplog.text

    async def test_superseded_suspension_still_notifies(self):
        """A suspension the run has already moved past (e.g. it was resumed
        before this observer confirmed it) must still stop the engine: the
        resumed run gets a fresh submission, and this engine continuing would
        double-execute. The confirmation reconstructs the reported Suspended
        state from the event's identity."""
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        state_id = uuid.uuid4()
        occurred = cast(DateTime, now("UTC") - timedelta(seconds=5))
        resumed_state = Scheduled()

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(
                observer._client,
                "read_flow_run",
                return_value=MagicMock(state=resumed_state),
            ):
                await self.consume(
                    observer,
                    suspension_event(flow_run_id, state_id, occurred=occurred),
                )

                async for attempt in retry_asserts():
                    with attempt:
                        callback.assert_called_once()

        notified_flow_run_id, notified_state = callback.call_args[0]
        assert notified_flow_run_id == flow_run_id
        assert notified_state.id == state_id
        assert notified_state.timestamp == occurred
        assert is_suspended_flow_run_state(notified_state)

    async def test_confirmation_abandoned_when_flow_run_deleted(self):
        """A deleted flow run has nothing left to suspend: the confirmation
        stops instead of retrying forever."""
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(
                observer._client,
                "read_flow_run",
                side_effect=ObjectNotFound(Exception("deleted")),
            ) as read_flow_run:
                await self.consume(
                    observer, suspension_event(flow_run_id, uuid.uuid4())
                )

                async for attempt in retry_asserts():
                    with attempt:
                        assert read_flow_run.await_count == 1

                await asyncio.sleep(0)
                assert read_flow_run.await_count == 1
                callback.assert_not_called()

    @pytest.mark.parametrize(
        ("event_offset", "should_suspend"),
        [(-1, False), (1, True)],
        ids=["replayed-event", "clock-skewed-new-event"],
    )
    async def test_event_is_filtered_against_server_checkpoint(
        self, event_offset: int, should_suspend: bool
    ):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        checkpoint = cast(DateTime, now("UTC") - timedelta(minutes=5))
        current_state = Running(timestamp=checkpoint)
        suspended_state = Suspended()

        async with observer:
            with patch.object(
                observer._client,
                "read_flow_run",
                side_effect=[
                    MagicMock(state=current_state),
                    MagicMock(state=suspended_state),
                ],
            ) as read_flow_run:
                await observer.watch_flow_run_id(flow_run_id)
                await self.consume(
                    observer,
                    suspension_event(
                        flow_run_id,
                        suspended_state.id,
                        occurred=cast(
                            DateTime, checkpoint + timedelta(seconds=event_offset)
                        ),
                    ),
                )

                if should_suspend:
                    async for attempt in retry_asserts():
                        with attempt:
                            callback.assert_called_once_with(
                                flow_run_id, suspended_state
                            )
                else:
                    await asyncio.sleep(0)
                    # Only the initial state check read the flow run; the
                    # replayed event was filtered before any confirmation read.
                    assert read_flow_run.await_count == 1
                    callback.assert_not_called()

    async def test_event_is_buffered_during_initial_state_check(self):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        checkpoint = cast(DateTime, now("UTC") - timedelta(seconds=1))
        current_state = Running(timestamp=checkpoint)
        suspended_state = Suspended()
        initial_read_started = asyncio.Event()
        release_initial_read = asyncio.Event()
        read_count = 0

        async def read_flow_run(observed_flow_run_id: uuid.UUID):
            assert observed_flow_run_id == flow_run_id
            nonlocal read_count
            read_count += 1
            if read_count == 1:
                initial_read_started.set()
                await release_initial_read.wait()
                return MagicMock(state=current_state)
            return MagicMock(state=suspended_state)

        async with observer:
            with patch.object(observer._client, "read_flow_run", read_flow_run):
                watch_task = asyncio.create_task(
                    observer.watch_flow_run_id(flow_run_id)
                )
                await initial_read_started.wait()
                await self.consume(
                    observer,
                    suspension_event(
                        flow_run_id,
                        suspended_state.id,
                        occurred=cast(DateTime, checkpoint + timedelta(milliseconds=1)),
                    ),
                )
                await asyncio.sleep(0)
                # Confirmation waits behind the initialization gate: only the
                # in-flight initial check has read the flow run.
                assert read_count == 1
                callback.assert_not_called()

                release_initial_read.set()
                await watch_task

                async for attempt in retry_asserts():
                    with attempt:
                        callback.assert_called_once_with(flow_run_id, suspended_state)

    async def test_confirmation_does_not_block_other_flow_runs(self):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        blocked_flow_run_id = uuid.uuid4()
        flow_run_id = uuid.uuid4()
        suspended_state = Suspended()
        blocked = asyncio.Event()

        async def read_flow_run(observed_flow_run_id: uuid.UUID):
            if observed_flow_run_id == blocked_flow_run_id:
                await blocked.wait()
                raise ObjectNotFound(Exception("gone"))
            return MagicMock(state=suspended_state)

        async with observer:
            observer.add_in_flight_flow_run_id(blocked_flow_run_id)
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(observer._client, "read_flow_run", read_flow_run):
                await self.consume(
                    observer,
                    suspension_event(blocked_flow_run_id, uuid.uuid4()),
                    suspension_event(flow_run_id, suspended_state.id),
                )

                async for attempt in retry_asserts():
                    with attempt:
                        callback.assert_called_once_with(flow_run_id, suspended_state)

    @pytest.mark.parametrize("stop", ["remove", "shutdown"])
    async def test_pending_confirmation_is_cancelled(self, stop: str):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        blocked = asyncio.Event()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def read_flow_run(observed_flow_run_id: uuid.UUID):
            started.set()
            try:
                await blocked.wait()
            finally:
                cancelled.set()
            raise ObjectNotFound(Exception("gone"))

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(observer)
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(observer._client, "read_flow_run", read_flow_run):
                await self.consume(
                    observer,
                    suspension_event(flow_run_id, uuid.uuid4()),
                )
                await started.wait()

                if stop == "remove":
                    observer.remove_in_flight_flow_run_id(flow_run_id)
                else:
                    await stack.aclose()

                await cancelled.wait()
                callback.assert_not_called()

    def test_observe_flow_run_suspension_waits_for_initial_check(self, monkeypatch):
        flow_run_id = uuid.uuid4()
        suspension_request = FlowRunSuspensionRequest()
        watch_started = threading.Event()
        release_watch = threading.Event()
        entered_context = threading.Event()
        exit_context = threading.Event()
        errors: list[BaseException] = []

        class FakeFlowRunSuspendingObserver:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                pass

            async def watch_flow_run_id(self, observed_flow_run_id):
                assert observed_flow_run_id == flow_run_id
                watch_started.set()
                await asyncio.to_thread(release_watch.wait)

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )

        def enter_observer_context():
            try:
                with observe_flow_run_suspension(flow_run_id, suspension_request):
                    entered_context.set()
                    exit_context.wait(timeout=2)
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=enter_observer_context)
        thread.start()

        assert watch_started.wait(timeout=2)
        assert not entered_context.wait(timeout=2.2)

        release_watch.set()
        assert entered_context.wait(timeout=2)

        exit_context.set()
        thread.join(timeout=2)

        assert not thread.is_alive()
        assert not errors

    def test_observe_flow_run_suspension_stops_observer_interrupted_during_initial_check(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        watch_started = threading.Event()
        observers: list[_FlowRunSuspensionObserverThread] = []

        class FakeFlowRunSuspendingObserver:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                pass

            async def watch_flow_run_id(self, observed_flow_run_id):
                watch_started.set()
                # Retries until stopped, like the real observer while the API is
                # unavailable.
                while True:
                    await asyncio.sleep(0.01)

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )

        original_init = _FlowRunSuspensionObserverThread.__init__

        def init_with_interrupted_wait(
            self: _FlowRunSuspensionObserverThread, *args, ready, **kwargs
        ):
            original_init(self, *args, ready=ready, **kwargs)
            observers.append(self)

            # Raises like the SIGTERM handler of the engine does.
            def interrupted_wait(timeout: float | None = None) -> bool:
                assert watch_started.wait(timeout=10)
                raise TerminationSignal(signal=signal.SIGTERM)

            ready.wait = interrupted_wait

        monkeypatch.setattr(
            _FlowRunSuspensionObserverThread, "__init__", init_with_interrupted_wait
        )
        caplog.set_level("DEBUG", logger="prefect.flow_run_suspension")

        with pytest.raises(TerminationSignal):
            with observe_flow_run_suspension(uuid.uuid4(), FlowRunSuspensionRequest()):
                pass

        (observer,) = observers
        observer.join(timeout=10)
        assert not observer._thread.is_alive()
        assert "cancelled before it was stopped" not in caplog.text

    def test_observe_flow_run_suspension_logs_unexpected_observer_cancellation(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        class FakeFlowRunSuspendingObserver:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                pass

            async def watch_flow_run_id(self, observed_flow_run_id):
                # Cancelled by something other than `stop`.
                task = asyncio.current_task()
                assert task is not None
                task.cancel()
                await asyncio.sleep(0)

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )
        caplog.set_level("DEBUG", logger="prefect.flow_run_suspension")

        with observe_flow_run_suspension(uuid.uuid4(), FlowRunSuspensionRequest()):
            pass

        assert (
            "Flow run suspension observer was cancelled before it was stopped"
            in caplog.text
        )

    async def test_observe_flow_run_suspension_async_waits_for_initial_check_without_blocking_event_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        flow_run_id = uuid.uuid4()
        test_loop = asyncio.get_running_loop()
        watch_started = asyncio.Event()
        release_watch = asyncio.Event()
        watch_released = False

        class FakeFlowRunSuspendingObserver:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                pass

            async def watch_flow_run_id(self, observed_flow_run_id):
                nonlocal watch_released
                assert observed_flow_run_id == flow_run_id
                test_loop.call_soon_threadsafe(watch_started.set)
                # Completes only if the caller's event loop keeps running.
                await asyncio.wait_for(
                    asyncio.wrap_future(
                        asyncio.run_coroutine_threadsafe(
                            release_watch.wait(), test_loop
                        )
                    ),
                    timeout=10,
                )
                watch_released = True

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )

        entered_context = asyncio.Event()
        exit_context = asyncio.Event()

        async def run_with_observer():
            async with observe_flow_run_suspension_async(
                flow_run_id, FlowRunSuspensionRequest()
            ):
                entered_context.set()
                await exit_context.wait()

        observed = asyncio.create_task(run_with_observer())
        await watch_started.wait()
        assert not entered_context.is_set()

        release_watch.set()
        await asyncio.wait_for(entered_context.wait(), timeout=10)
        assert watch_released

        exit_context.set()
        await asyncio.wait_for(observed, timeout=10)

    async def test_observe_flow_run_suspension_async_exits_without_waiting_for_observer_shutdown(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        release_shutdown = threading.Event()
        observer_exited = threading.Event()

        class FakeFlowRunSuspendingObserver:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                # Holds the observer's thread until the test releases it.
                release_shutdown.wait(timeout=10)
                observer_exited.set()

            async def watch_flow_run_id(self, observed_flow_run_id):
                pass

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )
        # Makes the test fail if leaving the context waits for the observer, as
        # `observe_flow_run_suspension` does.
        monkeypatch.setattr(
            "prefect._flow_run_suspension._OBSERVER_SHUTDOWN_TIMEOUT", 60
        )

        try:
            async with observe_flow_run_suspension_async(
                uuid.uuid4(), FlowRunSuspensionRequest()
            ):
                pass

            assert not observer_exited.is_set()
        finally:
            release_shutdown.set()

        assert await asyncio.to_thread(observer_exited.wait, 10)

    async def test_observe_flow_run_suspension_async_marks_suspension_request(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        flow_run_id = uuid.uuid4()
        suspension_request = FlowRunSuspensionRequest()
        suspended_state = Suspended()

        class FakeFlowRunSuspendingObserver:
            def __init__(self, on_suspended, **kwargs):
                self.on_suspended = on_suspended

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                pass

            async def watch_flow_run_id(self, observed_flow_run_id):
                self.on_suspended(observed_flow_run_id, suspended_state)

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )

        async with observe_flow_run_suspension_async(flow_run_id, suspension_request):
            assert suspension_request.get_state() is suspended_state

    async def test_observe_flow_run_suspension_async_stops_observer_cancelled_during_initial_check(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        test_loop = asyncio.get_running_loop()
        watch_started = asyncio.Event()
        observer_exited = threading.Event()

        class FakeFlowRunSuspendingObserver:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                observer_exited.set()

            async def watch_flow_run_id(self, observed_flow_run_id):
                test_loop.call_soon_threadsafe(watch_started.set)
                # Retries until stopped, like the real observer while the API is
                # unavailable.
                while True:
                    await asyncio.sleep(0.01)

        monkeypatch.setattr(
            "prefect._internal.observers.FlowRunSuspendingObserver",
            FakeFlowRunSuspendingObserver,
        )

        async def run_with_observer():
            async with observe_flow_run_suspension_async(
                uuid.uuid4(), FlowRunSuspensionRequest()
            ):
                pass

        observed = asyncio.create_task(run_with_observer())
        await asyncio.wait_for(watch_started.wait(), timeout=10)
        observed.cancel()

        done, _ = await asyncio.wait([observed], timeout=10)
        assert observed in done
        assert observed.cancelled()
        assert await asyncio.to_thread(observer_exited.wait, 10)


CLOSE = object()
HANG = object()


class ScriptedConnection:
    """One events websocket connection, fed by the test."""

    def __init__(self, *items: object):
        self.items: asyncio.Queue[object] = asyncio.Queue()
        for item in items:
            self.send(item)

    def send(self, item: object) -> None:
        """Deliver an `Event`, raise an exception, or `CLOSE` the stream."""
        self.items.put_nowait(item)


class ScriptedEventStream:
    """
    Stands in for the events subscriber. Each connection attempt follows the
    next script entry: an exception fails setup, `HANG` never completes setup,
    an `asyncio.Event` completes setup once set, and a `ScriptedConnection`
    succeeds. Attempts beyond the script fail.
    """

    def __init__(self, *script: object):
        self.script = list(script)
        self.attempts = 0
        self.connections = 0
        self.exits = 0
        self.abandoned = 0
        self.factory_kwargs: dict[str, object] = {}
        self._connection: ScriptedConnection | None = None

    def __call__(self, **kwargs: object) -> "ScriptedEventStream":
        self.factory_kwargs = kwargs
        return self

    async def __aenter__(self) -> "ScriptedEventStream":
        self.attempts += 1
        entry = self.script.pop(0) if self.script else ConnectionError("down")
        if isinstance(entry, BaseException):
            raise entry
        try:
            if entry is HANG:
                await asyncio.Event().wait()
            if isinstance(entry, asyncio.Event):
                await entry.wait()
                entry = ScriptedConnection()
        except asyncio.CancelledError:
            self.abandoned += 1
            raise
        assert isinstance(entry, ScriptedConnection)
        self._connection = entry
        self.connections += 1
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.exits += 1
        self._connection = None

    def __aiter__(self) -> "ScriptedEventStream":
        return self

    async def __anext__(self) -> Event:
        assert self._connection is not None
        item = await self._connection.items.get()
        if item is CLOSE:
            raise StopAsyncIteration
        if isinstance(item, BaseException):
            raise item
        assert isinstance(item, Event)
        return item


class ReconnectTimer:
    """Replaces reconnect delays with waits the test releases explicitly."""

    def __init__(self):
        self.delays: list[float] = []
        self._waiters: list[asyncio.Future[None]] = []

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        await waiter

    @property
    def pending(self) -> int:
        return sum(not waiter.done() for waiter in self._waiters)

    async def fire(self) -> None:
        """Release the next reconnect delay, waiting for it to start."""
        await until(lambda: self.pending > 0)
        waiter = next(waiter for waiter in self._waiters if not waiter.done())
        waiter.set_result(None)


class FakeAPI:
    """Stands in for the API client, serving current flow run states."""

    def __init__(self):
        self.cancelling: set[uuid.UUID] = set()
        self.suspended: dict[uuid.UUID, State] = {}
        self.states: dict[uuid.UUID, State] = {}
        self.failures: list[Exception] = []
        self.gate: asyncio.Event | None = None
        self.hold: Callable[[int], Awaitable[None]] | None = None
        self.reads = 0
        self.waiting = 0
        self.enters = 0
        self.exits = 0

    async def __aenter__(self) -> "FakeAPI":
        self.enters += 1
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.exits += 1

    async def read_flow_runs(self, flow_run_filter: FlowRunFilter) -> list[MagicMock]:
        self.reads += 1
        self.waiting += 1
        try:
            if self.hold is not None:
                await self.hold(self.reads)
            if self.gate is not None:
                await self.gate.wait()
        finally:
            self.waiting -= 1
        if self.failures:
            raise self.failures.pop(0)
        assert flow_run_filter.id is not None and flow_run_filter.state is not None
        assert flow_run_filter.id.any_ is not None
        assert flow_run_filter.state.type is not None
        assert flow_run_filter.state.type.any_ is not None
        requested = set(flow_run_filter.id.any_)
        if StateType.CANCELLING in flow_run_filter.state.type.any_:
            return [MagicMock(id=id) for id in requested & self.cancelling]
        if StateType.PAUSED in flow_run_filter.state.type.any_:
            return [
                MagicMock(id=id, state=self.suspended[id])
                for id in requested & self.suspended.keys()
            ]
        return []

    async def read_flow_run(self, flow_run_id: uuid.UUID) -> MagicMock:
        return MagicMock(state=self.states.get(flow_run_id))


class HeldReads:
    """Holds each API read until the test resolves it, in the order started."""

    def __init__(self):
        self.reads: list[asyncio.Future[None]] = []
        self.taken = 0

    async def __call__(self, read: int) -> None:
        read_completes = asyncio.get_running_loop().create_future()
        self.reads.append(read_completes)
        await read_completes

    async def next(self) -> asyncio.Future[None]:
        """Wait for the next read to start and return its outcome to resolve."""
        await until(lambda: len(self.reads) > self.taken)
        self.taken += 1
        return self.reads[self.taken - 1]


def unavailable() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://api/flow_runs/filter")
    return httpx.HTTPStatusError(
        "unavailable", request=request, response=httpx.Response(503, request=request)
    )


async def until(predicate: Callable[[], bool], timeout: float = 5) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.001)


def cancelling_event(flow_run_id: uuid.UUID) -> Event:
    return Event(
        id=uuid.uuid4(),
        event="prefect.flow-run.Cancelling",
        resource=Resource({"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}),
    )


class RecoveryCase:
    """Drives one observer through its public interface for recovery tests."""

    def __init__(self, kind: str, api: FakeAPI):
        self.kind = kind
        self.api = api
        self.callback = MagicMock()
        self.on_failure = MagicMock()
        if kind == "cancelling":
            self.observer: FlowRunCancellingObserver | FlowRunSuspendingObserver = (
                FlowRunCancellingObserver(
                    on_cancelling=self.callback,
                    polling_interval=0.01,
                    on_failure=self.on_failure,
                )
            )
        else:
            self.observer = FlowRunSuspendingObserver(
                on_suspended=self.callback,
                polling_interval=0.01,
                on_failure=self.on_failure,
            )

    @property
    def notified(self) -> list[uuid.UUID]:
        return [call.args[0] for call in self.callback.call_args_list]

    def signal_by_polling(self, flow_run_id: uuid.UUID) -> None:
        """Make the server report the signal to current-state checks."""
        if self.kind == "cancelling":
            self.api.cancelling.add(flow_run_id)
        else:
            state = Suspended()
            self.api.suspended[flow_run_id] = state
            self.api.states[flow_run_id] = state

    def signal_event(self, flow_run_id: uuid.UUID) -> Event:
        """An event for the signal; only confirmation reads observe the state."""
        if self.kind == "cancelling":
            return cancelling_event(flow_run_id)
        state = Suspended()
        self.api.states[flow_run_id] = state
        return suspension_event(flow_run_id, state.id)


@pytest.fixture
def timer(monkeypatch: pytest.MonkeyPatch) -> ReconnectTimer:
    timer = ReconnectTimer()
    monkeypatch.setattr("prefect._internal._observation_delivery._sleep", timer.sleep)
    return timer


@pytest.fixture
def api() -> Generator[FakeAPI, None, None]:
    api = FakeAPI()
    with patch("prefect._internal.observers.get_client", return_value=api):
        yield api


@pytest.fixture
def stream() -> Generator[ScriptedEventStream, None, None]:
    stream = ScriptedEventStream()
    with patch("prefect._internal.observers.get_events_subscriber", stream):
        yield stream


@pytest.fixture(params=["cancelling", "suspending"])
def case(request: pytest.FixtureRequest, api: FakeAPI) -> RecoveryCase:
    return RecoveryCase(request.param, api)


RESTORED = "reconnected to the events stream and stopped polling"


def restored(caplog: pytest.LogCaptureFixture) -> int:
    return caplog.text.count(RESTORED)


async def assert_not_polling(api: FakeAPI) -> None:
    reads = api.reads
    await asyncio.sleep(0.1)
    assert api.reads == reads


@pytest.mark.usefixtures("timer")
class TestObserverRecovery:
    @pytest.fixture(autouse=True)
    def capture_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("DEBUG", logger="prefect.FlowRunCancellingObserver")
        caplog.set_level("DEBUG", logger="prefect.FlowRunSuspendingObserver")

    async def test_recovers_after_initial_connection_failure(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
    ):
        connection = ScriptedConnection()
        stream.script = [ConnectionError("down"), connection]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            assert "Falling back to polling" in caplog.text

            await until(lambda: api.reads >= 3)
            await until(lambda: timer.pending == 1)
            await timer.fire()

            await until(lambda: restored(caplog) == 1)
            await assert_not_polling(api)

            connection.send(case.signal_event(flow_run_id))
            await until(lambda: case.notified == [flow_run_id])

        assert stream.factory_kwargs["reconnection_attempts"] == 0
        assert stream.exits == 1
        case.on_failure.assert_not_called()

    @pytest.mark.parametrize("ending", ["closed", "failed"])
    async def test_recovers_after_stream_ends(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
        ending: str,
    ):
        first, second = ScriptedConnection(), ScriptedConnection()
        stream.script = [first, second]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await assert_not_polling(api)

            first.send(
                CLOSE if ending == "closed" else ConnectionClosedError(None, None)
            )
            await until(lambda: api.reads >= 3)
            assert "Switching to polling mode until it reconnects" in caplog.text
            assert stream.exits == 1

            await timer.fire()
            await until(lambda: restored(caplog) == 1)
            await assert_not_polling(api)

            second.send(case.signal_event(flow_run_id))
            await until(lambda: case.notified == [flow_run_id])

        case.on_failure.assert_not_called()

    async def test_repeated_outages_recover_each_time(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
    ):
        connections = [ScriptedConnection() for _ in range(3)]
        stream.script = list(connections)

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(uuid.uuid4())
            for cycle, connection in enumerate(connections[:-1], start=1):
                connection.send(CLOSE)
                await timer.fire()
                await until(lambda cycle=cycle: restored(caplog) == cycle)
            await assert_not_polling(api)

        assert stream.connections == 3
        assert stream.exits == 3

    async def test_keeps_polling_while_setup_hangs(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "prefect._internal._observation_delivery.SETUP_TIMEOUT_SECONDS", 0.2
        )
        stream.script = [ConnectionError("down"), HANG, ScriptedConnection()]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: timer.pending == 1)
            await timer.fire()
            await until(lambda: stream.attempts == 2)

            case.signal_by_polling(flow_run_id)
            await until(lambda: case.notified == [flow_run_id])
            assert stream.abandoned == 0

            await until(lambda: stream.abandoned == 1)
            await until(lambda: timer.pending == 1)
            assert "failed to reconnect to the events stream" in caplog.text
            await timer.fire()
            await until(lambda: restored(caplog) == 1)

        assert case.notified == [flow_run_id]
        case.on_failure.assert_not_called()

    async def test_flapping_connection_keeps_backing_off(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "prefect._internal._observation_delivery.RECONNECT_MAX_DELAY_SECONDS", 8
        )
        # Every handshake succeeds, but each stream closes right away
        stream.script = [ScriptedConnection(CLOSE) for _ in range(7)]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            for attempt in range(2, 8):
                await until(lambda: timer.pending == 1)
                await timer.fire()
                await until(lambda attempt=attempt: stream.connections == attempt)

            case.signal_by_polling(flow_run_id)
            await until(lambda: case.notified == [flow_run_id])

        assert restored(caplog) == 0
        assert stream.exits == stream.connections
        # Jittered delays grow with each failed attempt and stay capped
        assert timer.delays[0] <= 1
        assert all(4 <= delay <= 8 for delay in timer.delays[3:])
        case.on_failure.assert_not_called()

    async def test_reports_failure_when_polling_fails_without_stream(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        flow_run_ids = {uuid.uuid4(), uuid.uuid4()}
        captured: list[set[uuid.UUID]] = []
        case.on_failure.side_effect = captured.append
        api.failures = [ValueError("not retryable")]

        async with case.observer:
            for flow_run_id in flow_run_ids:
                case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: bool(captured))
            case.observer.add_in_flight_flow_run_id(uuid.uuid4())

        assert captured == [flow_run_ids]
        case.callback.assert_not_called()

    async def test_reports_failure_after_transient_polling_failures(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        flow_run_id = uuid.uuid4()
        api.failures = [httpx.ConnectError("down") for _ in range(3)]

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: case.on_failure.called)

        case.on_failure.assert_called_once_with({flow_run_id})

    async def test_failure_is_not_deferred_by_pending_setup(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
    ):
        stream.script = [ConnectionError("down"), HANG]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: timer.pending == 1)
            await timer.fire()
            await until(lambda: stream.attempts == 2)

            api.failures = [ValueError("not retryable")]
            await until(lambda: case.on_failure.called)
            assert stream.abandoned == 1

        case.on_failure.assert_called_once_with({flow_run_id})

    async def test_poll_failure_does_not_override_established_stream(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
    ):
        setup_completes = asyncio.Event()
        stream.script = [ConnectionError("down"), setup_completes]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: timer.pending == 1)
            await timer.fire()
            await until(lambda: stream.attempts == 2)

            api.gate = asyncio.Event()
            await until(lambda: api.waiting == 1)
            api.failures = [ValueError("not retryable")]
            # The poll fails and setup completes at the same time
            api.gate.set()
            setup_completes.set()

            await until(lambda: restored(caplog) == 1)
            await assert_not_polling(api)

        case.on_failure.assert_not_called()

    @pytest.mark.parametrize("first_failure", ["polling", "reconciliation"])
    async def test_failed_reconciliation_keeps_working_stream(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
        first_failure: str,
    ):
        held = HeldReads()
        api.hold = held
        connection = ScriptedConnection()
        stream.script = [ConnectionError("down"), connection]
        first_run, second_run, running = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        async def exhaust_polling(first_poll: asyncio.Future[None]) -> None:
            first_poll.set_exception(unavailable())
            for _ in range(2):
                (await held.next()).set_exception(unavailable())

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(first_run)
            case.observer.add_in_flight_flow_run_id(second_run)
            case.observer.add_in_flight_flow_run_id(running)
            poll = await held.next()
            await timer.fire()
            reconciliation = await held.next()
            assert stream.connections == 1

            connection.send(case.signal_event(first_run))
            await until(lambda: case.notified == [first_run])

            if first_failure == "polling":
                await exhaust_polling(poll)
                reconciliation.set_exception(unavailable())
            else:
                reconciliation.set_exception(unavailable())
                await until(lambda: timer.pending == 1)
                await exhaust_polling(poll)
            await until(lambda: timer.pending == 1)
            await asyncio.sleep(0.1)
            assert held.taken == len(held.reads), "polling should have stopped"

            # The stream keeps delivering while both HTTP mechanisms are failing
            connection.send(case.signal_event(second_run))
            await until(lambda: case.notified == [first_run, second_run])
            assert stream.exits == 0
            case.on_failure.assert_not_called()
            assert restored(caplog) == 0

            # The handoff completes once the current state has been checked
            api.hold = None
            reads = api.reads
            await timer.fire()
            await until(lambda: restored(caplog) == 1)
            assert api.reads > reads

        case.on_failure.assert_not_called()

    @pytest.mark.parametrize("next_action", ["stream_end", "shutdown"])
    async def test_leaves_reconciliation_retry_safely(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
        next_action: str,
    ):
        held = HeldReads()
        api.hold = held
        first, second = ScriptedConnection(), ScriptedConnection()
        stream.script = [ConnectionError("down"), first, second]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            poll = await held.next()
            await timer.fire()
            reconciliation = await held.next()
            reconciliation.set_exception(unavailable())
            await until(lambda: timer.pending == 1)

            if next_action == "stream_end":
                api.hold = None
                poll.set_result(None)
                first.send(CLOSE)
                await until(lambda: stream.exits == 1)
                await timer.fire()
                await until(lambda: restored(caplog) == 1)
                second.send(case.signal_event(flow_run_id))
                await until(lambda: case.notified == [flow_run_id])

        if next_action == "shutdown":
            assert poll.cancelled()
            assert stream.attempts == 2
            case.callback.assert_not_called()
        assert timer.pending == 0
        assert api.waiting == 0
        assert stream.exits == stream.connections
        case.on_failure.assert_not_called()

    async def test_reports_failure_when_stream_ends_after_polling_failed(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
    ):
        held = HeldReads()
        api.hold = held
        connection = ScriptedConnection()
        stream.script = [ConnectionError("down"), connection]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            poll = await held.next()
            await timer.fire()
            reconciliation = await held.next()
            reconciliation.set_exception(unavailable())
            poll.set_exception(unavailable())
            for _ in range(2):
                (await held.next()).set_exception(unavailable())
            await until(lambda: timer.pending == 1)
            case.on_failure.assert_not_called()

            connection.send(CLOSE)
            await until(lambda: case.on_failure.called)
            assert stream.exits == 1

        case.on_failure.assert_called_once_with({flow_run_id})

    async def test_cancelled_entry_releases_resources(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        setup_completes = asyncio.Event()
        stream.script = [setup_completes]

        async def enter_observer() -> None:
            async with case.observer:
                pytest.fail("entry should have been cancelled")

        entering = asyncio.create_task(enter_observer())
        await until(lambda: stream.attempts == 1)
        assert api.enters == 1
        entering.cancel()
        with pytest.raises(asyncio.CancelledError):
            await entering

        assert entering.cancelled()
        assert stream.abandoned == 1
        assert api.exits == 1
        setup_completes.set()
        await asyncio.sleep(0.05)
        assert stream.attempts == 1
        case.on_failure.assert_not_called()

    @pytest.mark.parametrize(
        "stop_during", ["delay", "setup", "reconciliation", "streaming"]
    )
    async def test_shutdown_stops_recovery(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        stop_during: str,
    ):
        flow_run_id = uuid.uuid4()
        if stop_during == "streaming":
            stream.script = [ScriptedConnection()]
        elif stop_during == "setup":
            stream.script = [ConnectionError("down"), HANG]
        else:
            stream.script = [ConnectionError("down"), ScriptedConnection()]

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            if stop_during != "streaming":
                await until(lambda: timer.pending == 1)
            if stop_during == "reconciliation":
                api.gate = asyncio.Event()
                await until(lambda: api.waiting == 1)
                await timer.fire()
                await until(lambda: stream.connections == 1 and api.waiting == 2)
            elif stop_during == "setup":
                await timer.fire()
                await until(lambda: stream.attempts == 2)

        attempts = stream.attempts
        assert timer.pending == 0
        assert stream.exits == stream.connections
        if stop_during == "setup":
            assert stream.abandoned == 1

        case.signal_by_polling(flow_run_id)
        if api.gate is not None:
            api.gate.set()
        await asyncio.sleep(0.1)
        assert stream.attempts == attempts
        case.callback.assert_not_called()
        case.on_failure.assert_not_called()


@pytest.mark.usefixtures("timer")
class TestCancellationDispatch:
    @pytest.fixture
    def case(self, api: FakeAPI) -> RecoveryCase:
        return RecoveryCase("cancelling", api)

    async def test_rejected_event_callback_is_retried_by_polling(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        connection = ScriptedConnection()
        stream.script = [connection]
        flow_run_id, still_running = uuid.uuid4(), uuid.uuid4()
        accepted: list[uuid.UUID] = []

        def accept(flow_run_id: uuid.UUID) -> None:
            if case.callback.call_count == 1:
                raise RuntimeError("Cancellation dispatch was not accepted")
            accepted.append(flow_run_id)

        case.callback.side_effect = accept
        case.signal_by_polling(flow_run_id)

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            # Keep polling observable after the cancellation has been accepted.
            case.observer.add_in_flight_flow_run_id(still_running)
            connection.send(cancelling_event(flow_run_id))
            await until(lambda: api.reads >= 6)

            assert case.notified == [flow_run_id, flow_run_id]
            assert accepted == [flow_run_id]
            case.on_failure.assert_not_called()

    async def test_rejected_poll_callback_reports_unavailability(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        stream.script = [ConnectionError("down")]
        flow_run_id, still_running = uuid.uuid4(), uuid.uuid4()
        case.callback.side_effect = RuntimeError(
            "Cancellation dispatch was not accepted"
        )
        case.signal_by_polling(flow_run_id)

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            case.observer.add_in_flight_flow_run_id(still_running)
            await until(lambda: case.on_failure.called)

        case.callback.assert_called_once_with(flow_run_id)
        case.on_failure.assert_called_once_with({flow_run_id, still_running})

    async def test_replayed_event_after_poll_notifies_once(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
    ):
        caplog.set_level("INFO", logger="prefect.FlowRunCancellingObserver")
        connection = ScriptedConnection()
        stream.script = [ConnectionError("down"), connection]
        flow_run_id, other_flow_run_id = uuid.uuid4(), uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            case.observer.add_in_flight_flow_run_id(other_flow_run_id)
            case.signal_by_polling(flow_run_id)
            await until(lambda: case.notified == [flow_run_id])

            await timer.fire()
            await until(lambda: restored(caplog) == 1)
            connection.send(cancelling_event(flow_run_id))
            connection.send(cancelling_event(other_flow_run_id))
            await until(lambda: len(case.notified) == 2)

        assert case.notified == [flow_run_id, other_flow_run_id]

    async def test_event_before_inflight_poll_and_reconciliation_notifies_once(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
    ):
        caplog.set_level("INFO", logger="prefect.FlowRunCancellingObserver")
        first, second = ScriptedConnection(), ScriptedConnection()
        stream.script = [first, second]
        flow_run_id = uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            api.gate = asyncio.Event()
            first.send(CLOSE)
            # A poll and then the reconciliation check are waiting on reads
            await until(lambda: api.waiting == 1)
            await timer.fire()
            await until(lambda: api.waiting == 2)

            second.send(cancelling_event(flow_run_id))
            await until(lambda: case.notified == [flow_run_id])

            case.signal_by_polling(flow_run_id)
            api.gate.set()
            await until(lambda: restored(caplog) == 1)

        assert case.notified == [flow_run_id]

    async def test_removed_registration_ignores_inflight_poll(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        flow_run_id, other_flow_run_id = uuid.uuid4(), uuid.uuid4()

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(other_flow_run_id)
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            api.gate = asyncio.Event()
            await until(lambda: api.waiting == 1)

            case.observer.remove_in_flight_flow_run_id(flow_run_id)
            case.signal_by_polling(flow_run_id)
            api.gate.set()
            # The in-flight poll and the next full poll complete
            await until(lambda: api.reads >= 4)

        case.callback.assert_not_called()

    async def test_replaced_registration_ignores_inflight_poll(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        flow_run_id = uuid.uuid4()
        stale_poll, later_polls = asyncio.Event(), asyncio.Event()

        async def hold(read: int) -> None:
            # A poll makes two reads; only the stale poll is released at first
            await (stale_poll if read <= 2 else later_polls).wait()

        api.hold = hold

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: api.waiting == 1)

            case.observer.remove_in_flight_flow_run_id(flow_run_id)
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            case.signal_by_polling(flow_run_id)
            stale_poll.set()
            await until(lambda: api.reads == 3)
            case.callback.assert_not_called()

            later_polls.set()
            await until(lambda: case.notified == [flow_run_id])

        assert case.notified == [flow_run_id]

    async def test_readded_registration_is_notified_again(
        self,
        case: RecoveryCase,
        stream: ScriptedEventStream,
        api: FakeAPI,
    ):
        flow_run_id = uuid.uuid4()
        case.signal_by_polling(flow_run_id)

        async with case.observer:
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: case.notified == [flow_run_id])
            await asyncio.sleep(0.05)
            assert case.notified == [flow_run_id]

            case.observer.remove_in_flight_flow_run_id(flow_run_id)
            case.observer.add_in_flight_flow_run_id(flow_run_id)
            await until(lambda: case.notified == [flow_run_id, flow_run_id])


@pytest.mark.usefixtures("timer")
class TestSuspensionRecovery:
    async def test_replay_after_resume_still_notifies(
        self,
        stream: ScriptedEventStream,
        api: FakeAPI,
        timer: ReconnectTimer,
        caplog: pytest.LogCaptureFixture,
    ):
        caplog.set_level("INFO", logger="prefect.FlowRunSuspendingObserver")
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(
            on_suspended=callback, polling_interval=0.01
        )
        connection = ScriptedConnection()
        stream.script = [ConnectionError("down"), connection]
        flow_run_id = uuid.uuid4()
        started = cast(DateTime, now("UTC"))
        api.states[flow_run_id] = Running(timestamp=started)

        async with observer:
            await observer.watch_flow_run_id(flow_run_id)

            # Suspended and resumed between polls; the run is scheduled again
            suspended_at = started + timedelta(seconds=1)
            suspended_state_id = uuid.uuid4()
            api.states[flow_run_id] = Scheduled(
                timestamp=started + timedelta(seconds=2)
            )

            await timer.fire()
            await until(lambda: restored(caplog) == 1)
            # A replayed event from before the watch started is still ignored
            connection.send(
                suspension_event(
                    flow_run_id, uuid.uuid4(), started - timedelta(seconds=1)
                )
            )
            connection.send(
                suspension_event(flow_run_id, suspended_state_id, suspended_at)
            )
            await until(lambda: callback.called)

        callback.assert_called_once()
        notified_flow_run_id, state = callback.call_args.args
        assert notified_flow_run_id == flow_run_id
        assert state.id == suspended_state_id
        assert is_suspended_flow_run_state(state)
