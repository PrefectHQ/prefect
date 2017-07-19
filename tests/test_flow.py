import datetime
from prefect.signals import PrefectError
import prefect
from prefect.flow import Flow
from prefect.task import Task
import pytest
import ujson


class TestFlow:

    def test_create_flow(self):
        # name is required
        with pytest.raises(TypeError) as e:
            Flow()
        err = "__init__() missing 1 required positional argument: 'name'"
        assert err in str(e)

        f = Flow('test', version='3')
        assert f.project == prefect.config.get('flows', 'default_project')
        assert f.name == 'test'
        assert f.version == '3'

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
            f.add_edge(upstream_task=t1, downstream_task=t2)
        assert tuple(f) == f.sort_tasks() == (t1, t2)

    def test_edge(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(upstream_task=t1, downstream_task=t2)
        assert f.upstream_tasks(t2) == set([t1])
        assert f.upstream_tasks(t1) == set()
        assert f.downstream_tasks(t2) == set()
        assert f.downstream_tasks(t1) == set([t2])
        assert f.edges_to(t2) == f.edges_from(t1)

    def test_pipes(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(upstream_task=t1, downstream_task=t2)
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
            f.add_edge(upstream_task=t1, downstream_task=t2)

        assert f.get_task('Task_1') is t1
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

    @pytest.fixture
    def flow(self):
        with Flow(
                'test',
                schedule=prefect.schedules.IntervalSchedule(
                    start_date=datetime.datetime(2017, 1, 1),
                    interval=datetime.timedelta(days=1))) as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)
        return f

    def test_serialize_deserialize_flow(self, flow):
        f2 = Flow.deserialize(flow.serialize())
        assert f2.id == flow.id
        assert [t.id for t in flow] == [t.id for t in f2]

    def test_access_schedule_from_serialized(self, flow):
        s = flow.serialize()
        schedule = prefect.utilities.serialize.deserialize(
            ujson.loads(s)['schedule'])
        next_date = schedule.next_n(
            on_or_after=datetime.datetime(2017, 1, 1, 1))[0]
        assert next_date == datetime.datetime(2017, 1, 2)

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
        assert t1.name == 't1_1'
        assert isinstance(t2, Task)
        assert t2.name == 'test_name'
