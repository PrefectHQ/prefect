"""
Tests for NodeTaskTracker class and related functionality.
"""

import threading
import time
from typing import Any, Dict
from unittest.mock import Mock
from uuid import UUID

import pytest
from prefect_dbt.core._tracker import NodeTaskTracker

from prefect.client.schemas.objects import Flow, State
from prefect.logging.loggers import PrefectLogAdapter
from prefect.tasks import Task


@pytest.fixture
def mock_task():
    """Create a mock Task instance."""
    task = Mock(spec=Task)
    task.name = "test_task"
    return task


@pytest.fixture
def mock_flow():
    """Create a mock Flow instance."""
    flow = Mock(spec=Flow)
    flow.name = "test_flow"
    return flow


@pytest.fixture
def mock_state():
    """Create a mock State instance."""
    state = Mock(spec=State)
    state.id = "test-state-id"
    return state


@pytest.fixture
def sample_node_id():
    """Sample node ID for testing."""
    return "model.test_project.test_model"


@pytest.fixture
def sample_task_run_id():
    """Sample task run ID for testing."""
    return UUID("12345678-1234-5678-9abc-123456789abc")


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "node_info": {
            "unique_id": "model.test_project.test_model",
            "node_status": "success",
        },
        "status": "success",
    }


@pytest.fixture
def sample_flow_run_context():
    """Sample flow run context for testing."""
    return {
        "id": "test-flow-run-id",
        "name": "test_flow_run",
    }


class TestNodeTaskTrackerInitialization:
    """Test NodeTaskTracker initialization and basic functionality."""

    def test_initializes_with_empty_state(self):
        """Test that tracker initializes with empty internal state."""
        tracker = NodeTaskTracker()

        # Verify all internal collections are empty by testing public methods
        assert tracker.get_task_result("unknown") is None
        assert tracker.get_node_status("unknown") is None
        assert tracker.is_node_complete("unknown") is False
        assert tracker.get_node_dependencies("unknown") == []
        assert tracker.get_task_run_id("unknown") is None
        assert tracker.get_task_run_name("unknown") is None

    def test_start_task_registers_task_and_creates_event(
        self, mock_task: Mock, sample_node_id: str
    ):
        """Test that start_task properly registers a task and creates completion event."""
        tracker = NodeTaskTracker()

        tracker.start_task(sample_node_id, mock_task)

        # Verify node is marked as incomplete initially
        assert tracker.is_node_complete(sample_node_id) is False

        # Verify we can wait for completion (indicates event was created)
        # Start a thread to complete the node
        def complete_node():
            time.sleep(0.01)
            tracker.set_node_status(sample_node_id, {}, "completed")

        thread = threading.Thread(target=complete_node)
        thread.daemon = True
        thread.start()

        # Wait for completion
        result = tracker.wait_for_node_completion(sample_node_id, timeout=0.1)
        assert result is True


class TestNodeTaskTrackerStatusManagement:
    """Test node status management functionality."""

    def test_set_node_status_stores_status_and_marks_complete(
        self, sample_node_id: str, sample_event_data: Dict[str, Any]
    ):
        """Test that set_node_status stores status and marks node as complete."""
        tracker = NodeTaskTracker()
        event_message = "Node completed successfully"

        tracker.set_node_status(sample_node_id, sample_event_data, event_message)

        # Verify status is stored
        stored_status = tracker.get_node_status(sample_node_id)
        assert stored_status is not None
        assert stored_status["event_data"] == sample_event_data
        assert stored_status["event_message"] == event_message
        # Verify node is marked as complete
        assert tracker.is_node_complete(sample_node_id) is True

    def test_set_node_status_signals_completion_event(
        self, sample_node_id, sample_event_data
    ):
        """Test that set_node_status signals the completion event."""
        tracker = NodeTaskTracker()
        tracker.start_task(sample_node_id, Mock(spec=Task))

        # Verify event is not set initially
        assert not tracker._node_events[sample_node_id].is_set()

        # Set status
        tracker.set_node_status(sample_node_id, sample_event_data, "completed")

        # Verify event is now set
        assert tracker._node_events[sample_node_id].is_set()


class TestNodeTaskTrackerCompletionWaiting:
    """Test node completion waiting functionality."""

    @pytest.mark.parametrize(
        "timeout,expected_result",
        [
            (1.0, True),
            (None, True),
        ],
    )
    def test_wait_for_node_completion_when_complete(
        self, sample_node_id, sample_event_data, timeout, expected_result
    ):
        """Test that wait_for_node_completion returns True when node is already complete."""
        tracker = NodeTaskTracker()
        tracker.set_node_status(sample_node_id, sample_event_data, "completed")

        result = tracker.wait_for_node_completion(sample_node_id, timeout=timeout)

        assert result == expected_result

    def test_wait_for_node_completion_waits_for_completion(
        self, sample_node_id, sample_event_data
    ):
        """Test that wait_for_node_completion waits for node to complete."""
        tracker = NodeTaskTracker()
        tracker.start_task(sample_node_id, Mock(spec=Task))

        # Start a thread that will complete the node after a delay
        def complete_node():
            time.sleep(0.05)
            tracker.set_node_status(sample_node_id, sample_event_data, "completed")

        thread = threading.Thread(target=complete_node)
        thread.daemon = True
        thread.start()

        # Wait for completion
        result = tracker.wait_for_node_completion(sample_node_id, timeout=1.0)

        assert result is True
        assert tracker.is_node_complete(sample_node_id) is True


class TestNodeTaskTrackerTaskResults:
    """Test task result management functionality."""

    @pytest.mark.parametrize(
        "result_value",
        [
            Mock(spec=State),
            None,
        ],
    )
    def test_task_result_set_and_get(self, sample_node_id, result_value):
        """Test that set_task_result stores and get_task_result retrieves the result."""
        tracker = NodeTaskTracker()

        # Set result
        tracker.set_task_result(sample_node_id, result_value)

        # Get result
        retrieved_result = tracker.get_task_result(sample_node_id)

        # Verify result matches
        assert retrieved_result == result_value
        assert tracker._task_results[sample_node_id] == result_value


class TestNodeTaskTrackerDependencies:
    """Test dependency management functionality."""

    @pytest.mark.parametrize(
        "dependencies",
        [
            ["dep1", "dep2", "dep3"],
            [],
        ],
    )
    def test_node_dependencies_set_and_get(self, sample_node_id, dependencies):
        """Test that set_node_dependencies stores and get_node_dependencies retrieves dependencies."""
        tracker = NodeTaskTracker()

        # Set dependencies
        tracker.set_node_dependencies(sample_node_id, dependencies)

        # Get dependencies
        retrieved_dependencies = tracker.get_node_dependencies(sample_node_id)

        # Verify dependencies match
        assert retrieved_dependencies == dependencies
        assert tracker._node_dependencies[sample_node_id] == dependencies


class TestNodeTaskTrackerTaskRunIds:
    """Test task run ID management functionality."""

    def test_task_run_id_set_and_get(self, sample_node_id, sample_task_run_id):
        """Test that set_task_run_id stores and get_task_run_id retrieves the task run ID."""
        tracker = NodeTaskTracker()

        # Set task run ID
        tracker.set_task_run_id(sample_node_id, sample_task_run_id)

        # Get task run ID
        retrieved_id = tracker.get_task_run_id(sample_node_id)

        # Verify ID matches
        assert retrieved_id == sample_task_run_id
        assert tracker._task_run_ids[sample_node_id] == sample_task_run_id


class TestNodeTaskTrackerTaskRunNames:
    """Test task run name management functionality."""

    def test_task_run_name_set_and_get(self, sample_node_id):
        """Test that set_task_run_name stores and get_task_run_name retrieves the task run name."""
        tracker = NodeTaskTracker()
        task_run_name = "test_task_run"

        # Set task run name
        tracker.set_task_run_name(sample_node_id, task_run_name)

        # Get task run name
        retrieved_name = tracker.get_task_run_name(sample_node_id)

        # Verify name matches
        assert retrieved_name == task_run_name
        assert tracker._task_run_names[sample_node_id] == task_run_name


class TestNodeTaskTrackerLogging:
    """Test logging functionality."""

    @pytest.mark.parametrize(
        "flow_context",
        [
            (None, None),
            ({"id": "test-id", "name": "test_name"}, None),
            (None, Mock(spec=Flow)),
            ({"id": "test-flow-run-id", "name": "test_flow_run"}, Mock(spec=Flow)),
        ],
    )
    def test_get_task_logger_with_various_contexts(
        self, sample_node_id, sample_task_run_id, flow_context
    ):
        """Test that get_task_logger works with various flow context combinations."""
        tracker = NodeTaskTracker()
        tracker.set_task_run_id(sample_node_id, sample_task_run_id)
        tracker.set_task_run_name(sample_node_id, "test_task_run")

        flow_run, flow = flow_context

        # Configure mock flow if present
        if flow is not None:
            flow.name = "test_flow"

        logger = tracker.get_task_logger(
            sample_node_id,
            flow_run=flow_run,
            flow=flow,
        )

        assert isinstance(logger, PrefectLogAdapter)
        assert logger.extra["task_run_id"] == sample_task_run_id
        assert logger.extra["task_run_name"] == "test_task_run"
        assert logger.extra["task_name"] == "execute_dbt_node"

        # Verify flow context
        if flow_run:
            assert logger.extra["flow_run_id"] == flow_run["id"]
            assert logger.extra["flow_run_name"] == flow_run["name"]
        else:
            assert logger.extra["flow_run_id"] == "<unknown>"
            assert logger.extra["flow_run_name"] == "<unknown>"

        if flow:
            assert logger.extra["flow_name"] == flow.name
        else:
            assert logger.extra["flow_name"] == "<unknown>"

    def test_get_task_logger_with_additional_kwargs(
        self, sample_node_id, sample_task_run_id
    ):
        """Test that get_task_logger includes additional kwargs in extra data."""
        tracker = NodeTaskTracker()
        tracker.set_task_run_id(sample_node_id, sample_task_run_id)

        logger = tracker.get_task_logger(
            sample_node_id,
            custom_key="custom_value",
            another_key=123,
        )

        assert logger.extra["custom_key"] == "custom_value"
        assert logger.extra["another_key"] == 123

    def test_get_task_logger_without_task_run_id(self, sample_node_id):
        """Test that get_task_logger works without task run ID."""
        tracker = NodeTaskTracker()

        logger = tracker.get_task_logger(sample_node_id)

        assert logger.extra["task_run_id"] is None
        assert logger.extra["task_run_name"] is None


class TestNodeTaskTrackerThreadExecution:
    """Test thread execution functionality."""

    @pytest.fixture
    def mock_thread_execution_setup(self, monkeypatch):
        """Set up common mocking for thread execution tests."""
        # Mock run_task_sync
        mock_run_task = Mock(return_value=Mock(spec=State))
        monkeypatch.setattr("prefect_dbt.core._tracker.run_task_sync", mock_run_task)

        # Mock hydrated_context
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock()
        mock_context_manager.__exit__ = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core._tracker.hydrated_context",
            Mock(return_value=mock_context_manager),
        )

        return mock_run_task

    @pytest.mark.parametrize(
        "return_value,expected_result",
        [
            (Mock(spec=State), Mock(spec=State)),
            (None, None),
        ],
    )
    def test_run_task_in_thread_stores_result(
        self,
        sample_node_id,
        mock_task,
        sample_task_run_id,
        mock_thread_execution_setup,
        return_value,
        expected_result,
    ):
        """Test that run_task_in_thread stores the correct result."""
        tracker = NodeTaskTracker()
        parameters = {"param": "value"}
        context = {"context": "data"}

        # Configure mock to return specified value
        mock_thread_execution_setup.return_value = return_value

        tracker.run_task_in_thread(
            sample_node_id, mock_task, sample_task_run_id, parameters, context
        )

        # Wait for thread to complete
        time.sleep(0.2)

        # Verify result was stored
        result = tracker.get_task_result(sample_node_id)
        if return_value is not None:
            # For mock objects, just verify it's a mock with the same spec
            assert isinstance(result, Mock)
            assert result._spec_class == return_value._spec_class
        else:
            assert result == expected_result

    @pytest.mark.parametrize(
        "dependencies_setup,expected_wait_count",
        [
            ({"dep1": Mock(spec=State), "dep2": Mock(spec=State)}, 2),
            ({"dep1": Mock(spec=State)}, 1),
            ({}, 0),
        ],
    )
    def test_run_task_in_thread_with_dependencies(
        self,
        sample_node_id,
        mock_task,
        sample_task_run_id,
        mock_state,
        mock_thread_execution_setup,
        dependencies_setup,
        expected_wait_count,
    ):
        """Test that run_task_in_thread handles dependencies correctly."""
        tracker = NodeTaskTracker()
        parameters = {"param": "value"}
        context = {"context": "data"}

        # Set up dependencies
        dependencies = list(dependencies_setup.keys())
        tracker.set_node_dependencies(sample_node_id, dependencies)

        # Set up dependency results
        for dep_id, result in dependencies_setup.items():
            tracker.set_task_result(dep_id, result)

        # Configure mock
        mock_thread_execution_setup.return_value = mock_state

        tracker.run_task_in_thread(
            sample_node_id, mock_task, sample_task_run_id, parameters, context
        )

        # Wait for thread to complete
        time.sleep(0.2)

        # Verify run_task_sync was called with correct dependencies
        mock_thread_execution_setup.assert_called_once()
        call_args = mock_thread_execution_setup.call_args
        assert len(call_args[1]["wait_for"]) == expected_wait_count

    def test_run_task_in_thread_starts_daemon_thread(
        self, sample_node_id, mock_task, sample_task_run_id, mock_thread_execution_setup
    ):
        """Test that run_task_in_thread starts a daemon thread."""
        tracker = NodeTaskTracker()
        parameters = {"param": "value"}
        context = {"context": "data"}

        tracker.run_task_in_thread(
            sample_node_id, mock_task, sample_task_run_id, parameters, context
        )

        # Wait for thread to start and potentially complete
        time.sleep(0.1)

        # Verify run_task_sync was called
        mock_thread_execution_setup.assert_called_once()


class TestNodeTaskTrackerIntegration:
    """Test integration scenarios and complex workflows."""

    def test_comprehensive_workflow_with_multiple_nodes(self):
        """Test a comprehensive workflow with multiple nodes and dependencies."""
        tracker = NodeTaskTracker()

        # Set up multiple nodes
        nodes = ["model_1", "model_2", "model_3"]
        mock_tasks = {node: Mock(spec=Task) for node in nodes}

        # Start all nodes
        for node in nodes:
            tracker.start_task(node, mock_tasks[node])

        # Set up dependencies: model_3 depends on model_1 and model_2
        tracker.set_node_dependencies("model_3", ["model_1", "model_2"])

        # Complete model_1 and model_2
        tracker.set_node_status("model_1", {"status": "success"}, "Model 1 complete")
        tracker.set_node_status("model_2", {"status": "success"}, "Model 2 complete")

        # Set task results for dependencies
        tracker.set_task_result("model_1", Mock(spec=State))
        tracker.set_task_result("model_2", Mock(spec=State))

        # Verify all nodes are in expected states
        assert tracker.is_node_complete("model_1") is True
        assert tracker.is_node_complete("model_2") is True
        assert tracker.is_node_complete("model_3") is False

        # Verify dependencies are correctly stored
        deps = tracker.get_node_dependencies("model_3")
        assert deps == ["model_1", "model_2"]

        # Verify loggers are available
        assert tracker.get_task_logger("model_1") is not None
        assert tracker.get_task_logger("model_2") is not None
        assert tracker.get_task_logger("model_3") is not None

    def test_concurrent_node_completion(self):
        """Test that multiple nodes can complete concurrently."""
        tracker = NodeTaskTracker()
        nodes = ["node_1", "node_2", "node_3"]

        # Start all nodes
        for node in nodes:
            tracker.start_task(node, Mock(spec=Task))

        # Complete nodes concurrently
        def complete_node(node_id: str, delay: float):
            time.sleep(delay)
            tracker.set_node_status(
                node_id, {"status": "success"}, f"{node_id} complete"
            )

        threads = []
        for i, node in enumerate(nodes):
            thread = threading.Thread(target=complete_node, args=(node, i * 0.05))
            thread.daemon = True
            threads.append(thread)
            thread.start()

        # Wait for all nodes to complete
        for node in nodes:
            assert tracker.wait_for_node_completion(node, timeout=1.0) is True
            assert tracker.is_node_complete(node) is True

        # Wait for all threads to finish
        for thread in threads:
            thread.join(timeout=1.0)

    def test_node_lifecycle_with_task_execution(
        self, sample_node_id, mock_task, sample_task_run_id, mock_state, monkeypatch
    ):
        """Test complete node lifecycle including task execution."""
        tracker = NodeTaskTracker()

        # Mock run_task_sync
        monkeypatch.setattr(
            "prefect_dbt.core._tracker.run_task_sync", Mock(return_value=mock_state)
        )

        # Mock hydrated_context
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock()
        mock_context_manager.__exit__ = Mock()
        monkeypatch.setattr(
            "prefect_dbt.core._tracker.hydrated_context",
            Mock(return_value=mock_context_manager),
        )

        # Start the node
        tracker.start_task(sample_node_id, mock_task)
        assert not tracker.is_node_complete(sample_node_id)

        # Set up task run ID and name
        tracker.set_task_run_id(sample_node_id, sample_task_run_id)
        tracker.set_task_run_name(sample_node_id, "test_task_run")

        # Run task in thread
        parameters = {"param": "value"}
        context = {"context": "data"}
        tracker.run_task_in_thread(
            sample_node_id, mock_task, sample_task_run_id, parameters, context
        )

        # Wait for task to complete
        time.sleep(0.2)

        # Verify task result was stored
        result = tracker.get_task_result(sample_node_id)
        assert result == mock_state

        # Complete the node
        tracker.set_node_status(sample_node_id, {"status": "success"}, "completed")
        assert tracker.is_node_complete(sample_node_id) is True

        # Verify logger has correct information
        logger = tracker.get_task_logger(sample_node_id)
        assert logger.extra["task_run_id"] == sample_task_run_id
        assert logger.extra["task_run_name"] == "test_task_run"
