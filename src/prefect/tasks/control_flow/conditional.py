from typing import Any, Dict

import prefect
from prefect import Task
from prefect.engine import signals
from prefect.tasks.core import operators
from prefect.utilities.tasks import as_task

__all__ = ["switch", "ifelse"]


class Match(Task):
    def __init__(self, match_value: str, **kwargs):
        self.match_value = match_value
        kwargs.setdefault("name", 'match: "{}"'.format(match_value))
        super().__init__(**kwargs)

    def run(self, value):
        if value != self.match_value:
            raise signals.SKIP(
                'Provided value "{}" did not match "{}"'.format(value, self.match_value)
            )


def switch(condition: Task, cases: Dict[Any, Task]):
    """
    Builds a switch into a workflow.

    The result of the `condition` is looked up in the `cases` dict and the
    resulting Task continues execution. All other pattern Tasks are skipped.
    """

    with prefect.group("switch"):
        for match_value, task in cases.items():
            match_condition = Match(match_value=match_value)(value=condition)
            task.set_dependencies(upstream_tasks=[match_condition])


def ifelse(condition, true_task, false_task):
    """
    Builds a conditional branch into a workflow.

    If the condition evaluates True(ish), the true_task will run. If it
    evaluates False(ish), the false_task will run. The branch that doesn't run
    will be stopped by raising a signals.DONTRUN() signal.
    """

    return switch(condition=condition, cases={True: true_task, False: false_task})
