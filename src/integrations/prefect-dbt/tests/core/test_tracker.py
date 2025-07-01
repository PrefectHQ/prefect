"""
Unit tests for NodeTaskTracker - focusing on outcomes.
"""

import threading
import time
from unittest.mock import Mock

import pytest
from prefect_dbt.core._tracker import NodeTaskTracker

from prefect._internal.uuid7 import uuid7


@pytest.fixture
def tracker():
    """Fixture providing a NodeTaskTracker instance."""
    return NodeTaskTracker()


@pytest.fixture
def mock_task():
    """Fixture providing a mock task."""
    return Mock()


@pytest.fixture
def mock_state():
    """Fixture providing a mock state."""
    return Mock()


@pytest.fixture
def mock_context_manager(monkeypatch):
    """Fixture providing a mock context manager for hydrated_context."""
    mock_context = Mock()
    mock_context.__enter__ = Mock()
    mock_context.__exit__ = Mock()
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.hydrated_context",
        Mock(return_value=mock_context),
    )
    return mock_context


@pytest.fixture
def mock_run_task_sync(monkeypatch, mock_state):
    """Fixture providing a mock run_task_sync function."""
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.run_task_sync", Mock(return_value=mock_state)
    )
    return mock_state


@pytest.fixture
def sample_node_id():
    """Fixture providing a sample node ID."""
    return "test_node"


@pytest.fixture
def sample_task_run_id():
    """Fixture providing a sample task run ID."""
    return uuid7()


@pytest.fixture
def sample_parameters():
    """Fixture providing sample parameters."""
    return {"param": "value"}


@pytest.fixture
def sample_context():
    """Fixture providing sample context."""
    return {"context": "data"}


def test_tracker_manages_node_lifecycle(tracker, sample_node_id, mock_task):
    """Test that tracker properly manages the complete lifecycle of a node."""
    # Start the node
    tracker.start_task(sample_node_id, mock_task)
    assert not tracker.is_node_complete(sample_node_id)

    # Set node status (completes the node)
    event_data = {"status": "success", "node_info": {"node_status": "success"}}
    tracker.set_node_status(sample_node_id, event_data, "Node completed successfully")

    # Verify node is complete
    assert tracker.is_node_complete(sample_node_id)
    status = tracker.get_node_status(sample_node_id)
    assert status is not None
    assert status["event_data"] == event_data
    assert status["event_message"] == "Node completed successfully"


def test_tracker_handles_multiple_nodes_independently(tracker, mock_task):
    """Test that tracker can manage multiple nodes without interference."""
    # Set up two nodes
    tracker.start_task("node1", mock_task)
    tracker.start_task("node2", mock_task)

    # Complete one node
    tracker.set_node_status("node1", {"status": "success"}, "Node 1 done")

    # Verify states are independent
    assert tracker.is_node_complete("node1") is True
    assert tracker.is_node_complete("node2") is False

    # Complete second node
    tracker.set_node_status("node2", {"status": "running"}, "Node 2 running")
    assert tracker.is_node_complete("node2") is True


def test_tracker_provides_thread_safe_completion_waiting():
    """Test that tracker provides thread-safe waiting for node completion."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    tracker.start_task(node_id, Mock())

    # Start a thread that will complete the node after a delay
    def complete_node():
        time.sleep(0.05)
        tracker.set_node_status(node_id, {"status": "success"}, "completed")

    thread = threading.Thread(target=complete_node)
    thread.daemon = True
    thread.start()

    # Wait for completion from main thread
    result = tracker.wait_for_node_completion(node_id, timeout=1.0)
    assert result is True
    assert tracker.is_node_complete(node_id) is True


def test_tracker_handles_timeout_gracefully():
    """Test that tracker handles timeout scenarios gracefully."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    tracker.start_task(node_id, Mock())

    # Try to wait for completion with short timeout
    result = tracker.wait_for_node_completion(node_id, timeout=0.1)
    assert result is False
    assert not tracker.is_node_complete(node_id)


def test_tracker_manages_task_results():
    """Test that tracker properly manages task results."""
    tracker = NodeTaskTracker()
    node_id = "test_node"

    # Set and retrieve task result
    mock_result = Mock()
    tracker.set_task_result(node_id, mock_result)
    retrieved_result = tracker.get_task_result(node_id)
    assert retrieved_result == mock_result

    # Test with None result
    tracker.set_task_result(node_id, None)
    assert tracker.get_task_result(node_id) is None


def test_tracker_manages_dependencies():
    """Test that tracker properly manages node dependencies."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    dependencies = ["dep1", "dep2", "dep3"]

    # Set dependencies
    tracker.set_node_dependencies(node_id, dependencies)
    retrieved_deps = tracker.get_node_dependencies(node_id)
    assert retrieved_deps == dependencies

    # Test default empty list for unknown node
    assert tracker.get_node_dependencies("unknown_node") == []


def test_tracker_thread_execution_outcomes(
    tracker,
    sample_node_id,
    mock_task,
    sample_task_run_id,
    sample_parameters,
    sample_context,
    mock_run_task_sync,
    mock_context_manager,
):
    """Test that tracker properly handles thread execution outcomes."""
    # Mock successful execution is already set up by mock_run_task_sync fixture

    tracker.run_task_in_thread(
        sample_node_id, mock_task, sample_task_run_id, sample_parameters, sample_context
    )

    # Wait for thread completion
    time.sleep(0.2)

    # Verify result was stored
    result = tracker.get_task_result(sample_node_id)
    assert result == mock_run_task_sync


def test_tracker_handles_execution_with_dependencies(monkeypatch: pytest.MonkeyPatch):
    """Test that tracker handles execution with dependencies correctly."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_task = Mock()
    task_run_id = uuid7()

    # Set up dependencies with results
    tracker.set_node_dependencies(node_id, ["dep1", "dep2"])
    mock_dep_state1 = Mock()
    mock_dep_state2 = Mock()
    tracker.set_task_result("dep1", mock_dep_state1)
    tracker.set_task_result("dep2", mock_dep_state2)

    parameters = {"param": "value"}
    context = {"context": "data"}

    # Mock execution that should receive dependencies
    mock_state = Mock()

    monkeypatch.setattr(
        "prefect_dbt.core._tracker.run_task_sync", Mock(return_value=mock_state)
    )

    # Set up context manager mock
    mock_context = Mock()
    mock_context.__enter__ = Mock()
    mock_context.__exit__ = Mock()
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.hydrated_context",
        Mock(return_value=mock_context),
    )

    tracker.run_task_in_thread(node_id, mock_task, task_run_id, parameters, context)

    # Wait for thread completion
    time.sleep(0.2)

    # Verify result was stored
    result = tracker.get_task_result(node_id)
    assert result == mock_state


def test_tracker_handles_execution_failures(monkeypatch: pytest.MonkeyPatch):
    """Test that tracker properly handles execution failures."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_task = Mock()
    task_run_id = uuid7()
    parameters = {"param": "value"}
    context = {"context": "data"}

    # Mock execution that raises an exception
    test_exception = Exception("Task execution failed")

    monkeypatch.setattr(
        "prefect_dbt.core._tracker.run_task_sync", Mock(side_effect=test_exception)
    )

    # Set up context manager mock
    mock_context = Mock()
    mock_context.__enter__ = Mock()
    mock_context.__exit__ = Mock()
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.hydrated_context",
        Mock(return_value=mock_context),
    )

    # The exception should cause the thread to fail, but we can't easily test that
    # since the exception would be raised in the thread context
    # Instead, we test that the function can be called without error
    tracker.run_task_in_thread(node_id, mock_task, task_run_id, parameters, context)

    # Wait for thread completion
    time.sleep(0.2)

    # The result should be None since the exception would prevent state from being set
    result = tracker.get_task_result(node_id)
    # Note: In the actual implementation, exceptions in threads are not caught
    # and would cause the thread to fail silently
    assert result is None


def test_tracker_handles_no_state_returned(monkeypatch: pytest.MonkeyPatch):
    """Test that tracker handles cases where no state is returned."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_task = Mock()
    task_run_id = uuid7()
    parameters = {"param": "value"}
    context = {"context": "data"}

    # Mock execution that returns None

    monkeypatch.setattr(
        "prefect_dbt.core._tracker.run_task_sync", Mock(return_value=None)
    )

    # Set up context manager mock
    mock_context = Mock()
    mock_context.__enter__ = Mock()
    mock_context.__exit__ = Mock()
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.hydrated_context",
        Mock(return_value=mock_context),
    )

    tracker.run_task_in_thread(node_id, mock_task, task_run_id, parameters, context)

    # Wait for thread completion
    time.sleep(0.2)

    # Verify None was stored as result
    result = tracker.get_task_result(node_id)
    assert result is None


def test_get_task_logger_creates_logger_with_task_id():
    """Test that get_task_logger creates a logger with the correct task ID."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    task_run_id = uuid7()

    # Set up task run ID
    tracker.set_task_run_id(node_id, task_run_id)
    tracker.set_task_run_name(node_id, "test_task_run")

    # Create logger
    logger = tracker.get_task_logger(node_id)

    # Verify logger has correct task run ID
    assert logger.extra["task_run_id"] == task_run_id
    assert logger.extra["task_run_name"] == "test_task_run"
    assert logger.extra["task_name"] == "execute_dbt_node"


def test_get_task_logger_with_flow_context():
    """Test that get_task_logger includes flow context when provided."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    task_run_id = uuid7()

    tracker.set_task_run_id(node_id, task_run_id)
    tracker.set_task_run_name(node_id, "test_task_run")

    flow_run = {"id": "flow-run-123", "name": "test_flow_run"}
    flow = Mock()
    flow.name = "test_flow"

    logger = tracker.get_task_logger(node_id, flow_run=flow_run, flow=flow)

    assert logger.extra["flow_run_id"] == "flow-run-123"
    assert logger.extra["flow_run_name"] == "test_flow_run"
    assert logger.extra["flow_name"] == "test_flow"


def test_task_id_tracking():
    """Test that task run IDs and names are properly tracked."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    task_run_id = uuid7()
    task_run_name = "my_task_run"

    # Initially no task run ID should be set
    assert tracker.get_task_run_id(node_id) is None
    assert tracker.get_task_run_name(node_id) is None

    # Set task run ID and name
    tracker.set_task_run_id(node_id, task_run_id)
    tracker.set_task_run_name(node_id, task_run_name)

    # Verify they are stored correctly
    assert tracker.get_task_run_id(node_id) == task_run_id
    assert tracker.get_task_run_name(node_id) == task_run_name


def test_task_run_name_tracking():
    """Test that task run names are properly tracked and updated."""
    tracker = NodeTaskTracker()
    node_id = "test_node"

    # Initially no task run name should be set
    assert tracker.get_task_run_name(node_id) is None

    # Set initial task run name
    initial_name = "initial_task_run"
    tracker.set_task_run_name(node_id, initial_name)
    assert tracker.get_task_run_name(node_id) == initial_name

    # Update task run name
    updated_name = "updated_task_run"
    tracker.set_task_run_name(node_id, updated_name)
    assert tracker.get_task_run_name(node_id) == updated_name

    # Test with different node
    other_node = "other_node"
    other_name = "other_task_run"
    tracker.set_task_run_name(other_node, other_name)
    assert tracker.get_task_run_name(other_node) == other_name
    assert tracker.get_task_run_name(node_id) == updated_name  # Original unchanged


def test_tracker_comprehensive_workflow() -> None:
    """Test a comprehensive workflow using the tracker."""
    tracker = NodeTaskTracker()

    # Set up a complex scenario with multiple nodes and dependencies
    nodes = ["model_1", "model_2", "model_3"]
    mock_tasks = {node: Mock() for node in nodes}

    # Start all nodes
    for node in nodes:
        tracker.start_task(node, mock_tasks[node])

    # Set up dependencies: model_3 depends on model_1 and model_2
    tracker.set_node_dependencies("model_3", ["model_1", "model_2"])

    # Complete model_1 and model_2
    tracker.set_node_status("model_1", {"status": "success"}, "Model 1 complete")
    tracker.set_node_status("model_2", {"status": "success"}, "Model 2 complete")

    # Set task results for dependencies
    tracker.set_task_result("model_1", Mock())
    tracker.set_task_result("model_2", Mock())

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
