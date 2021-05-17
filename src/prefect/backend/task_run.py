from typing import Any, List, Iterator

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

    Args:
        - task_run_id: The task run uuid
        - task_id: The uuid of the task associated with this task run
        - task_slug: The slug of the task associated with this task run
        - name: The task run name
        - state: The state of the task run
        - map_index: The map index of the task run. Is -1 if it is not a mapped subtask,
             otherwise it is in the index of the task run in the mapping
        - flow_run_id: The uuid of the flow run associated with this task run

    Properties:
        - result: The result of this task run loaded from the `Result` location; lazily
            retrieved on first use
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

    def get_result(self) -> Any:
        """
        The result of this task run loaded from the `Result` location. Lazily loaded
        on the first call then cached for repeated access. For the parent of mapped
        task runs, this will include the results of all children. May require
        credentials to be present if the result location is remote (ie S3). If your
        flow was run on another machine and `LocalResult` was used, we will fail
        to load the result.

        See `TaskRunView.iter_mapped` for lazily iterating through mapped tasks instead
        of retrieving all of the results at once.

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
                self._from_task_run_data(task_run)
                for task_run in self._query_for_task_runs(
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

    def iter_mapped(self) -> Iterator["TaskRunView"]:
        """
        Iterate over the results of a mapped task, yielding a `TaskRunView` for each map
        index. This query is not performed in bulk so the results can be lazily
        consumed. If you want all of the task results at once, use `result` instead.

        Yields:
            A `TaskRunView` for each mapped item
        """
        if not self.state.is_mapped():
            raise TypeError(
                f"Task run {self.task_run_id!r} ({self.task_slug}) is not a "
                "mapped task."
            )

        # Generate a where clause given the map index
        where = lambda index: {
            "task": {"slug": {"_eq": self.task_slug}},
            "flow_run_id": {"_eq": self.flow_run_id},
            "map_index": {"_eq": index},
        }
        map_index = 0
        while True:  # Iterate until we are out of child task runs
            task_run_data = self._query_for_task_run(
                where=where(map_index), error_on_empty=False
            )
            if not task_run_data:
                break

            yield self._from_task_run_data(task_run_data)
            map_index += 1

    @classmethod
    def _from_task_run_data(cls, task_run: dict) -> "TaskRunView":
        """
        Instantiate a `TaskRunView` from serialized data

        This method deserializes objects into their Prefect types.

        Args:
            - task_run: The serialized task run data

        Returns:
            A populated `TaskRunView` instance
        """
        task_run = task_run.copy()  # Create a copy to avoid mutation
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
        """
        Get an instance of this class; query by task run id

        Args:
            - task_run_id: The UUID identifying the task run in the backend

        Returns:
            A populated `TaskRunView` instance
        """
        if not isinstance(task_run_id, str):
            raise TypeError(
                f"Unexpected type {type(task_run_id)!r} for `task_run_id`, "
                f"expected 'str'."
            )

        return cls._from_task_run_data(
            cls._query_for_task_run(where={"id": {"_eq": task_run_id}})
        )

    @classmethod
    def from_task_slug(
        cls, task_slug: str, flow_run_id: str, map_index: int = -1
    ) -> "TaskRunView":
        """
        Get an instance of this class; query by task slug and flow run id.

        Args:
            - task_slug: The unique string identifying this task in the flow. Typically
                `<task-name>-1`.
            - flow_run_id: The UUID identifying the flow run the task run occurred in
            - map_index (optional): The index to access for mapped tasks; defaults to
                the parent task with a map index of -1

        Returns:
            A populated `TaskRunView` instance
        """
        return cls._from_task_run_data(
            cls._query_for_task_run(
                where={
                    "task": {"slug": {"_eq": task_slug}},
                    "flow_run_id": {"_eq": flow_run_id},
                    "map_index": {"_eq": map_index},
                }
            )
        )

    @staticmethod
    def _query_for_task_run(where: dict, **kwargs: Any) -> dict:
        """
        Query for task run data using `_query_for_task_runs` but throw an exception if
        more than one matching task run is found

        Args:
            - where: The `where` clause to use
            - **kwargs: Additional kwargs are passed to `_query_for_task_runs`

        Returns:
            A dict of task run data
        """
        task_runs = TaskRunView._query_for_task_runs(where=where, **kwargs)

        if len(task_runs) > 1:
            raise ValueError(
                f"Found multiple ({len(task_runs)}) task runs while querying for task "
                f"runs where {where}: {task_runs}"
            )

        if not task_runs:
            # Erroring on an empty result is handled by `_query_for_task_runs`
            return {}

        task_run = task_runs[0]
        return task_run

    @staticmethod
    def _query_for_task_runs(
        where: dict,
        order_by: dict = None,
        error_on_empty: bool = True,
    ) -> List[dict]:
        """
        Query for task run data necessary to initialize `TaskRunView` instances
        with `TaskRunView.from_task_run_data`.

        Args:
            - where (required): The Hasura `where` clause to filter by
            - order_by (optional): An optional Hasura `order_by` clause to order results
                by.
            - error_on_empty (optional): If `True` and no tasks are found, a `ValueError`
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

        if not task_runs and error_on_empty:
            raise ValueError(
                f"No task runs found while querying for task runs where {where}"
            )

        return task_runs

    def __repr__(self) -> str:
        result = "<not loaded>" if self._result is NotLoaded else repr(self._result)
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

    def __eq__(self, other: Any) -> Any:
        if not isinstance(other, TaskRunView):
            return NotImplemented

        return other.task_run_id == self.task_run_id and other.state == self.state
