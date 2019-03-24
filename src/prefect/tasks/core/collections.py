"""
The tasks in this module can be used to represent collections of task results, such as
lists, tuples, sets, and dictionaries.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users create dependencies between a task and a collection of other objects.
"""
from typing import Any, Iterable

from prefect import Task


class VarArgsTask(Task):
    """
    Most task classes do not support `*args` as an input.

    This task *does* accept `*args` and automatically transforms them into `**kwargs`.

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def bind(
        self,
        *args: Any,
        upstream_tasks: Iterable[Any] = None,
        mapped: bool = False,
        flow: "prefect.Flow" = None
    ) -> Task:
        """
        Args:
            - *args: arguments to bind to the current Task's `run` method
            - mapped (bool, optional): Whether the results of these tasks should be mapped over
            - upstream_tasks ([Task], optional): a list of upstream dependencies for the
                current task.
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified

        Returns:
            - Task: the current Task instance
        """
        kwargs = {"arg_{}".format(i + 1): a for i, a in enumerate(args)}
        return super().bind(
            upstream_tasks=upstream_tasks, mapped=mapped, flow=flow, **kwargs
        )


class List(VarArgsTask):
    """
    Collects task results into a list.

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, **task_results: Any) -> list:  # type: ignore
        """
        Args:
            - **task_results (Any): task results to collect into a list

        Returns:
            - list: a list of task results
        """
        return [v for (k, v) in sorted(task_results.items())]


class Tuple(VarArgsTask):
    """
    Collects task results into a tuple.

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, **task_results: Any) -> tuple:  # type: ignore
        """
        Args:
            - **task_results (Any): task results to collect into a tuple

        Returns:
            - tuple: a tuple of task results
        """
        return tuple([v for (k, v) in sorted(task_results.items())])


class Set(VarArgsTask):
    """
    Collects task results into a set.

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, **task_results: Any) -> set:  # type: ignore
        """
        Args:
            - **task_results (Any): task results to collect into a set

        Returns:
            - set: a set of task results
        """
        return set(task_results.values())


class Dict(Task):
    """
    Collects task results into a dict.

    Args:
        - *args (Any): positional arguments for the `Task` class
        - **kwargs (Any): keyword arguments for the `Task` class
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def run(self, **task_results: Any) -> dict:  # type: ignore
        """
        Args:
            - **task_results (Any): task result key / value pairs to collect into a dict

        Returns:
            - dict: a dict of task results
        """
        return task_results
