from collections import defaultdict
from types import MappingProxyType
from typing import Iterator, Iterable
from typing import List, Optional, Dict, Set

import prefect
from prefect.api.task_run import TaskRun
from prefect.core.task import Task
from prefect.engine.state import State
from prefect.utilities.graphql import with_args
from prefect.utilities.logging import get_logger


logger = get_logger("flow_run")


class FlowRun:
    def __init__(
        self,
        flow_run_id: str = None,
        flow_id: str = None,
        task_runs: Iterable["TaskRun"] = None,
        state: State = None,
    ):
        self.flow_run_id = flow_run_id
        self.flow_id = flow_id
        self.state = state

        # Cached value of all task run ids for this flow run, only cached if the flow
        # is done running
        self._task_run_ids: Optional[List[str]] = None

        # Store a mapping of task run ids to task runs
        self._task_runs: Dict[str, "TaskRun"] = {}

        # Store a mapping of slugs to task run ids (mapped tasks share a slug)
        self._task_slug_to_task_run_ids: Dict[str, Set[str]] = defaultdict(set)

        if task_runs is not None:
            for task_run in task_runs:
                self._add_task_run(task_run)

    def _add_task_run(self, task_run: "TaskRun"):
        self._task_runs[task_run.task_run_id] = task_run
        self._task_slug_to_task_run_ids[task_run.task_slug].add(task_run.task_run_id)

    def update(self) -> "FlowRun":
        """
        Get the a new copy of this object with the newest data from the API
        """
        return self.from_flow_run_id(
            flow_run_id=self.flow_run_id,
            load_static_tasks=False,
            _task_runs=self._task_runs.values(),
        )

    @property
    def task_runs(self) -> MappingProxyType:
        return MappingProxyType(self._task_runs)

    @classmethod
    def from_flow_run_id(
        cls,
        flow_run_id: str,
        load_static_tasks: bool = True,
        _task_runs: Iterable["TaskRun"] = None,
    ) -> "FlowRun":
        """
        Get an instance of this class filled with information by querying for the given
        flow run id

        Args:
            flow_run_id: the flow run id to lookup
            load_static_tasks: Pre-populate the task runs with results from flow tasks
                that are unmapped.
            _task_runs: Pre-populate the task runs with an existing iterable of task
                runs

        Returns:
            A populated `FlowRun` instance
        """
        client = prefect.Client()

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
            task_run_data = TaskRun.query_for_task_runs(
                where={
                    "map_index": {"_eq": -1},
                    "flow_run_id": {"_eq": flow_run_id},
                },
                many=True,
            )
            task_runs = [TaskRun.from_task_run_data(data) for data in task_run_data]

        else:
            task_runs = []

        # Combine with the provided `_task_runs` iterable
        task_runs = task_runs + list(_task_runs or [])

        return cls(
            flow_run_id=flow_run["id"],
            flow_id=flow_run["flow_id"],
            state=State.deserialize(flow_run["serialized_state"]),
            task_runs=task_runs,
        )

    def get(
        self, task: Task = None, task_slug: str = None, task_run_id: str = None
    ) -> "TaskRun":
        """
        Get information about a task run from this flow run. Lookup is available by one
        of the following arguments. If the task information is not available locally
        already, we will query the database for it.

        Args:
            task:
            task_slug:
            task_run_id:

        Returns:
            TaskRun
        """

        if task is not None:
            if not task.slug and not task_slug:
                raise ValueError(
                    f"Given task {task} does not have a `slug` set and cannot be "
                    "used for lookups; this generally occurs when the flow has not "
                    "been registered or serialized."
                )

            if task_slug is not None and task_slug != task.slug:
                raise ValueError(
                    "Both `task` and `task_slug` were provided but they contain "
                    "different slug values! "
                    f"`task.slug == {task.slug!r}` and `task_slug == {task_slug!r}`"
                )

            # If they've passed a task_slug that matches this task's slug we can
            # basically ignore the passed `task` object
            if not task_slug:
                task_slug = task.slug

        if task_run_id is not None:
            # Load from the cache if available or query for results
            result = (
                self.task_runs[task_run_id]
                if task_run_id in self._task_runs
                else TaskRun.from_task_run_id(task_run_id)
            )

            if task_slug is not None and result.task_slug != task_slug:
                raise ValueError(
                    "Both `task_slug` and `task_run_id` were provided but the task "
                    "found using `task_run_id` has a different slug! "
                    f"`task_slug == {task_slug!r}` and "
                    f"`result.task_slug == {result.task_slug!r}`"
                )

            self._add_task_run(result)
            return result

        if task_slug is not None:

            if task_slug in self._task_slug_to_task_run_ids:
                task_run_ids = self._task_slug_to_task_run_ids[task_slug]
                if len(task_run_ids) > 1:
                    # We have a mapped task, return the base task
                    for task_run_id in task_run_ids:
                        result = self.task_runs[task_run_id]
                        if result.map_index == -1:
                            return result

                    # We did not find the base mapped task in the cache so we'll
                    # drop through to query for it

            result = TaskRun.from_task_slug(
                task_slug=task_slug, flow_run_id=self.flow_run_id
            )
            self._add_task_run(result)
            return result

        raise ValueError(
            "One of `task_run_id`, `task`, or `task_slug` must be provided!"
        )

    def iter_mapped(
        self,
        task: Task = None,
        task_slug: str = None,
        cache_results: bool = True,
    ) -> Iterator["TaskRun"]:
        if task is not None:
            if task_slug is not None and task_slug != task.slug:
                raise ValueError(
                    "Both `task` and `task_slug` were provided but "
                    f"`task.slug == {task.slug!r}` and `task_slug == {task_slug!r}`"
                )
            task_slug = task.slug

        if task_slug is None:
            raise ValueError("Either `task` or `task_slug` must be provided!")

        where = lambda index: {
            "task": {"slug": {"_eq": task_slug}},
            "flow_run_id": {"_eq": self.flow_run_id},
            "map_index": {"_eq": index},
        }
        task_run = TaskRun.from_task_run_data(
            TaskRun.query_for_task_runs(where=where(-1))
        )
        if not task_run.state.is_mapped():
            raise TypeError(
                f"Task run {task_run.task_run_id!r} ({task_run.slug}) is not a mapped "
                f"task."
            )

        map_index = 0
        while task_run:
            task_run_data = TaskRun.query_for_task_runs(
                where=where(map_index), error_on_empty=False
            )
            if not task_run_data:
                break

            task_run = TaskRun.from_task_run_data(task_run_data)

            # Allow the user to skip the cache if they have a lot of task runs
            if cache_results:
                self._add_task_run(task_run)

            yield task_run

            map_index += 1

    def get_all(self):
        if len(self.task_run_ids) > 1000:
            raise ValueError(
                "Refusing to `get_all` for a flow with more than 1000 tasks. "
                "Please load the tasks you are interested in individually."
            )

        # Run a single query instead of querying for each task run separately
        task_run_data = TaskRun.query_for_task_runs(
            where={
                "flow_run_id": {"_eq": self.flow_run_id},
            },
            many=True,
        )
        task_runs = [TaskRun.from_task_run_data(data) for data in task_run_data]
        # Add to cache
        for task_run in task_runs:
            self._add_task_run(task_run)

        return task_runs

    @property
    def task_run_ids(self) -> List[str]:
        # Return the cached value immediately if it exists
        if self._task_run_ids:
            return self._task_run_ids

        client = prefect.Client()

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
            f"FlowRun"
            f"("
            + ", ".join(
                [
                    f"flow_run_id={self.flow_run_id}",
                    f"flow_id={self.flow_id}",
                    f"state={self.state}",
                    f"cached_task_runs={len(self.task_runs)}",
                ]
            )
            + f")"
        )
