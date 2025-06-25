"""
Unit tests for NodeTaskTracker - focusing on outcomes.
"""

import threading
import time
from unittest.mock import Mock

import pytest
from prefect_dbt.core._tracker import NodeTaskTracker


def test_tracker_manages_node_lifecycle():
    """Test that tracker properly manages the complete lifecycle of a node."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_task = Mock()

    # Start the node
    tracker.start_task(node_id, mock_task)
    assert not tracker.is_node_complete(node_id)

    # Set node status (completes the node)
    event_data = {"status": "success", "node_info": {"node_status": "success"}}
    tracker.set_node_status(node_id, event_data, "Node completed successfully")

    # Verify node is complete
    assert tracker.is_node_complete(node_id)
    status = tracker.get_node_status(node_id)
    assert status["event_data"] == event_data
    assert status["event_message"] == "Node completed successfully"


def test_tracker_handles_multiple_nodes_independently():
    """Test that tracker can manage multiple nodes without interference."""
    tracker = NodeTaskTracker()

    # Set up two nodes
    tracker.start_task("node1", Mock())
    tracker.start_task("node2", Mock())

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


def test_tracker_manages_loggers():
    """Test that tracker properly manages task loggers."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_logger = Mock()

    # Set and retrieve logger
    tracker.set_task_logger(node_id, mock_logger)
    retrieved_logger = tracker.get_task_logger(node_id)
    assert retrieved_logger == mock_logger

    # Test None for unknown node
    assert tracker.get_task_logger("unknown_node") is None


def test_tracker_thread_execution_outcomes(monkeypatch: pytest.MonkeyPatch):
    """Test that tracker properly handles thread execution outcomes."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_task = Mock()
    parameters = {"param": "value"}
    context = {"context": "data"}

    # Mock successful execution
    mock_state = Mock()

    monkeypatch.setattr(
        "prefect_dbt.core._tracker.run_task_sync", Mock(return_value=mock_state)
    )
    monkeypatch.setattr("prefect_dbt.core._tracker.hydrated_context", Mock())

    # Set up context manager mock
    mock_context = Mock()
    mock_context.__enter__ = Mock()
    mock_context.__exit__ = Mock()
    monkeypatch.setattr(
        "prefect_dbt.core._tracker.hydrated_context",
        Mock(return_value=mock_context),
    )

    tracker.run_task_in_thread(node_id, mock_task, parameters, context)

    # Wait for thread completion
    time.sleep(0.2)

    # Verify result was stored
    result = tracker.get_task_result(node_id)
    assert result == mock_state


def test_tracker_handles_execution_with_dependencies(monkeypatch: pytest.MonkeyPatch):
    """Test that tracker handles execution with dependencies correctly."""
    tracker = NodeTaskTracker()
    node_id = "test_node"
    mock_task = Mock()

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

    tracker.run_task_in_thread(node_id, mock_task, parameters, context)

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
    tracker.run_task_in_thread(node_id, mock_task, parameters, context)

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

    tracker.run_task_in_thread(node_id, mock_task, parameters, context)

    # Wait for thread completion
    time.sleep(0.2)

    # Verify None was stored as result
    result = tracker.get_task_result(node_id)
    assert result is None


def test_tracker_comprehensive_workflow() -> None:
    """Test a comprehensive workflow using the tracker."""
    tracker = NodeTaskTracker()

    # Set up a complex scenario with multiple nodes and dependencies
    nodes = ["model_1", "model_2", "model_3"]
    mock_tasks = {node: Mock() for node in nodes}

    # Start all nodes
    for node in nodes:
        tracker.start_task(node, mock_tasks[node])
        tracker.set_task_logger(node, Mock())

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
