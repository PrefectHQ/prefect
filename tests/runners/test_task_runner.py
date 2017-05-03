import pytest
import prefect

def test_simple_taskrunner():
    with prefect.Flow('flow') as f:
        t1 = prefect.Task(fn=lambda: 1)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result.is_successful()
    assert result.result == 1
