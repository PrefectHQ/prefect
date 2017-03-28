import prefect
import pytest


def fn(**params):
    """ a test function for tasks"""
    pass


def setup_flow():
    with prefect.flow.Flow('test') as f:
        t1 = prefect.task.Task(fn=fn, name='t1')
        t2 = prefect.task.Task(fn=fn, name='t2')
        t1.run_before(t2)
    return f


def test_create_runner():
    flow = setup_flow()
    tr = prefect.runners.task_runner.TaskRunner(
        task=flow.get_task('t1'), run_id='1', params={},)
    tr.run({})
    tr.run({})
