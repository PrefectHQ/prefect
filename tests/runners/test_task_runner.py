import pytest
import prefect

def test_simple_taskrunner():
    with prefect.Flow('flow') as f:
        t1 = prefect.Task(fn=lambda: 1)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result.is_successful()
    assert result.value['value'] == 1



def test_yielding_taskrunner():
    """
    Tests that TaskRunner properly runs yielded tasks
    """
    yielded = []

    with prefect.Flow('flow') as f:

        def yield_tasks():
            for i in range(5):
                yield prefect.Task(fn=lambda: yielded.append(i), flow=f)
            return 'done'

        t1 = prefect.Task(fn=yield_tasks)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result.is_successful()
    assert result.value['value'] == 'done'
    assert yielded == list(range(5))


def test_subtask_taskrunner():
    """
    Tests that TaskRunner properly runs tasks that explicitly run themselves,
    both blocking and non-blocking
    """
    yielded = []

    with prefect.Flow('flow') as f:

        def yield_tasks():
            for i in range(5):
                task = prefect.Task(fn=lambda: i, flow=f)
                result_i = prefect.context.run_task(task, block=True)
                assert result_i.value['value'] == i
                task = prefect.Task(fn=lambda: yielded.append(i), flow=f)
                prefect.context.run_task(task, block=False)
            return 'done'

        t1 = prefect.Task(fn=yield_tasks)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result.is_successful()
    assert result.value['value'] == 'done'
    assert yielded == list(range(5))
