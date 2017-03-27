import mongoengine
import pytest
from prefect.exceptions import PrefectError
import prefect
from prefect.flow import Flow


def test_create_flow():

    # name is required
    with pytest.raises(TypeError) as e:
        Flow()
    err = "__init__() missing 1 required positional argument: 'name'"
    assert err in str(e)

    # name must be a string
    with pytest.raises(TypeError) as e:
        f = Flow(name=1)
    assert 'Name must be a string' in str(e)

    f = Flow('test')


def test_cycle_detection():
    """
    Test that cycles are detected
    """
    f = Flow('test')
    # use integers as dummy tasks
    f.graph[1] = set()
    f.graph[2] = set([1])
    f.graph[3] = set([2, 1])
    tasks = f.sorted_tasks()

    # introduce a cycle
    f.graph[2].add(3)
    with pytest.raises(PrefectError) as e:
        tasks = f.sorted_tasks()
    assert 'Cycle detected' in str(e)


def test_inverted_graph():
    """
    Tests that the inverted_graph() is created properly
    """
    with Flow('test') as f:
        t1 = prefect.task.Task(fn=lambda: 1, name='t1')
        t2 = prefect.task.Task(fn=lambda: 1, name='t2')
        t3 = prefect.task.Task(fn=lambda: 1, name='t3')
        t1.run_before(t2)
        t1.run_before(t3)
    assert f.inverted_graph() == {t1: set([t2, t3]), t2: set(), t3: set()}


def test_getitem():
    """
    Test that accessing a flow as flow[task] returns the preceding tasks
    """
    with Flow('test') as f:
        t1 = prefect.task.Task(fn=lambda: 1, name='t1')
        t2 = prefect.task.Task(fn=lambda: 1, name='t2')
        t1.run_before(t2)
    assert f[t2] == set([t1])


def test_iter():
    """
    Tests that iterating over a Flow yields the tasks in order
    """
    with Flow('test') as f:
        t1 = prefect.task.Task(fn=lambda: 1, name='t1')
        t2 = prefect.task.Task(fn=lambda: 1, name='t2')
        t1.run_before(t2)
    assert list(f) == f.sorted_tasks()


def test_get_task_by_name():
    """
    Tests flow.get_task()
    """
    with Flow('test') as f:
        t1 = prefect.task.Task(fn=lambda: 1, name='t1')
        t2 = prefect.task.Task(fn=lambda: 1, name='t2')
        t1.run_before(t2)

    assert f.get_task('t1') is t1
    with pytest.raises(PrefectError):
        f.get_task('some task')


def test_serialize():
    with Flow('test') as f:
        t1 = prefect.task.Task(fn=lambda: 1, name='t1')
        t2 = prefect.task.Task(fn=lambda: 1, name='t2')
        t1.run_before(t2)

    serialized = f.serialize()
    f2 = Flow.from_serialized(serialized)
    assert set(t.name for t in f.graph) == set(t.name for t in f2.graph)
    assert f2.graph[f2.get_task('t2')] == set([f2.get_task('t1')])


def test_save():
    name = 'test-save-flow'
    with Flow(name) as f:
        t1 = prefect.task.Task(fn=lambda: 1, name='t1')
        t2 = prefect.task.Task(fn=lambda: 1, name='t2')
        t1.run_before(t2)
    model = f.save()
    c = mongoengine.connection.get_connection()
    collection = c[prefect.config.get('mongo', 'db')][model._collection.name]
    assert collection.find_one(f.id)['name'] == name

    new_name = 'new name'
    f.name = new_name
    f.save()
    assert collection.find_one(f.id)['name'] == new_name
