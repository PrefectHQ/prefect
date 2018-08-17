from typing import Any, Dict

import prefect
from prefect import Task
from prefect.engine import signals

__all__ = ["switch", "ifelse"]


class Match(Task):
    """
    Args:
        - match_value (Any): the value this task will attempt to match when it runs
        - **kwargs: keyword arguments for the Task
    """

    def __init__(self, match_value: Any, **kwargs) -> None:
        self.match_value = match_value
        kwargs.setdefault("name", 'match: "{}"'.format(match_value))
        super().__init__(**kwargs)

    def run(self, value: Any) -> None:
        """
        Raises a SKIP signal if the passed value does not match the task's match value;
        succeeds silently otherwise.

        Args:
            - value (Any): the value that will be matched against the task's match_value.
        """
        if value != self.match_value:
            raise signals.SKIP(
                'Provided value "{}" did not match "{}"'.format(value, self.match_value)
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
    """

    with prefect.groups("switch"):
        for match_value, task in cases.items():
            match_condition = Match(match_value=match_value)(value=condition)
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
