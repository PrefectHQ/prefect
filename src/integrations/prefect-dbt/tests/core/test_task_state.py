"""
Unit tests for TaskState class.
"""

import threading
import time
from unittest.mock import Mock, patch

from prefect_dbt.core.task_state import TaskState


class TestTaskState:
    """Test cases for TaskState class."""

    def test_init(self):
        """Test TaskState initialization."""
        task_state = TaskState()

        # Test that all internal collections are empty
        assert task_state.get_task_logger("any_node") is None
        assert task_state.get_node_status("any_node") is None
        assert task_state.get_task_result("any_node") is None
        assert task_state.get_node_dependencies("any_node") == []
        assert task_state.is_node_complete("any_node") is False

    def test_start_task(self):
        """Test starting a task."""
        task_state = TaskState()
        mock_task = Mock()
        node_id = "test_node"

        task_state.start_task(node_id, mock_task)

        # Test that node is not complete initially
        assert task_state.is_node_complete(node_id) is False

        # Test that we can wait for completion (should timeout since not complete)
        result = task_state.wait_for_node_completion(node_id, timeout=0.1)
        assert result is False

    def test_set_and_get_task_logger(self):
        """Test setting and getting task logger."""
        task_state = TaskState()
        mock_logger = Mock()
        node_id = "test_node"

        # Test setting logger
        task_state.set_task_logger(node_id, mock_logger)

        # Test getting logger
        retrieved_logger = task_state.get_task_logger(node_id)
        assert retrieved_logger == mock_logger

        # Test getting non-existent logger
        non_existent_logger = task_state.get_task_logger("non_existent")
        assert non_existent_logger is None

    def test_set_and_get_node_status(self):
        """Test setting and getting node status."""
        task_state = TaskState()
        node_id = "test_node"
        event_data = {"status": "running"}
        event_message = "Task is running"

        # Test setting status
        task_state.set_node_status(node_id, event_data, event_message)

        expected_status = {
            "event_data": event_data,
            "event_message": event_message,
        }

        # Test getting status
        retrieved_status = task_state.get_node_status(node_id)
        assert retrieved_status == expected_status

        # Test that node is marked as complete
        assert task_state.is_node_complete(node_id) is True

        # Test getting non-existent status
        non_existent_status = task_state.get_node_status("non_existent")
        assert non_existent_status is None

    def test_is_node_complete(self):
        """Test checking if node is complete."""
        task_state = TaskState()
        node_id = "test_node"

        # Test incomplete node
        assert task_state.is_node_complete(node_id) is False

        # Test complete node
        task_state.set_node_status(node_id, {}, "completed")
        assert task_state.is_node_complete(node_id) is True

    def test_wait_for_node_completion(self):
        """Test waiting for node completion."""
        task_state = TaskState()
        node_id = "test_node"

        # Test waiting for non-existent node (should return completion status)
        result = task_state.wait_for_node_completion(node_id, timeout=0.1)
        assert result is False  # Node doesn't exist, so not complete

        # Test waiting for already complete node
        task_state.set_node_status(node_id, {}, "completed")
        result = task_state.wait_for_node_completion(node_id, timeout=0.1)
        assert result is True

        # Test waiting for node that completes during wait
        task_state = TaskState()
        node_id = "test_node"
        task_state.start_task(node_id, Mock())

        def complete_node():
            time.sleep(0.05)
            task_state.set_node_status(node_id, {}, "completed")

        thread = threading.Thread(target=complete_node)
        thread.daemon = True
        thread.start()

        result = task_state.wait_for_node_completion(node_id, timeout=1.0)
        assert result is True

    def test_wait_for_node_completion_timeout(self):
        """Test waiting for node completion with timeout."""
        task_state = TaskState()
        node_id = "test_node"
        task_state.start_task(node_id, Mock())

        # Test timeout
        result = task_state.wait_for_node_completion(node_id, timeout=0.1)
        assert result is False

    def test_set_and_get_task_result(self):
        """Test setting and getting task result."""
        task_state = TaskState()
        node_id = "test_node"
        mock_result = Mock()

        # Test setting result
        task_state.set_task_result(node_id, mock_result)

        # Test getting result
        retrieved_result = task_state.get_task_result(node_id)
        assert retrieved_result == mock_result

        # Test getting non-existent result
        non_existent_result = task_state.get_task_result("non_existent")
        assert non_existent_result is None

    def test_set_and_get_node_dependencies(self):
        """Test setting and getting node dependencies."""
        task_state = TaskState()
        node_id = "test_node"
        dependencies = ["dep1", "dep2", "dep3"]

        # Test setting dependencies
        task_state.set_node_dependencies(node_id, dependencies)

        # Test getting dependencies
        retrieved_dependencies = task_state.get_node_dependencies(node_id)
        assert retrieved_dependencies == dependencies

        # Test getting non-existent dependencies
        non_existent_dependencies = task_state.get_node_dependencies("non_existent")
        assert non_existent_dependencies == []

    @patch("prefect_dbt.core.task_state.run_task_sync")
    @patch("prefect_dbt.core.task_state.hydrated_context")
    def test_run_task_in_thread_success(
        self, mock_hydrated_context: Mock, mock_run_task_sync: Mock
    ) -> None:
        """Test running task in thread successfully."""
        task_state = TaskState()
        node_id = "test_node"
        mock_task = Mock()
        parameters = {"param1": "value1"}
        context = {"context1": "value1"}
        mock_state = Mock()

        mock_run_task_sync.return_value = mock_state
        mock_hydrated_context.return_value.__enter__ = Mock()
        mock_hydrated_context.return_value.__exit__ = Mock()

        task_state.run_task_in_thread(node_id, mock_task, parameters, context)

        # Wait for thread to complete
        time.sleep(0.1)

        # Verify task result was set
        result = task_state.get_task_result(node_id)
        assert result == mock_state

        # Verify run_task_sync was called correctly
        mock_run_task_sync.assert_called_once_with(
            mock_task,
            parameters=parameters,
            wait_for=[],
            context=context,
            return_type="state",
        )

    @patch("prefect_dbt.core.task_state.run_task_sync")
    @patch("prefect_dbt.core.task_state.hydrated_context")
    def test_run_task_in_thread_with_dependencies(
        self, mock_hydrated_context: Mock, mock_run_task_sync: Mock
    ) -> None:
        """Test running task in thread with dependencies."""
        task_state = TaskState()
        node_id = "test_node"
        mock_task = Mock()
        parameters = {"param1": "value1"}
        context = {"context1": "value1"}
        mock_state = Mock()
        mock_dep_state = Mock()

        # Set up dependencies
        task_state.set_node_dependencies(node_id, ["dep1", "dep2"])
        task_state.set_task_result("dep1", mock_dep_state)
        task_state.set_task_result("dep2", mock_dep_state)

        mock_run_task_sync.return_value = mock_state
        mock_hydrated_context.return_value.__enter__ = Mock()
        mock_hydrated_context.return_value.__exit__ = Mock()

        task_state.run_task_in_thread(node_id, mock_task, parameters, context)

        # Wait for thread to complete
        time.sleep(0.1)

        # Verify run_task_sync was called with dependencies
        mock_run_task_sync.assert_called_once_with(
            mock_task,
            parameters=parameters,
            wait_for=[mock_dep_state, mock_dep_state],
            context=context,
            return_type="state",
        )

    @patch("prefect_dbt.core.task_state.run_task_sync")
    @patch("prefect_dbt.core.task_state.hydrated_context")
    def test_run_task_in_thread_no_state_returned(
        self, mock_hydrated_context: Mock, mock_run_task_sync: Mock
    ) -> None:
        """Test running task in thread when no state is returned."""
        task_state = TaskState()
        node_id = "test_node"
        mock_task = Mock()
        parameters = {"param1": "value1"}
        context = {"context1": "value1"}

        mock_run_task_sync.return_value = None
        mock_hydrated_context.return_value.__enter__ = Mock()
        mock_hydrated_context.return_value.__exit__ = Mock()

        task_state.run_task_in_thread(node_id, mock_task, parameters, context)

        # Wait for thread to complete
        time.sleep(0.1)

        # Verify None was stored as result
        result = task_state.get_task_result(node_id)
        assert result is None

    def test_multiple_nodes(self) -> None:
        """Test managing multiple nodes simultaneously."""
        task_state = TaskState()

        # Set up multiple nodes
        task_state.start_task("node1", Mock())
        task_state.start_task("node2", Mock())

        task_state.set_task_logger("node1", Mock())
        task_state.set_task_logger("node2", Mock())

        task_state.set_node_status("node1", {"status": "complete"}, "Node 1 complete")
        task_state.set_node_status("node2", {"status": "running"}, "Node 2 running")

        # Verify all nodes are managed correctly
        assert task_state.is_node_complete("node1") is True
        assert task_state.is_node_complete("node2") is True
        assert task_state.get_task_logger("node1") is not None
        assert task_state.get_task_logger("node2") is not None
        assert task_state.get_node_status("node1") is not None
        assert task_state.get_node_status("node2") is not None
