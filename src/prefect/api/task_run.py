from typing import Any
from typing import List, Union

import prefect
from prefect.engine.state import State
from prefect.utilities.graphql import with_args, EnumValue
from prefect.utilities.logging import get_logger

# Utility to indicate a task result is not loaded to distinguish from `None` values
NotLoaded = object()

logger = get_logger("flow_run")


class TaskRun:
    def __init__(
        self,
        task_run_id: str,
        task_id: str,
        task_slug: str,
        name: str,
        state: State,
        map_index: int,
        flow_run_id: str,
    ):
        self.task_run_id = task_run_id
        self.name = name
        self.task_id = task_id
        self.task_slug = task_slug
        self.state = state
        self.map_index = map_index
        self.flow_run_id = flow_run_id

        # Uses NotLoaded so to separate from return values of `None`
        self._result: Any = NotLoaded

    @property
    def result(self):
        if self._result is NotLoaded:
            # Load the result from the result location
            self._result = self._load_result()

        return self._result

    def _load_result(self) -> Any:
        if self.state.is_mapped():
            # Mapped tasks require the state.map_states field to be manually filled
            # to load results of all mapped subtasks
            child_task_runs = [
                self.from_task_run_data(task_run)
                for task_run in self.query_for_task_runs(
                    where={
                        "task": {"slug": {"_eq": self.task_slug}},
                        "flow_run_id": {"_eq": self.flow_run_id},
                        # Ignore the root task since we are the root task
                        "map_index": {"_neq": -1},
                    },
                    # Ensure the returned tasks are ordered matching map indices
                    order_by={"map_index": EnumValue("asc")},
                    many=True,
                )
            ]

            self.state.map_states = [task_run.state for task_run in child_task_runs]

        # Fire the state result hydration
        self.state.load_result()
        return self.state.result

    @classmethod
    def from_task_run_data(cls, task_run: dict) -> "TaskRun":
        return cls(
            task_run_id=task_run["id"],
            name=task_run["name"],
            task_id=task_run["task"]["id"],
            task_slug=task_run["task"]["slug"],
            map_index=task_run["map_index"],
            flow_run_id=task_run["flow_run_id"],
            state=State.deserialize(task_run["serialized_state"]),
        )

    @classmethod
    def from_task_run_id(cls, task_run_id: str = None) -> "TaskRun":
        if not isinstance(task_run_id, str):
            raise TypeError(
                f"Unexpected type {type(task_run_id)!r} for `task_run_id`, "
                f"expected 'str'."
            )

        return cls.from_task_run_data(
            cls.query_for_task_runs(where={"id": {"_eq": task_run_id}})
        )

    @classmethod
    def from_task_slug(cls, task_slug: str, flow_run_id: str) -> "TaskRun":
        return cls.from_task_run_data(
            cls.query_for_task_runs(
                where={
                    "task": {"slug": {"_eq": task_slug}},
                    "flow_run_id": {"_eq": flow_run_id},
                    # Since task slugs can be duplicated for mapped tasks, only allow
                    # the root task to be pulled by this
                    "map_index": {"_eq": -1},
                }
            )
        )

    @staticmethod
    def query_for_task_runs(
        where: dict,
        many: bool = False,
        order_by: dict = None,
        error_on_empty: bool = True,
    ) -> Union[dict, List[dict]]:
        """
        Query for task run data necessary to initialize `TaskRun` instances
        with `TaskRun.from_task_run_data`.

        Args:
            where (required): The Hasura `where` clause to filter by
            many (optional): Are many results expected? If `False`, a single record will
                be returned and if many are found by the `where` clause an exception
                will be thrown. If `True` a list of records will be returned.
            order_by (optional): An optional Hasura `order_by` clause to order results
                by. Only applicable when `many` is `True`
            error_on_empty (optional): If `True` and no tasks are found, a `ValueError`
                will be raised. If `False`, an empty list or dict will be returned
                based on the value of `many`.

        Returns:
            A dict of task run information (or a list of dicts if `many` is `True`)
        """
        client = prefect.Client()

        query_args = {"where": where}
        if order_by is not None:
            query_args["order_by"] = order_by

        query = {
            "query": {
                with_args("task_run", query_args): {
                    "id": True,
                    "name": True,
                    "task": {"id": True, "slug": True},
                    "map_index": True,
                    "serialized_state": True,
                    "flow_run_id": True,
                }
            }
        }

        result = client.graphql(query)
        task_runs = result.get("data", {}).get("task_run", None)

        if task_runs is None:
            raise ValueError(
                f"Received bad result while querying for task runs where {where}: "
                f"{result}"
            )

        if len(task_runs) > 1 and not many:
            raise ValueError(
                f"Found multiple ({len(task_runs)}) task runs while querying for task "
                f"runs where {where}: {task_runs}"
            )

        if not task_runs:  # Empty list
            if error_on_empty:
                raise ValueError(
                    f"No task runs found while querying for task runs where {where}"
                )
            return [] if many else {}

        # Return a dict
        if not many:
            task_run = task_runs[0]
            return task_run

        # Return a list
        return task_runs

    def update(self) -> "TaskRun":
        """
        Get the a new copy of this object with the newest data from the API
        """
        return self.from_task_run_id(
            task_run_id=self.task_run_id,
        )

    def __repr__(self) -> str:
        result = "<not loaded>" if self._result is NotLoaded else self.result
        return (
            f"TaskRun"
            f"("
            + ", ".join(
                [
                    f"task_run_id={self.task_run_id}",
                    f"task_id={self.task_id}",
                    f"task_slug={self.task_slug}",
                    f"state={self.state}",
                    f"result={result}",
                ]
            )
            + f")"
        )
