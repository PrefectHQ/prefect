"""
State for managing tasks across callbacks.
"""

import threading
from typing import Any, Optional, Union
from uuid import UUID

from prefect.client.schemas.objects import Flow, State
from prefect.context import hydrated_context
from prefect.logging.loggers import PrefectLogAdapter, get_logger
from prefect.task_engine import run_task_sync
from prefect.tasks import Task


class NodeTaskTracker:
    """
    Maintains the state, upstream dependencies, logger, and results
    for all the tasks called by the execution of each node in the dbt project.
    """

    def __init__(self):
        self._tasks: dict[str, Task[Any, Any]] = {}
        self._task_results: dict[str, Any] = {}
        self._node_status: dict[str, dict[str, Any]] = {}
        self._node_complete: dict[str, bool] = {}
        self._node_dependencies: dict[str, list[str]] = {}
        self._node_events: dict[str, threading.Event] = {}
        self._task_run_ids: dict[str, UUID] = {}
        self._task_run_names: dict[str, str] = {}

    def start_task(self, node_id: str, task: Task[Any, Any]) -> None:
        """Start a task for a node."""
        self._tasks[node_id] = task
        self._node_complete[node_id] = False
        self._node_events[node_id] = threading.Event()

    def get_task_logger(
        self,
        node_id: str,
        flow_run: Optional[dict[str, Any]] = None,
        flow: Optional[Flow] = None,
        **kwargs: Any,
    ) -> PrefectLogAdapter:
        """Get the logger for a task."""
        logger = PrefectLogAdapter(
            get_logger("prefect.task_runs"),
            extra={
                **{
                    "task_run_id": self.get_task_run_id(node_id),
                    "flow_run_id": str(flow_run.get("id")) if flow_run else "<unknown>",
                    "task_run_name": self.get_task_run_name(node_id),
                    "task_name": "execute_dbt_node",
                    "flow_run_name": flow_run.get("name") if flow_run else "<unknown>",
                    "flow_name": flow.name if flow else "<unknown>",
                },
                **kwargs,
            },
        )

        return logger

    def set_node_status(
        self, node_id: str, event_data: dict[str, Any], event_message: str
    ) -> None:
        """Set the status for a node."""
        self._node_status[node_id] = {
            "event_data": event_data,
            "event_message": event_message,
        }
        # Mark node as complete when status is set
        self._node_complete[node_id] = True
        # Signal the event to wake up any waiting threads
        if node_id in self._node_events:
            self._node_events[node_id].set()

    def get_node_status(self, node_id: str) -> Union[dict[str, Any], None]:
        """Get the status for a node."""
        return self._node_status.get(node_id)

    def is_node_complete(self, node_id: str) -> bool:
        """Check if a node is complete."""
        return self._node_complete.get(node_id, False)

    def wait_for_node_completion(
        self, node_id: str, timeout: Union[float, None] = None
    ) -> bool:
        """Wait for a node to complete using threading.Event.

        Args:
            node_id: The ID of the node to wait for
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if the node completed, False if timeout occurred
        """
        if node_id not in self._node_events:
            # If no event exists, the node might already be complete
            return self.is_node_complete(node_id)

        return self._node_events[node_id].wait(timeout=timeout)

    def set_task_result(self, node_id: str, result: Any) -> None:
        """Set the result for a task."""
        self._task_results[node_id] = result

    def get_task_result(self, node_id: str) -> Union[Any, None]:
        """Get the result for a task."""
        return self._task_results.get(node_id)

    def set_node_dependencies(self, node_id: str, dependencies: list[str]) -> None:
        """Set the dependencies for a node."""
        self._node_dependencies[node_id] = dependencies

    def get_node_dependencies(self, node_id: str) -> list[str]:
        """Get the dependencies for a node."""
        return self._node_dependencies.get(node_id, [])

    def set_task_run_id(self, node_id: str, task_run_id: UUID) -> None:
        """Set the task run ID for a node."""
        self._task_run_ids[node_id] = task_run_id

    def get_task_run_id(self, node_id: str) -> Union[UUID, None]:
        """Get the task run ID for a node."""
        return self._task_run_ids.get(node_id)

    def set_task_run_name(self, node_id: str, task_run_name: str) -> None:
        """Set the task run name for a node."""
        self._task_run_names[node_id] = task_run_name

    def get_task_run_name(self, node_id: str) -> Union[str, None]:
        """Get the task run name for a node."""
        return self._task_run_names.get(node_id)

    def run_task_in_thread(
        self,
        node_id: str,
        task: Task[Any, Any],
        task_run_id: UUID,
        parameters: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Run a task in a separate thread."""

        def run_task():
            with hydrated_context(context):
                states: list[State] = []
                dependencies = self.get_node_dependencies(node_id)
                for dep_id in dependencies:
                    state = self.get_task_result(dep_id)
                    if state:
                        states.append(state)

                state = run_task_sync(
                    task,
                    task_run_id=task_run_id,
                    parameters=parameters,
                    wait_for=states,
                    context=context,
                    return_type="state",
                )

                # Wait for the task to complete
                if state:
                    self.set_task_result(node_id, state)
                else:
                    self.set_task_result(node_id, None)

        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()
