import prefect
from prefect import signals, Task
from prefect.tasks.core import FunctionTask, Not

__all__ = ['ifelse']

class Condition(FunctionTask):

    def __init__(self, condition_fn, name=None, **kwargs):
        """
        This task evaluates a True/False condition
        """
        super().__init__(fn=condition_fn, name=name, **kwargs)


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


def ifelse(condition, true_task, false_task, name=None):
    """
    Builds a conditional branch into a workflow.

    If the condition evaluates True(ish), the true_task will run. If it
    evaluates False(ish), the false_task will run. The branch that doesn't run
    will be stopped by raising a signals.DONTRUN() signal.
    """
    if not isinstance(condition, Task):
        condition = Condition(condition_fn=condition, name=name)

    # build true branch
    true_eval = EvaluateCondition(raise_if_false=signals.SKIP_DOWNSTREAM)
    true_eval.run_after(condition=condition)
    true_task.run_after(true_eval)

    # build false branch
    false_eval = EvaluateCondition(raise_if_false=signals.SKIP_DOWNSTREAM)
    inv_condition = Not().run_after(x=condition)
    false_eval.run_after(condition=inv_condition)
    false_task.run_after(false_eval)

    return condition
