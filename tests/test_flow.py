import peewee
from prefect.exceptions import PrefectError
import prefect
from prefect.models import FlowModel, TaskModel
from prefect.flow import Flow
from prefect.task import Task
from prefect.edges import Edge, Pipe
import pytest
import uuid


def fn():
    """ a test function for tasks"""
    pass

class TestFlow:

    def test_create_flow(self):
        # name is required
        with pytest.raises(TypeError) as e:
            Flow()
        err = "__init__() missing 1 required positional argument: 'name'"
        assert err in str(e)

        f = Flow('test')
        assert f.namespace == prefect.config.get('flows', 'default_namespace')
        assert f.name == 'test'
        assert f.version == prefect.config.get('flows', 'default_version')

    def test_add_task(self):
        f = Flow('test')
        f2 = Flow('test-2')
        with pytest.raises(TypeError):
            f.add_task(1)

        # can't add task from another flow
        t2 = Task(flow=f2)
        with pytest.raises(ValueError):
            f.add_task(t2)

        # can't add task already in the flow
        t3 = Task(flow=f)
        with pytest.raises(ValueError):
            f.add_task(t3)

    def test_context_manager(self):
        with Flow('test') as f:
            t1 = Task()

        assert t1.flow is f
        assert t1 in f

    def test_iter(self):
        """
        Tests that iterating over a Flow yields the tasks in order
        """
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(Edge(upstream_task=t1, downstream_task=t2))
        assert tuple(f) == f.sort_tasks() == (t1, t2)

    def test_edge(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(Edge(upstream_task=t1, downstream_task=t2))
        assert f.upstream_tasks(t2) == set([t1])
        assert f.upstream_tasks(t1) == set()
        assert f.downstream_tasks(t2) == set()
        assert f.downstream_tasks(t1) == set([t2])

    def test_pipes(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(Edge(upstream_task=t1, downstream_task=t2))
        assert f.upstream_tasks(t2) == set([t1])
        assert f.upstream_tasks(t1) == set()
        assert f.downstream_tasks(t2) == set()
        assert f.downstream_tasks(t1) == set([t2])

    def test_get_task_by_name(self):
        """
        Tests flow.get_task()
        """
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(Edge(upstream_task=t1, downstream_task=t2))

        assert f.get_task('Task-1') is t1
        with pytest.raises(PrefectError):
            f.get_task('some task')

    def test_detect_cycle(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            t3 = Task()

        t1.then(t2).then(t3)

        with pytest.raises(ValueError) as e:
            t3.run_before(t1)

class TestPersistence:

    def test_serialize(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)

        serialized = prefect.utilities.serialize.serialize(f, encryption_key='abc')
        f2 = prefect.utilities.serialize.deserialize(serialized, decryption_key='abc')
        assert isinstance(f2, Flow)
        assert set(f) == set(f2)


    def test_save(self):
        with Flow(uuid.uuid4().hex) as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)
        assert len(list(FlowModel)) == 0
        f.save()
        assert len(list(FlowModel)) == 1

    def test_flow_id(self):
        with Flow(uuid.uuid4().hex) as f:
            t1 = Task()
        with pytest.raises(PrefectError):
            f.id
        f.save()
        assert f.id > 0

    def test_reload(self):
        with Flow(uuid.uuid4().hex) as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)
        f.save()
        f.active = False
        f.reload()
        assert f.active

    def test_from_id(self):
        with Flow(uuid.uuid4().hex) as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)
        f.save()

        f2 = Flow.from_id(f.id)
        assert f2.id == f.id

    def test_delete(self):
        with Flow(uuid.uuid4().hex) as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)
        f.save()

        TaskModel.get(id=t1.id)
        f.delete(confirm=True)
        with pytest.raises(peewee.DoesNotExist):
            TaskModel.get(id=t1.id)

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
        assert t1.name == 't1-1'
        assert isinstance(t2, Task)
        assert t2.name == 'test_name'
