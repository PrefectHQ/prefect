import pytest

import prefect
from prefect.state import TaskRunState


def test_taskrunner():
    """
    Test running a task that finishes successfully and returns a result
    """
    t1 = prefect.tasks.FunctionTask(fn=lambda: 1)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result['state'].is_successful()
    assert result['result'] == 1


def test_taskrunner_error():
    """
    Test running a task that has an error
    """
    t1 = prefect.tasks.FunctionTask(fn=lambda: 1 / 0)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result['state'].is_failed()
    assert result['result'] is None


def test_taskrunner_signal():
    """
    Test running a task that raises a Prefect signal
    """

    def t1_fn():
        raise prefect.signals.FAIL()

    t1 = prefect.tasks.FunctionTask(fn=t1_fn)
    tr1 = prefect.runners.TaskRunner(task=t1)
    result = tr1.run()
    assert result['state'].is_failed()
    assert result['result'] is None

    def t2_fn():
        raise prefect.signals.SKIP()

    t2 = prefect.tasks.FunctionTask(fn=t2_fn)
    tr2 = prefect.runners.TaskRunner(task=t2)
    result = tr2.run()
    assert result['state'].is_skipped()
    assert result['result'] is None

    def t3_fn():
        raise prefect.signals.SUCCESS()

    t3 = prefect.tasks.FunctionTask(fn=t3_fn)
    tr3 = prefect.runners.TaskRunner(task=t3)
    result = tr3.run()
    assert result['state'].is_successful()
    assert result['result'] is None


def test_run_finished_task():
    """
    Test running tasks that are given finished states.

    They shouldn't run and the state should be returned.
    """
    t1 = prefect.tasks.FunctionTask(fn=lambda: 1)
    tr1 = prefect.runners.TaskRunner(task=t1)
    result1 = tr1.run(state=TaskRunState.FAILED)
    assert result1['state'].is_failed()
    assert result1['result'] is None

    t2 = prefect.tasks.FunctionTask(fn=lambda: 1 / 0)
    tr2 = prefect.runners.TaskRunner(task=t2)
    result2 = tr2.run(state=TaskRunState.SUCCESS)
    assert result2['state'].is_successful()
    assert result2['result'] is None

    t2 = prefect.tasks.FunctionTask(fn=lambda: 1 / 0)
    tr2 = prefect.runners.TaskRunner(task=t2)
    result2 = tr2.run(state=TaskRunState.SKIPPED)
    assert result2['state'].is_skipped()
    assert result2['result'] is None
