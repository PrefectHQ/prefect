from typing import Iterable, Any
from prefect.engine.state import State
from prefect.core.task import Task
from prefect.utilities.graphql import with_args
from prefect.client.client import Client
from prefect.utilities.logging import get_logger

from typing import List, Union


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

        # Cached value of all task run ids for this flow run
        self._task_run_ids: Optional[List[str]] = None

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
            task_runs = TaskRunResult.query_for_task_runs(
                where={
                    "map_index": {"_eq": -1},
                    "flow_run_id": {"_eq": flow_run_id},
                },
                many=True,
            )
            task_results = [
                TaskRunResult.from_task_run_data(task_run) for task_run in task_runs
            ]

        else:
            task_results = None

        return cls(
            flow_run_id=flow_run["id"],
            flow_id=flow_run["flow_id"],
            state=State.deserialize(flow_run["serialized_state"]),
            task_run_results=task_results,
        )

    def get(
        self, task: Task = None, task_slug: str = None, task_run_id: str = None
    ) -> "TaskRunResult":
        """
        Get information about a task run from this flow run. Lookup is available by one
        of the following arguments. If the task information is not available locally
        already, we will query the database for it.

        Args:
            task:
            task_slug:
            task_run_id:

        Returns:
            TaskRunResult
        """
        if task_run_id in self.task_results:
            return self.task_results[task_run_id]

        if task is not None:
            if task_slug is not None and task_slug != task.slug:
                raise ValueError(
                    "Both `task` and `task_slug` were provided but "
                    f"`task.slug == {task.slug!r}` and `task_slug == {task_slug!r}`"
                )
            task_slug = task.slug

        if task_run_id is not None:
            result = TaskRunResult.from_task_run_id(task_run_id)

            if task_slug is not None and result.task_slug != task_slug:
                raise ValueError(
                    "Both `task_slug` and `task_run_id` were provided but the task "
                    "found using `task_run_id` has a different slug! "
                    f"`task_slug == {task_slug!r}` and "
                    f"`result.task_slug == {result.task_slug!r}`"
                )

            self.task_results[result.task_run_id] = result
            return result

        if task_slug is not None:
            result = TaskRunResult.from_task_slug(
                task_slug=task_slug, flow_run_id=self.flow_run_id
            )
            self.task_results[result.task_run_id] = result
            return result

        raise ValueError(
            "One of `task_run_id`, `task`, or `task_slug` must be provided!"
        )

    def get_mapped(
        self,
        task: Task = None,
        task_slug: str = None,
    ) -> List["TaskRunResult"]:
        if task is not None:
            if task_slug is not None and task_slug != task.slug:
                raise ValueError(
                    "Both `task` and `task_slug` were provided but "
                    f"`task.slug == {task.slug!r}` and `task_slug == {task_slug!r}`"
                )
            task_slug = task.slug

        if task_slug is not None:
            task_runs = TaskRunResult.query_for_task_runs(
                where={
                    "task_slug": {"_eq": task_slug},
                    "flow_run_id": {"_eq": self.flow_run_id},
                },
                many=True,
            )
            return [
                TaskRunResult.from_task_run_data(task_run) for task_run in task_runs
            ]

        raise ValueError("Either `task` or `task_slug` must be provided!")

    def get_all(self):
        task_run_ids = self.task_run_ids
        if len(task_run_ids) > 1000:
            raise ValueError(
                "Refusing to `get_all` for a flow with more than 1000 tasks. "
                "Please load the tasks you are interested in individually."
            )

        results = [self.get(task_run_id=id_) for id_ in task_run_ids]
        return results

    @property
    def task_run_ids(self) -> List[str]:
        # Return the cached value immediately if it exists
        if self._task_run_ids:
            return self._task_run_ids

        client = Client()

        task_query = {
            "query": {
                with_args(
                    "task_run",
                    {
                        "where": {
                            "flow_run_id": {"_eq": self.flow_run_id},
                        }
                    },
                ): {
                    "id": True,
                }
            }
        }
        result = client.graphql(task_query)
        task_runs = result.get("data", {}).get("task_run", None)

        if task_runs is None:
            logger.warning(
                f"Failed to load task run ids for flow run {self.flow_run_id}: "
                f"{result}"
            )

        task_run_ids = [task_run["id"] for task_run in task_runs]

        # If the flow run is done, we can safely cache this value
        if self.state.is_finished():
            self._task_run_ids = task_run_ids

        return task_run_ids

    def __repr__(self) -> str:
        return (
            f"FlowRunResult"
            f"("
            + ", ".join(
                [
                    f"flow_run_id={self.flow_run_id}",
                    f"flow_id={self.flow_id}",
                    f"state={self.state}",
                    f"cached_task_results={len(self.task_results)}",
                ]
            )
            + f")"
        )


class TaskRunResult:
    def __init__(
        self,
        task_run_id: str,
        task_id: str,
        task_slug: str,
        name: str,
        state: State,
        map_index: int,
        result: Any = None,
    ):
        self.task_run_id = task_run_id
        self.name = name
        self.task_id = task_id
        self.task_slug = task_slug
        self.state = state
        self.map_index = map_index

        if result is None and state is not None:
            result = state.result

        self.result = result

    @classmethod
    def from_task_run_data(cls, task_run: dict) -> "TaskRunResult":
        return cls(
            task_run_id=task_run["id"],
            name=task_run["name"],
            task_id=task_run["task"]["id"],
            task_slug=task_run["task"]["slug"],
            map_index=task_run["map_index"],
            state=State.deserialize(task_run["serialized_state"]),
        )

    @classmethod
    def from_task_run_id(cls, task_run_id: str = None) -> "TaskRunResult":
        return cls.from_task_run_data(
            cls.query_for_task_runs(where={"id": {"_eq": task_run_id}})
        )

    @classmethod
    def from_task_slug(cls, task_slug: str, flow_run_id: str) -> "TaskRunResult":
        return cls.from_task_run_data(
            cls.query_for_task_runs(
                where={
                    "task": {"slug": {"_eq": task_slug}},
                    "flow_run_id": {"_eq": flow_run_id},
                }
            )
        )

    @staticmethod
    def query_for_task_runs(where: dict, many: bool = False) -> Union[dict, List[dict]]:
        client = Client()

        query = {
            "query": {
                with_args("task_run", {"where": where}): {
                    "id": True,
                    "name": True,
                    "task": {"id": True, "slug": True},
                    "map_index": True,
                    "serialized_state": True,
                }
            }
        }

        result = client.graphql(query)
        task_runs = result.get("data", {}).get("task_run", None)

        if task_runs is None:
            raise ValueError(
                f"Received bad result while querying for task where {where}: "
                f"{result}"
            )

        if len(task_runs) > 1 and not many:
            raise ValueError(
                f"Found multiple ({len(task_runs)}) task runs while querying for task "
                f"where {where}: {task_runs}"
            )

        # Return a dict
        if not many:
            task_run = task_runs[0]
            return task_run

        # Return a list
        return task_runs

    def __repr__(self) -> str:
        return (
            f"TaskRunResult"
            f"("
            + ", ".join(
                [
                    f"task_run_id={self.task_run_id}",
                    f"task_id={self.task_id}",
                    f"task_slug={self.task_slug}",
                    f"state={self.state}",
                    f"result={self.result}",
                ]
            )
            + f")"
        )
