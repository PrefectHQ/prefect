import mongoengine
import pytest
from prefect.exceptions import PrefectError
import prefect
from prefect.models import FlowModel
from prefect.flow import Flow, Graph
from prefect.task import Task


def fn():
    """ a test function for tasks"""
    pass


class TestGraph:

    def test_add_nodes(self):
        g = Graph()
        for i in range(3):
            g.add_node(i)
            assert i in g
        assert g.nodes == set(range(3))

        # re-add node
        g.add_node(0)

    def test_add_edge(self):
        g = Graph()
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(0, 2)
        assert g.nodes == set(range(3))
        assert g.edges_to(2) == set([0, 1])
        assert g.edges_from(0) == set([1, 2])

        # re-add edge
        g.add_edge(0, 1)

    def test_sort_nodes(self):
        g = Graph()
        g.add_edge(9, 5)
        g.add_edge(5, 3)
        g.add_edge(3, 1)
        g.add_edge(5, 1)
        assert g.sort_nodes() == (9, 5, 3, 1)

    def test_add_cycle(self):
        g = Graph()
        with pytest.raises(ValueError):
            g.add_edge(0, 0)

        with pytest.raises(ValueError):
            g.add_edge(0, 1)
            g.add_edge(1, 0)

        with pytest.raises(ValueError):
            g.add_edge(0, 1)
            g.add_edge(1, 2)
            g.add_edge(3, 2)
            g.add_edge(3, 1)


class TestBasics:

    def test_create_flow(self):
        # name is required
        with pytest.raises(TypeError) as e:
            Flow()
        err = "__init__() missing 1 required positional argument: 'name'"
        assert err in str(e)

        f = Flow('test')

    def test_add_task(self):
        f = Flow('test')
        f2 = Flow('test-2')
        with pytest.raises(TypeError):
            f.add_task(1)

        # can't add task from another flow
        t2 = Task(fn=fn, name='t2', flow=f2)
        with pytest.raises(ValueError):
            f.add_task(t2)

        # can't add task already in the flow
        t3 = Task(fn=fn, name='t3', flow=f)
        with pytest.raises(ValueError):
            f.add_task(t3)

    def test_context_manager(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')

        assert t1.flow is f
        assert t1 in f

    def test_iter(self):
        """
        Tests that iterating over a Flow yields the tasks in order
        """
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_after(t2)
        assert tuple(f) == f.sort_tasks() == (t2, t1)

    def test_relationship(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_after(t2)
        assert f.upstream_tasks(t1) == set([t2])
        assert f.upstream_tasks(t2) == set()
        assert f.downstream_tasks(t1) == set()
        assert f.downstream_tasks(t2) == set([t1])

    def test_get_task_by_name(self):
        """
        Tests flow.get_task()
        """
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_before(t2)

        assert f.get_task('t1') is t1
        with pytest.raises(PrefectError):
            f.get_task('some task')


class TestPersistence:

    def test_serialize(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_before(t2)

        serialized = f.serialize()
        f2 = Flow.from_serialized(serialized)
        assert isinstance(f2, Flow)
        assert [t.name for t in f] == [t.name for t in f2]


    def test_save(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_before(t2)
        assert len(list(FlowModel)) == 0
        f.save()
        assert len(list(FlowModel)) == 1

    def test_reload(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_before(t2)
        f.active = False
        f.reload()
        assert f.active


    def test_from_name(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t1.run_before(t2)
        f.save()
        f2 = Flow.from_name(namespace=f.namespace, name=f.name, version=f.version)
        assert f2.id == f.id


class TestSugar:
    def test_task_decorator(self):
        with Flow('test') as f:
            @f.task
            def t1(**k):
                return 1

        @f.task(name='test_name')
        def t2(**k):
            return 2

        t1.run_before(t2)

        assert isinstance(t1, Task)
        assert t1.name == 't1'
        assert isinstance(t2, Task)
        assert t2.name == 'test_name'
