import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from io import StringIO
from time import sleep
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_kubernetes._logging import KopfObjectJsonFormatter
from prefect_kubernetes.observer import (
    _replicate_pod_event,
    start_observer,
    stop_observer,
)

from prefect.events.schemas.events import RelatedResource, Resource


@pytest.fixture
def mock_events_client(monkeypatch: pytest.MonkeyPatch):
    events_client = AsyncMock()

    @asynccontextmanager
    async def mock_get_events_client():
        try:
            yield events_client
        finally:
            pass

    monkeypatch.setattr(
        "prefect_kubernetes.observer.get_events_client", mock_get_events_client
    )
    monkeypatch.setattr("prefect_kubernetes.observer.events_client", events_client)
    return events_client


@pytest.fixture
def mock_orchestration_client(monkeypatch: pytest.MonkeyPatch):
    orchestration_client = AsyncMock()
    json_response = MagicMock()
    json_response.json.return_value = {"events": [{"id": "existing-event"}]}
    orchestration_client.request.return_value = json_response

    @asynccontextmanager
    async def mock_get_orchestration_client():
        try:
            yield orchestration_client
        finally:
            pass

    monkeypatch.setattr(
        "prefect_kubernetes.observer.get_client",
        mock_get_orchestration_client,
    )
    monkeypatch.setattr(
        "prefect_kubernetes.observer.orchestration_client", orchestration_client
    )
    # Initialize the startup event semaphore for tests
    monkeypatch.setattr(
        "prefect_kubernetes.observer._startup_event_semaphore",
        asyncio.Semaphore(5),
    )
    return orchestration_client


class TestReplicatePodEvent:
    async def test_minimal(self, mock_events_client: AsyncMock):
        flow_run_id = uuid.uuid4()
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "ADDED", "status": {"phase": "Running"}},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == "prefect.kubernetes.pod.running"
        assert emitted_event.resource == Resource(
            {
                "prefect.resource.id": f"prefect.kubernetes.pod.{pod_id}",
                "prefect.resource.name": "test",
                "kubernetes.namespace": "test",
            }
        )
        assert emitted_event.related == [
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": "test",
                }
            )
        ]

    async def test_deterministic_event_id(self, mock_events_client: AsyncMock):
        """Test that the event ID is deterministic"""
        pod_id = uuid.uuid4()
        await _replicate_pod_event(
            event={"type": "ADDED", "status": {"phase": "Running"}},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        first_event_id = mock_events_client.emit.call_args[1]["event"].id
        mock_events_client.emit.reset_mock()

        # Call the function again
        await _replicate_pod_event(
            event={"type": "ADDED", "status": {"phase": "Running"}},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        second_event_id = mock_events_client.emit.call_args[1]["event"].id
        assert first_event_id == second_event_id

    async def test_evicted_pod(self, mock_events_client: AsyncMock):
        """Test handling of evicted pods"""
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Failed",
                "container_statuses": [
                    {"state": {"terminated": {"reason": "OOMKilled"}}}
                ],
            },
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == "prefect.kubernetes.pod.evicted"
        assert emitted_event.resource == Resource(
            {
                "prefect.resource.id": f"prefect.kubernetes.pod.{pod_id}",
                "prefect.resource.name": "test",
                "kubernetes.namespace": "test",
                "kubernetes.reason": "OOMKilled",
            },
        )

    async def test_all_related_resources(self, mock_events_client: AsyncMock):
        """Test that all possible related resources are included"""
        flow_run_id = uuid.uuid4()
        deployment_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        work_pool_id = uuid.uuid4()
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
                "prefect.io/deployment-id": str(deployment_id),
                "prefect.io/deployment-name": "test-deployment",
                "prefect.io/flow-id": str(flow_id),
                "prefect.io/flow-name": "test-flow",
                "prefect.io/work-pool-id": str(work_pool_id),
                "prefect.io/work-pool-name": "test-pool",
                "prefect.io/worker-name": "test-worker",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        mock_events_client.emit.assert_called_once()
        emitted_event = mock_events_client.emit.call_args[1]["event"]
        related_resources = emitted_event.related

        # Verify all related resources are present
        resource_ids = {
            r.model_dump()["prefect.resource.id"] for r in related_resources
        }
        assert resource_ids == {
            f"prefect.flow-run.{flow_run_id}",
            f"prefect.deployment.{deployment_id}",
            f"prefect.flow.{flow_id}",
            f"prefect.work-pool.{work_pool_id}",
            "prefect.worker.kubernetes.test-worker",
        }

        resource_names = {
            r.model_dump()["prefect.resource.name"] for r in related_resources
        }
        assert resource_names == {
            "test-run",
            "test-deployment",
            "test-flow",
            "test-pool",
            "test-worker",
        }

    async def test_event_deduplication(
        self, mock_events_client: AsyncMock, mock_orchestration_client: AsyncMock
    ):
        """Test that checks from existing events when receiving events on startup"""
        pod_id = uuid.uuid4()
        await _replicate_pod_event(
            # Event types with None are received when reading current cluster state
            event={"type": None},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={"prefect.io/flow-run-id": str(uuid.uuid4())},
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        # Verify the request was made with correct payload structure
        mock_orchestration_client.request.assert_called_once()
        call_args = mock_orchestration_client.request.call_args
        assert call_args[0] == ("POST", "/events/filter")

        # Verify the json payload has the correct structure: {"filter": {...}}
        json_payload = call_args[1]["json"]
        assert "filter" in json_payload, "Expected 'filter' key in json payload"

        # Verify the nested filter contains expected fields
        event_filter = json_payload["filter"]
        assert "event" in event_filter, "Expected 'event' field in filter"
        assert "resource" in event_filter, "Expected 'resource' field in filter"
        assert "occurred" in event_filter, "Expected 'occurred' field in filter"

        # Verify no event was emitted since one already existed
        mock_events_client.emit.assert_not_called()

    @pytest.mark.parametrize("phase", ["Pending", "Running", "Succeeded", "Failed"])
    async def test_different_phases(self, mock_events_client: AsyncMock, phase: str):
        """Test handling of different pod phases"""
        pod_id = uuid.uuid4()
        flow_run_id = uuid.uuid4()

        mock_events_client.emit.reset_mock()
        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": phase},
            logger=MagicMock(),
        )

        mock_events_client.emit.assert_called_once()
        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == f"prefect.kubernetes.pod.{phase.lower()}"

    async def test_startup_event_semaphore_limits_concurrency(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that startup event deduplication respects semaphore concurrency limit"""
        # Track concurrent requests
        concurrent_count = 0
        max_concurrent = 0
        semaphore_limit = 2

        # Set up a semaphore with a small limit for testing
        monkeypatch.setattr(
            "prefect_kubernetes.observer._startup_event_semaphore",
            asyncio.Semaphore(semaphore_limit),
        )

        # Configure mock to return no existing events so we can track the full request
        json_response = MagicMock()
        json_response.json.return_value = {"events": []}
        mock_orchestration_client.request.return_value = json_response

        async def slow_request(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate network delay
            concurrent_count -= 1
            return json_response

        mock_orchestration_client.request.side_effect = slow_request

        # Launch multiple startup events concurrently
        tasks = []
        for i in range(5):
            tasks.append(
                asyncio.create_task(
                    _replicate_pod_event(
                        event={"type": None},
                        uid=str(uuid.uuid4()),
                        name=f"test-{i}",
                        namespace="test",
                        labels={
                            "prefect.io/flow-run-id": str(uuid.uuid4()),
                            "prefect.io/flow-run-name": f"test-run-{i}",
                        },
                        status={"phase": "Running"},
                        logger=MagicMock(),
                    )
                )
            )

        await asyncio.gather(*tasks)

        # Verify the semaphore limited concurrency
        assert max_concurrent <= semaphore_limit, (
            f"Expected max {semaphore_limit} concurrent requests, but got {max_concurrent}"
        )
        # Verify all requests were eventually made
        assert mock_orchestration_client.request.call_count == 5


class TestStartAndStopObserver:
    @pytest.mark.timeout(10)
    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_start_and_stop(self, monkeypatch: pytest.MonkeyPatch):
        """
        Test that the observer can be started and stopped without errors
        and without hanging.
        """
        start_observer()
        sleep(1)
        stop_observer()


class TestLoggingConfiguration:
    """Tests for the logging configuration logic in start_observer()"""

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_json_formatter_configures_kopf_logger(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that when Prefect uses JSON formatting, kopf logger gets its own
        handler with KopfObjectJsonFormatter and propagation is disabled.
        """
        # Stop any existing observer first
        stop_observer()

        # Set up Prefect to use JSON formatting
        monkeypatch.setenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER", "json")

        # Import and setup logging fresh to pick up env var
        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear any existing kopf logger configuration
        kopf_logger = logging.getLogger("kopf")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        # Start the observer which should configure kopf logging
        try:
            start_observer()
            sleep(0.5)  # Give it time to configure

            # Verify kopf logger has its own handler
            assert len(kopf_logger.handlers) > 0, "kopf logger should have a handler"

            # Verify the handler has the correct formatter
            handler = kopf_logger.handlers[0]
            assert isinstance(handler.formatter, KopfObjectJsonFormatter), (
                f"Expected KopfObjectJsonFormatter, got {type(handler.formatter)}"
            )

            # Verify propagation is disabled
            assert kopf_logger.propagate is False, (
                "kopf logger propagation should be disabled"
            )
        finally:
            stop_observer()
            monkeypatch.delenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER")

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_standard_formatter_uses_default_behavior(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that when Prefect uses standard formatting (default),
        kopf logger uses default propagation behavior.
        """
        # Stop any existing observer first
        stop_observer()

        # Use default logging configuration (standard formatter)
        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear any existing kopf logger configuration
        kopf_logger = logging.getLogger("kopf")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        # Start the observer
        try:
            start_observer()
            sleep(0.5)

            # Verify kopf logger doesn't have a dedicated handler added by start_observer
            # (it should propagate to root logger since we're using standard formatting)
            assert len(kopf_logger.handlers) == 0, (
                "kopf logger should not have handlers with standard formatting"
            )

            # Verify propagation is still enabled (default behavior)
            assert kopf_logger.propagate is True, (
                "kopf logger propagation should remain enabled with standard formatting"
            )
        finally:
            stop_observer()

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_no_duplicate_logs_with_json_formatting(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that kopf logs don't appear duplicated when JSON formatting is enabled.
        """
        # Stop any existing observer first
        stop_observer()

        # Set up JSON formatting
        monkeypatch.setenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER", "json")

        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear kopf logger
        kopf_logger = logging.getLogger("kopf.test")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        try:
            start_observer()
            sleep(0.5)

            # Create a custom handler to capture logs
            # (caplog won't work since propagation is disabled)
            captured_logs: list[logging.LogRecord] = []

            class CaptureHandler(logging.Handler):
                def emit(self, record: logging.LogRecord):
                    captured_logs.append(record)

            capture_handler = CaptureHandler()
            kopf_logger.addHandler(capture_handler)

            # Emit a test message
            kopf_logger.warning("Test message for duplicate check")

            # Count how many times the message appears
            matching_records = [
                r
                for r in captured_logs
                if "Test message for duplicate check" in r.message
            ]

            assert len(matching_records) == 1, (
                f"Expected 1 log message, got {len(matching_records)}"
            )
        finally:
            stop_observer()
            monkeypatch.delenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER")

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_kopf_logs_visible_with_json_formatting(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that kopf logs are actually emitted and visible when JSON formatting is enabled.
        """
        # Stop any existing observer first
        stop_observer()

        # Set up JSON formatting
        monkeypatch.setenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER", "json")

        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear kopf logger
        kopf_logger = logging.getLogger("kopf.test")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        try:
            start_observer()
            sleep(0.5)

            # Create a string buffer to capture output
            log_capture = StringIO()
            test_handler = logging.StreamHandler(log_capture)
            test_handler.setFormatter(KopfObjectJsonFormatter())
            kopf_logger.addHandler(test_handler)

            # Emit a test log message
            kopf_logger.warning("Test message for visibility check")

            # Get the captured output
            log_output = log_capture.getvalue()

            # Verify the message was emitted
            assert "Test message for visibility check" in log_output, (
                "kopf log message should be visible in output"
            )

            # Verify it's JSON formatted
            assert '"message"' in log_output or '"msg"' in log_output, (
                "Log output should be JSON formatted"
            )
        finally:
            stop_observer()
            monkeypatch.delenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER")
