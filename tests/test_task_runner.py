import prefect
import pytest


def fn(**params):
    """ a test function for tasks"""
    pass


def fn_err():
    1 / 0


def setup_flow():
    with prefect.flow.Flow('test') as f:
        t1 = prefect.task.Task(fn=fn, name='t1')
        t_err = prefect.task.Task(fn=fn_err, name='t_err')
        t1.run_before(t_err)
    return f


def test_create_runner_and_run_twice():
    flow = setup_flow()
    tr = prefect.runners.task_runner.TaskRunner(
        task=flow.get_task('t1'),
        run_id='1',
        params={},)
    tr.run({})
    assert tr.state.is_successful()
    tr.run({})
    assert tr.state.is_successful()


def test_create_runner_and_run_twice_with_error():
    flow = setup_flow()
    tr = prefect.runners.task_runner.TaskRunner(
        task=flow.get_task('t_err'),
        run_id='1',
        params={},)
    tr.run({})
    assert tr.state.is_failed()
