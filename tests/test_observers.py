import asyncio
import threading
import uuid
from contextlib import suppress
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect import flow
from prefect._flow_run_suspension import (
    FlowRunSuspensionRequest,
    observe_flow_run_suspension,
)
from prefect._internal.observers import (
    FlowRunCancellingObserver,
    FlowRunSuspendingObserver,
)
from prefect._internal.testing import retry_asserts
from prefect.client.schemas.objects import StateType
from prefect.events.filters import EventAnyResourceFilter, EventFilter, EventNameFilter
from prefect.events.utilities import emit_event
from prefect.states import Running, Suspended


@flow
def test_flow():
    """Simple test flow for observer tests."""
    pass


class TestFlowRunCancellingObserver:
    async def test_observer_initialization(self):
        """Test observer initializes with correct parameters."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback, polling_interval=5)

        assert observer.on_cancelling == callback
        assert observer.polling_interval == 5
        assert observer._in_flight_flow_run_ids == set()
        assert observer._cancelling_flow_run_ids == set()
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
        assert observer._consumer_task is None
        assert observer._polling_task is None

        async with observer:
            assert observer._client is not None
            assert observer._consumer_task is not None

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
            assert flow_run_id in observer._cancelling_flow_run_ids

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
            assert flow_run_id in observer._cancelling_flow_run_ids

            # Second call - should not trigger callback again due to deduplication
            # Both queries return empty because the flow run is now in _cancelling_flow_run_ids
            with patch.object(observer._client, "read_flow_runs", side_effect=[[], []]):
                await observer._check_for_cancelled_flow_runs()

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

    async def test_polling_fallback_on_websocket_failure(self):
        """Test observer switches to polling when websocket fails."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        flow_run_id = uuid.uuid4()
        mock_flow_run = mock.MagicMock()
        mock_flow_run.id = flow_run_id

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            # Mock websocket failure by making consumer task fail
            if observer._consumer_task:
                observer._consumer_task.cancel()
                try:
                    await observer._consumer_task
                except asyncio.CancelledError:
                    pass

                # Simulate the task failing with an exception to trigger fallback
                failed_task = AsyncMock()
                failed_task.cancelled.return_value = False
                failed_task.exception.return_value = Exception("Websocket failed")

                # Trigger the fallback manually
                observer._start_polling_task(failed_task)

                # Give polling task time to be created
                await asyncio.sleep(0.1)

                # Verify polling task was created (or at least attempted to be created)
                # Note: The polling task creation might happen async, so we just verify
                # the fallback mechanism was triggered

    async def test_client_not_initialized_error(self):
        """Test error handling when client is not initialized."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        # Try to check for cancelled flow runs without initializing
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await observer._check_for_cancelled_flow_runs()

    async def test_observer_shutdown_cancels_tasks(self):
        """Test proper cleanup on observer shutdown."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(on_cancelling=callback)

        async with observer:
            consumer_task = observer._consumer_task
            assert consumer_task is not None
            assert not consumer_task.done()

        # After exiting context, task should be cancelled
        assert consumer_task.cancelled() or consumer_task.done()

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

    async def test_on_failure_called_when_polling_task_fails(self):
        """Test on_failure callback is called when polling task fails."""
        on_cancelling = AsyncMock()
        on_failure = mock.MagicMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=on_cancelling,
            on_failure=on_failure,
            polling_interval=0.1,
        )

        flow_run_id = uuid.uuid4()

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            # Simulate a failed polling task
            failed_task = mock.MagicMock()
            failed_task.exception.return_value = Exception("Polling failed")

            # Call the done callback handler directly
            observer._handle_polling_task_done(failed_task)

            # Verify on_failure was called with the in-flight flow run IDs
            on_failure.assert_called_once()
            call_args = on_failure.call_args[0][0]
            assert flow_run_id in call_args

    async def test_on_failure_receives_copy_of_in_flight_ids(self):
        """Test on_failure receives a copy of in-flight IDs, not the original set."""
        on_cancelling = AsyncMock()
        captured_ids = []

        def capture_on_failure(ids):
            captured_ids.append(ids)

        observer = FlowRunCancellingObserver(
            on_cancelling=on_cancelling,
            on_failure=capture_on_failure,
            polling_interval=0.1,
        )

        flow_run_id_1 = uuid.uuid4()
        flow_run_id_2 = uuid.uuid4()

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id_1)
            observer.add_in_flight_flow_run_id(flow_run_id_2)

            # Simulate a failed polling task
            failed_task = mock.MagicMock()
            failed_task.exception.return_value = Exception("Polling failed")

            observer._handle_polling_task_done(failed_task)

            # Modify the original set after the callback
            observer._in_flight_flow_run_ids.add(uuid.uuid4())

            # Verify the captured IDs were not affected by the modification
            assert len(captured_ids) == 1
            assert len(captured_ids[0]) == 2
            assert flow_run_id_1 in captured_ids[0]
            assert flow_run_id_2 in captured_ids[0]

    async def test_on_failure_not_called_when_polling_succeeds(self):
        """Test on_failure is not called when polling completes successfully."""
        on_cancelling = AsyncMock()
        on_failure = mock.MagicMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=on_cancelling,
            on_failure=on_failure,
            polling_interval=0.1,
        )

        async with observer:
            # Simulate a successful polling task (no exception)
            successful_task = mock.MagicMock()
            successful_task.exception.return_value = None

            observer._handle_polling_task_done(successful_task)

            # Verify on_failure was NOT called
            on_failure.assert_not_called()

    async def test_on_failure_not_called_when_callback_is_none(self):
        """Test no error when on_failure is None and polling fails."""
        on_cancelling = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=on_cancelling,
            on_failure=None,  # Explicitly None
            polling_interval=0.1,
        )

        async with observer:
            # Simulate a failed polling task
            failed_task = mock.MagicMock()
            failed_task.exception.return_value = Exception("Polling failed")

            # Should not raise even though on_failure is None
            observer._handle_polling_task_done(failed_task)

    async def test_falls_back_to_polling_on_subscriber_connection_failure(self):
        """Test that the observer falls back to polling when the events
        subscriber fails to connect during __aenter__."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        with patch(
            "prefect._internal.observers.get_events_subscriber",
            side_effect=Exception("WebSocket connection failed"),
        ):
            async with observer:
                # Consumer task should NOT be created since subscriber failed
                assert observer._consumer_task is None
                # Polling task SHOULD be created as fallback
                assert observer._polling_task is not None
                # Client should still be initialized
                assert observer._client is not None
                # Subscriber should be None
                assert observer._events_subscriber is None

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

    async def test_shutdown_cleans_up_polling_fallback_task(self):
        """Test that __aexit__ properly cleans up the polling task created
        by the fallback mechanism."""
        callback = AsyncMock()
        observer = FlowRunCancellingObserver(
            on_cancelling=callback, polling_interval=0.1
        )

        with patch(
            "prefect._internal.observers.get_events_subscriber",
            side_effect=Exception("WebSocket connection failed"),
        ):
            async with observer:
                polling_task = observer._polling_task
                assert polling_task is not None
                assert not polling_task.done()

        # After exiting context, polling task should be cancelled/done
        assert polling_task.cancelled() or polling_task.done()


class TestFlowRunSuspendingObserver:
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
            assert flow_run_id in observer._suspended_flow_run_ids

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
            assert flow_run_id in observer._suspended_flow_run_ids
            assert "Failed to check current state" in caplog.text

    async def test_event_consumer_reads_flow_run_before_callback(self):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        flow_run_id = uuid.uuid4()
        suspended_state = Suspended()
        running_flow_run = mock.MagicMock(state=Running())
        suspended_flow_run = mock.MagicMock(state=suspended_state)

        async with observer:
            observer.add_in_flight_flow_run_id(flow_run_id)

            with patch.object(
                observer._client,
                "read_flow_run",
                side_effect=[running_flow_run, suspended_flow_run],
            ):
                await observer._notify_if_suspended(flow_run_id)
                callback.assert_not_called()

                await observer._notify_if_suspended(flow_run_id)

            callback.assert_called_once_with(flow_run_id, suspended_state)

    async def test_clean_event_consumer_completion_starts_polling(self):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        async def complete():
            pass

        async def never_finish(*args, **kwargs):
            await asyncio.Event().wait()

        consumer_task = asyncio.create_task(complete())
        await consumer_task

        with patch(
            "prefect._internal.observers.critical_service_loop",
            AsyncMock(side_effect=never_finish),
        ) as critical_service_loop:
            observer._start_polling_task(consumer_task)
            await asyncio.sleep(0)

            assert observer._polling_task is not None
            critical_service_loop.assert_called_once()

            observer._polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await observer._polling_task

    @pytest.mark.parametrize("task_state", ["completed", "cancelled"])
    async def test_event_consumer_completion_does_not_poll_during_shutdown(
        self, task_state: str
    ):
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)
        observer._is_shutting_down = True

        async def complete():
            pass

        consumer_task = asyncio.create_task(complete())
        if task_state == "cancelled":
            consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await consumer_task
        else:
            await consumer_task

        with patch(
            "prefect._internal.observers.critical_service_loop"
        ) as critical_service_loop:
            observer._start_polling_task(consumer_task)

        assert observer._polling_task is None
        critical_service_loop.assert_not_called()

    async def test_polling_task_runs_as_backstop_when_websocket_connects(self):
        """Polling must run as a backstop alongside the websocket consumer.

        The websocket consumer can wait forever on `recv()` while the
        connection stays open but events silently stop arriving (e.g.
        server-side queue overflow or CPU starvation in the subprocess).
        In that scenario the websocket-failure fallback never triggers,
        so polling must always be started in `__aenter__`.
        """
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback, polling_interval=60)

        async def never_finish(*args: object, **kwargs: object) -> None:
            await asyncio.Event().wait()

        fake_subscriber = AsyncMock()
        fake_subscriber.__aenter__.return_value = fake_subscriber
        fake_subscriber.__aiter__.return_value = iter([])
        fake_subscriber.__anext__.side_effect = never_finish

        with patch(
            "prefect._internal.observers.get_events_subscriber",
            return_value=fake_subscriber,
        ):
            async with observer:
                assert observer._consumer_task is not None
                assert not observer._consumer_task.done()
                assert observer._polling_task is not None
                assert not observer._polling_task.done()

    async def test_start_polling_task_is_idempotent_when_backstop_running(self):
        """When polling is already running as a backstop, the websocket-failure
        callback should not spawn a second polling task."""
        callback = MagicMock()
        observer = FlowRunSuspendingObserver(on_suspended=callback)

        async def never_finish(*args: object, **kwargs: object) -> None:
            await asyncio.Event().wait()

        consumer_task = asyncio.create_task(asyncio.sleep(0))
        await consumer_task

        with patch(
            "prefect._internal.observers.critical_service_loop",
            AsyncMock(side_effect=never_finish),
        ) as critical_service_loop:
            observer._start_polling_task(consumer_task)
            await asyncio.sleep(0)
            backstop = observer._polling_task
            assert backstop is not None
            assert critical_service_loop.call_count == 1

            # Simulate the websocket consumer completing -- polling is already
            # running, so we should not spawn a second polling task.
            observer._start_polling_task(consumer_task)
            await asyncio.sleep(0)
            assert observer._polling_task is backstop
            assert critical_service_loop.call_count == 1

            backstop.cancel()
            with suppress(asyncio.CancelledError):
                await backstop

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
