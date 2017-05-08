import pytest
import prefect


def test_simple_flowrunner_success():
    with prefect.Flow('flow') as f:
        t1 = prefect.Task(fn=lambda: 1)
        t2 = prefect.Task(fn=lambda: 1)

        t1.run_before(t2)

    result = prefect.runners.FlowRunner(flow=f).run()
    assert result.is_successful()
    assert all(s.is_successful() for s in result.value.values())

def test_simple_flowrunner_fail():
    with prefect.Flow('flow') as f:
        t1 = prefect.Task(name='t1', fn=lambda: 1)
        t2 = prefect.Task(name='t2', fn=lambda: 1/0)

        t1.run_before(t2)

    result = prefect.runners.FlowRunner(flow=f).run()
    assert result.is_failed()
    assert result.value['t1'].is_successful()
    assert result.value['t2'].is_failed()

def test_piped_flowrunner():
    with prefect.Flow('flow') as f:
        x = prefect.Task(name='x', fn=lambda: 1)
        y = prefect.Task(name='y', fn=lambda: 2)
        z = prefect.Task(name='z', fn=lambda x, y: x + y)
        z.run_with(x=x, y=y)
    result = prefect.runners.FlowRunner(flow=f).run()
    assert result.is_successful()
    assert result.value['z'].value['value'] == 3
