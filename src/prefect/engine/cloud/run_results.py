from typing import Iterable, Any
from prefect.engine.state import State
from prefect.core.task import Task
from prefect.utilities.graphql import with_args
from prefect.client.client import Client
from prefect.utilities.logging import get_logger


logger = get_logger("run_results")


class FlowRunResult:
    def __init__(
        self,
        flow_run_id: str = None,
        flow_id: str = None,
        task_run_results: Iterable["TaskRunResult"] = None,
        state: State = None,
    ):
        self.flow_run_id = flow_run_id
        self.flow_id = flow_id
        self.state = state

        if task_run_results is not None:
            self.task_results = {
                result.task_run_id: result for result in task_run_results
            }

    @classmethod
    def from_flow_run_id(
        cls, flow_run_id: str, load_static_tasks: bool = True
    ) -> "FlowRunResult":
        """
        Get an instance of this class filled with information by querying for the given
        flow run id

        Args:
            flow_run_id:
            load_static_tasks: Pre-populate the task run results with results from tasks
                that are unmapped.

        Returns:

        """
        client = Client()

        flow_run_query = {
            "query": {
                with_args("flow_run_by_pk", {"id": flow_run_id}): {
                    "id": True,
                    "name": True,
                    "flow_id": True,
                    "serialized_state": True,
                }
            }
        }

        result = client.graphql(flow_run_query)
        flow_run = result.get("data", {}).get("flow_run_by_pk", None)

        if not flow_run:
            raise ValueError(
                f"Received bad result while querying for flow run {flow_run_id}: "
                f"{result}"
            )

        if load_static_tasks:
            task_query = {
                "query": {
                    with_args(
                        "task_run",
                        {
                            "where": {
                                "map_index": {"_eq": -1},
                                "flow_run_id": {"_eq": flow_run_id},
                            }
                        },
                    ): {
                        "id": True,
                        "name": True,
                        "task": {"id": True, "slug": True},
                        "serialized_state": True,
                    }
                }
            }
            result = client.graphql(task_query)
            task_runs = result.get("data", {}).get("task_run", None)

            if task_runs is None:
                logger.warning(
                    f"Failed to load static task runs for flow run {flow_run_id}: "
                    f"{result}"
                )
        else:
            task_runs = []

        task_results = [
            TaskRunResult(
                task_run_id=task_run["id"],
                name=task_run["name"],
                task_id=task_run["task"]["id"],
                slug=task_run["task"]["slug"],
                state=State.deserialize(task_run["serialized_state"]),
            )
            for task_run in task_runs
        ]

        return cls(
            flow_run_id=flow_run["id"],
            flow_id=flow_run["flow_id"],
            state=State.deserialize(flow_run["serialized_state"]),
            task_run_results=task_results,
        )

    def get(
        self, task: Task = None, task_name: str = None, task_run_id: str = None
    ) -> "TaskRunResult":
        """
        Get information about a task run from this flow run. Lookup is available by one
        of the following arguments. If the task information is not available locally
        already, we will query the database for it.

        Args:
            task:
            task_name:
            task_run_id:

        Returns:
            TaskRunResult
        """
        if task_run_id in self.task_results:
            return self.task_results[task_run_id]

        if task_run_id is not None:
            result = TaskRunResult.from_task_run_id(task_run_id)
            self.task_results[result] = result
            return result

        # Other methods not supported yet...


class TaskRunResult:
    def __init__(
        self,
        task_run_id: str,
        task_id: str,
        slug: str,
        name: str,
        state: State,
        result: Any = None,
    ):
        self.task_run_id = task_run_id
        self.name = name
        self.task_id = task_id
        self.slug = slug
        self.state = state

        if result is None and state is not None:
            result = state.result

        self.result = result

    @classmethod
    def from_task_run_id(cls, task_run_id: str = None) -> "TaskRunResult":
        # Query GQL for information about this task
        return TaskRunResult(task_run_id=task_run_id)
