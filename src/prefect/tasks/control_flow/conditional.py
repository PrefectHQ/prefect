import warnings
from typing import Any, Dict

import prefect
from prefect import Task
from prefect.engine import signals
from prefect.engine.result import NoResult


__all__ = ["switch", "ifelse"]


class Merge(Task):
    def __init__(self, **kwargs) -> None:
        if kwargs.setdefault("skip_on_upstream_skip", False):
            raise ValueError("Merge tasks must have `skip_on_upstream_skip=False`.")
        super().__init__(**kwargs)

    def run(self, **task_results: Any) -> Any:
        return next((v for v in task_results.values() if v != NoResult), None)


class CompareValue(Task):
    """
    This task stores a `value` at initialization and compares it to a `value` received at runtime.
    If the values don't match, it raises a SKIP exception.

    Args:
        - value (Any): the value this task will attempt to match when it runs
        - **kwargs: keyword arguments for the Task
    """

    def __init__(self, value: Any, **kwargs: Any):
        self.value = value
        kwargs.setdefault("name", 'CompareValue: "{}"'.format(value))
        super().__init__(**kwargs)

    def run(self, value: Any) -> None:
        """
        Raises a SKIP signal if the passed value does not match the task's match value;
        succeeds silently otherwise.

        Args:
            - value (Any): the value that will be matched against the task's value.
        """
        if value != self.value:
            raise signals.SKIP(
                'Provided value "{}" did not match "{}"'.format(value, self.value)
            )


def switch(condition: Task, cases: Dict[Any, Task]) -> None:
    """
    Adds a SWITCH to a workflow.

    The condition task is evaluated and the result is compared to the keys of the cases
    dictionary. The task corresponding to the matching key is run; all other tasks are
    skipped. Any tasks downstream of the skipped tasks are also skipped unless they set
    `skip_on_upstream_skip=False`.

    Args:
        - condition (Task): a task whose result forms the condition for the switch
        - cases (Dict[Any, Task]): a dict representing the "case" statements of the switch.
            The value of the `condition` task will be compared to the keys of this dict, and
            the matching task will be executed.

    Raises:
        - PrefectWarning: if any of the tasks in "cases" have upstream dependencies,
            then this task will warn that those upstream tasks may run whether or not the switch condition matches their branch. The most common cause of this
            is passing a list of tasks as one of the cases, which adds the `List` task
            to the switch condition but leaves the tasks themselves upstream.
    """

    with prefect.tags("switch"):
        for value, task in cases.items():
            task = prefect.utilities.tasks.as_task(task)

            active_flow = prefect.context.get("flow", None)
            if (
                active_flow
                and task in active_flow.tasks
                and active_flow.upstream_tasks(task)
            ):
                # TODO link this warning to a more complete example in the docs.
                warnings.warn(
                    "One of the tasks passed to the switch condition has upstream "
                    "dependencies: {}. Those upstream tasks could run even if the "
                    "switch condition fails, which might cause unexpected "
                    "results.".format(task),
                    prefect.utilities.exceptions.PrefectWarning,
                )

            match_condition = CompareValue(value=value).bind(value=condition)
            task.set_dependencies(upstream_tasks=[match_condition])


def ifelse(condition: Task, true_task: Task, false_task: Task) -> None:
    """
    Builds a conditional branch into a workflow.

    If the condition evaluates True(ish), the true_task will run. If it
    evaluates False(ish), the false_task will run. The task doesn't run is Skipped, as are
    all downstream tasks that don't set `skip_on_upstream_skip=False`.

    Args:
        - condition (Task): a task whose boolean result forms the condition for the ifelse
        - true_task (Task): a task that will be executed if the condition is True
        - false_task (Task): a task that will be executed if the condition is False
    """

    switch(condition=condition, cases={True: true_task, False: false_task})


def merge(*tasks: Task) -> Task:
    """
    Merges conditional branches back together.

    A conditional branch in a flow results in one or more tasks proceeding and one or
    more tasks skipping. It is often convenient to merge those branches back into a
    single result. This function is a simple way to achieve that goal.

    The merge will return the first real result it encounters, or `None`. If multiple
    tasks might return a result, group them with a list.

    Example:
        ```python
        with Flow("My Flow"):
            true_branch = ActionIfTrue()
            false_branch = ActionIfFalse()
            ifelse(CheckCondition(), true_branch, false_branch)

            merged_result = merge(true_branch, false_branch)
        ```

    Args:
        - *tasks (Task): tasks whose results should be merged into a single result. The tasks are
            assumed to all sit downstream of different `switch` branches, such that only
            one of them will contain a result and the others will all be skipped.

    Returns:
        - Task: a Task representing the merged result.

    """
    return Merge().bind(**{"task_{}".format(i + 1): t for i, t in enumerate(tasks)})
