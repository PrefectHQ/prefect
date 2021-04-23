from typing import Any, List

from prefect import Client
from prefect.engine.state import State
from prefect.utilities.graphql import with_args, EnumValue
from prefect.utilities.logging import get_logger

# Utility to indicate a task result is not loaded to distinguish from `None` values
NotLoaded = object()

logger = get_logger("backend.flow_run")


class TaskRunView:
    """
    A view of Task Run data stored in the Prefect API.

    Provides lazy loading of task run return values from Prefect `Result` locations.

    This object is designed to be an immutable view of the data stored in the Prefect
    backend API at the time it is created.

    Attributes:
        task_run_id: The task run uuid
        task_id: The uuid of the task associated with this task run
        task_slug: The slug of the task associated with this task run
        name: The task run name
        state: The state of the task run
        map_index: The map index of the task run. Is -1 if it is not a mapped subtask,
            otherwise it is in the index of the task run in the mapping
        flow_run_id: The uuid of the flow run associated with this task run
        result: The result of this task run loaded from the `Result` location
    """

    def __init__(
        self,
        task_run_id: str,
        task_id: str,
        task_slug: str,
        name: str,
        state: State,
        map_index: int,
        flow_run_id: str,
    ) -> None:
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
    def result(self) -> Any:
        """
        The result of this task run loaded from the `Result` location. Lazily loaded
        on the first call then cached for repeated access. For the parent of mapped
        task runs, this will include the results of all children. May require
        credentials to be present if the result location is remote (ie S3). If your
        flow was run on another machine and `LocalResult` was used, we will fail
        to load the result.

        Returns:
            Any: The value your task returned
        """
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
                )
            ]

            self.state.map_states = [task_run.state for task_run in child_task_runs]

        # Fire the state result hydration
        self.state.load_result()
        return self.state.result

    @classmethod
    def from_task_run_data(cls, task_run: dict) -> "TaskRunView":
        task_run_id = task_run.pop("id")
        task_data = task_run.pop("task")
        serialized_state = task_run.pop("serialized_state")

        return cls(
            task_run_id=task_run_id,
            state=State.deserialize(serialized_state),
            task_id=task_data["id"],
            task_slug=task_data["slug"],
            **task_run,
        )

    @classmethod
    def from_task_run_id(cls, task_run_id: str = None) -> "TaskRunView":
        if not isinstance(task_run_id, str):
            raise TypeError(
                f"Unexpected type {type(task_run_id)!r} for `task_run_id`, "
                f"expected 'str'."
            )

        return cls.from_task_run_data(
            cls.query_for_task_run(where={"id": {"_eq": task_run_id}})
        )

    @classmethod
    def from_task_slug(cls, task_slug: str, flow_run_id: str) -> "TaskRunView":
        return cls.from_task_run_data(
            cls.query_for_task_run(
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
    def query_for_task_run(where: dict, **kwargs: Any) -> dict:
        """
        Query for task run data using `query_for_task_runs` but throw an exception if
        more than one matching task run is found

        Args:
            where: The `where` clause to use
            **kwargs: Additional kwargs are passed to `query_for_task_runs`

        Returns:
            A dict of task run data
        """
        task_runs = TaskRunView.query_for_task_runs(where=where, **kwargs)

        if len(task_runs) > 1:
            raise ValueError(
                f"Found multiple ({len(task_runs)}) task runs while querying for task "
                f"runs where {where}: {task_runs}"
            )

        if not task_runs:
            # Erroring on an empty result is handled by `query_for_task_runs`
            return {}

        task_run = task_runs[0]
        return task_run

    @staticmethod
    def query_for_task_runs(
        where: dict,
        order_by: dict = None,
        error_on_empty: bool = True,
    ) -> List[dict]:
        """
        Query for task run data necessary to initialize `TaskRunView` instances
        with `TaskRunView.from_task_run_data`.

        Args:
            where (required): The Hasura `where` clause to filter by
            order_by (optional): An optional Hasura `order_by` clause to order results
                by.
            error_on_empty (optional): If `True` and no tasks are found, a `ValueError`
                will be raised.

        Returns:
           A list of dicts containing task run data
        """
        client = Client()

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

        if not task_runs:  # Empty list
            if error_on_empty:
                raise ValueError(
                    f"No task runs found while querying for task runs where {where}"
                )
            return []

        # Return a list
        return task_runs

    def get_latest(self) -> "TaskRunView":
        """
        Get the a new copy of this object with the latest data from the API

        This will not mutate the current object.

        Returns:
            A new instance of TaskRunView
        """
        return self.from_task_run_id(
            task_run_id=self.task_run_id,
        )

    def __repr__(self) -> str:
        result = "<not loaded>" if self._result is NotLoaded else self.result
        return (
            f"{type(self).__name__}"
            "("
            + ", ".join(
                [
                    f"task_run_id={self.task_run_id!r}",
                    f"task_id={self.task_id!r}",
                    f"task_slug={self.task_slug!r}",
                    f"state={self.state}",
                    f"result={result}",
                ]
            )
            + ")"
        )
