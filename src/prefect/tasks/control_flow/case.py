from typing import Any

import prefect
from prefect import Task

from .conditional import CompareValue


__all__ = ("case",)


class case(object):
    """A conditional block in a flow definition.

    Used as a context-manager, ``case`` creates a block of tasks that are only
    run if the result of ``task`` is equal to ``value``.

    Args:
        - task (Task): The task to use in the comparison
        - value (Any): A constant the result of ``task`` will be compared with

    Example:

    A ``case`` block is similar to Python's if-blocks. It delimits a block
    of tasks that will only be run if the result of ``task`` is equal to
    ``value``:

    ```python
    # Standard python code
    if task == value:
        res = run_if_task_equals_value()
        other_task(res)

    # Equivalent prefect code
    with case(task, value):
        # Tasks created in this block are only run if the
        # result of ``task`` is equal to ``value``
        res = run_if_task_equals_value()
        other_task(run)
    ```

    The ``value`` argument can be any non-task object. Here we branch on a
    string result:

    ```python
    with Flow("example") as flow:
        cond = condition()

        with case(cond, "a"):
            run_if_cond_is_a()

        with case(cond, "b"):
            run_if_cond_is_b()
    ```
    """

    def __init__(self, task: Task, value: Any):
        if isinstance(value, Task):
            raise TypeError("`value` cannot be a task")

        self.task = task
        self.value = value
        self._tasks = set()

    def add_task(self, task: Task) -> None:
        """Add a new task under the case statement.

        Args:
            - task (Task): the task to add
        """
        self._tasks.add(task)

    def __enter__(self):
        self.__prev_case = prefect.context.get("case")
        prefect.context.update(case=self)

    def __exit__(self, *args):
        if self.__prev_case is None:
            prefect.context.pop("case", None)
        else:
            prefect.context.update(case=self.__prev_case)

        if self._tasks:

            flow = prefect.context.get("flow", None)
            if not flow:
                raise ValueError("Could not infer an active Flow context.")

            cond = CompareValue(self.value, name=f"case({self.value})",).bind(
                value=self.task
            )

            for child in self._tasks:
                # If a task has no upstream tasks created in this case block,
                # the case conditional should be set as an upstream task.
                if not self._tasks.intersection(flow.upstream_tasks(child)):
                    child.set_upstream(cond)
