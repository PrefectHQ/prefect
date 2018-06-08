import prefect
from prefect import signals, Task
from prefect.tasks.core import operators
from prefect.utilities.tasks import as_task_result

__all__ = ["ifelse"]


class EvaluateCondition(Task):
    def __init__(self, raise_if_false=signals.FAIL, **kwargs):
        """
        A special task that receives a boolean value and succeeds if that value
        is True. If it's false, it raises the "raise_if_false" error.
        """
        self.raise_if_false = raise_if_false
        super().__init__(**kwargs)

    def run(self, condition):
        if not condition:
            raise self.raise_if_false


def switch(condition, patterns, name=None):
    """
    Builds a switch into a workflow.

    The result of the `condition` is looked up in the `patterns` dict and the
    resulting Task continues execution. All other pattern Tasks are skipped.
    """
    if not isinstance(condition, Task):
        condition = as_task_result(condition)

    for pattern, task in patterns.items():
        eval_cond = EvaluateCondition(raise_if_false=signals.SKIP_DOWNSTREAM)
        eval_cond.set(condition=operators.Eq(condition, pattern), run_before=task)

    return condition


def ifelse(condition, true_task, false_task):
    """
    Builds a conditional branch into a workflow.

    If the condition evaluates True(ish), the true_task will run. If it
    evaluates False(ish), the false_task will run. The branch that doesn't run
    will be stopped by raising a signals.DONTRUN() signal.
    """

    return switch(condition=condition, patterns={True: true_task, False: false_task})
