from prefect.flow import Flow
from prefect.task import Task
import pytest


def fn():
    pass


def test_create_task():
    """Test task creation"""

    # tasks require Flows
    with pytest.raises(ValueError) as e:
        t = Task(fn=fn)

    f = Flow('test_flow')
    t = Task(fn=fn, name='test', flow=f)
    assert t.flow is f

    with pytest.raises(TypeError) as e:
        Task(fn=fn, flow=f, retries=None)
    assert 'Retries must be an int' in str(e)

    with pytest.raises(TypeError) as e:
        Task(fn=fn, flow=f, retry_delay=5)
    assert 'Retry delay must be a timedelta' in str(e)


def test_flow_context_manager():
    """Tests that flows can be used as context managers"""

    with Flow('test_flow') as f:
        t = Task(fn=fn, name='test')

        # nested context manager
        with Flow('test_flow_2') as f2:
            t2 = Task(fn=fn, name='test')

        # return to original context manager
        t3 = Task(fn=fn, name='test1')

    assert t.flow is f
    assert t in f.graph

    assert t2.flow is f2
    assert t2 in f2.graph
    assert t2 not in f.graph

    assert t3.flow is f
    assert t3 in f.graph


def test_add_task_to_flow_after_flow_assigned():
    with Flow('test_flow') as f:
        t = Task(fn=fn, name='test')

    with pytest.raises(ValueError) as e:
        t2 = Task(fn=fn, name='test', flow=f)
    assert 'already exists in this Flow' in str(e)

    with pytest.raises(ValueError) as e:
        f2 = Flow('test_flow_2')
        f2.add_task(t)
    assert 'already in another Flow' in str(e)


def test_task_relationships():
    """Test task relationships"""
    with Flow('test') as f:
        before = Task(fn=fn, name='before')
        after = Task(fn=fn, name='after')

    before.run_before(after)
    assert before in f.graph
    assert after in f.graph
    assert before in f.graph[after]

    # same test, calling `run_after`
    with Flow('test') as f:
        before = Task(fn=fn, name='before')
        before2 = Task(fn=fn, name='before_2')
        after = Task(fn=fn, name='after')

    after.run_after(before, before2)
    assert before in f.graph
    assert before2 in f.graph
    assert after in f.graph
    assert before in f.graph[after]
    assert before2 in f.graph[after]


def test_shift_relationship_sugar():
    """Test task relationships with | and >> and << sugar"""
    with Flow('test') as f:
        before = Task(fn=fn, name='before')
        after = Task(fn=fn, name='after')

    before | after
    assert before in f.graph
    assert after in f.graph
    assert before in f.graph[after]

    with Flow('test') as f:
        before = Task(fn=fn, name='before')
        after = Task(fn=fn, name='after')

    before >> after
    assert before in f.graph
    assert after in f.graph
    assert before in f.graph[after]

    # same test, calling `run_after`
    with Flow('test') as f:
        before = Task(fn=fn, name='before')
        after = Task(fn=fn, name='after')

    after << before
    assert before in f.graph
    assert after in f.graph
    assert before in f.graph[after]
