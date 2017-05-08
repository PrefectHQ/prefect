import pytest
import prefect
import time


def test_local_executor():
    """
    Test that the LocalExecutor runs tasks in sequence
    """
    with prefect.Flow('flow') as f:
        t1 = prefect.Task(fn=lambda: time.sleep(.1))
        t2 = prefect.Task(fn=lambda: time.sleep(.1))
        t3 = prefect.Task(fn=lambda: time.sleep(.1))

    runner = prefect.runners.FlowRunner(
        flow=f, executor=prefect.runners.executors.LocalExecutor())
    start_time = time.time()
    result = runner.run()
    end_time = time.time()
    assert result.is_successful()
    assert 0.3 <= end_time - start_time <= 0.4

def test_threadpool_executor():
    """
    Test that the ThreadPoolExecutor runs tasks in parallel
    """
    with prefect.Flow('flow') as f:
        t1 = prefect.Task(fn=lambda: time.sleep(.1))
        t2 = prefect.Task(fn=lambda: time.sleep(.1))
        t3 = prefect.Task(fn=lambda: time.sleep(.1))

    runner = prefect.runners.FlowRunner(
        flow=f, executor=prefect.runners.executors.ThreadPoolExecutor(3))
    start_time = time.time()
    result = runner.run()
    end_time = time.time()
    assert result.is_successful()
    assert 0.1 <= end_time - start_time <= 0.2
