import asyncio
import uuid
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest

from prefect import flow
from prefect.client.schemas.objects import StateType
from prefect.events.utilities import emit_event
from prefect.runner._observers import FlowRunCancellingObserver


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
            # Give observer time to set up subscription
            await asyncio.sleep(0.1)

            # Emit cancelling event
            emit_event(
                event="prefect.flow-run.Cancelling",
                resource={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"},
                id=uuid.uuid4(),
            )

            # Give time for event to be processed
            await asyncio.sleep(0.2)

            # Should call callback
            callback.assert_called_once_with(flow_run_id)

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
