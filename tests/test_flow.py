import datetime

import pytest

import prefect
import ujson
from prefect.flow import Flow
from prefect.signals import PrefectError
from prefect.tasks import Task, FunctionTask, as_task_class
from prefect.utilities.tests import DummyTask


class TestFlow:

    def test_create_flow(self):
        # name is required
        with pytest.raises(TypeError) as e:
            Flow()
        err = "__init__() missing 1 required positional argument: 'name'"
        assert err in str(e)

        f = Flow('test')
        assert f.project == prefect.config.get('flows', 'default_project')
        assert f.name == 'test'

    def test_add_task(self):
        f = Flow('test')
        f2 = Flow('test-2')
        with pytest.raises(TypeError):
            f.add_task(1)

        # can't add task already in the flow
        t3 = Task(flow=f)
        with pytest.raises(ValueError):
            f.add_task(t3)

    def test_context_manager(self):
        with Flow('test') as f:
            t1 = Task()

        assert t1 in f

    def test_iter(self):
        """
        Tests that iterating over a Flow yields the tasks in order
        """
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            f.add_edge(upstream_task=t1, downstream_task=t2)
        assert tuple(f) == f.sorted_tasks() == (t1, t2)

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

    def test_get_task_by_name(self):
        """
        Tests flow.get_task()
        """
        with Flow('test') as f:
            t1 = Task(name='Task_1')
            t2 = Task()
            f.add_edge(upstream_task=t1, downstream_task=t2)

        assert f.get_task('Task_1') is t1
        with pytest.raises(ValueError):
            f.get_task('some task')

    def test_detect_cycle(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()
            t3 = Task()

            t1.set(run_before=t2)
            t2.set(run_before=t3)

            with pytest.raises(ValueError) as e:
                t3.set(run_before=t1)

    def test_run(self):
        """
        Test the flow's run() method
        """
        with Flow('test') as f:
            t1 = FunctionTask(fn=lambda: 1, name='my-task')

        assert f.run().result['my-task'].result == 1

    def test_constant(self):
        """
        Test that Flows properly wrap constant values
        """
        with Flow('test') as f:
            t1 = FunctionTask(fn=lambda x: x + 1, name='my-task')
            t1.run_after(x=5)

        # check that a Constant was added
        assert len(f.tasks) == 2

        assert f.run().result['my-task'].result == 6

    def test_terminal_tasks(self):
        with Flow('test') as f:
            t1 = DummyTask()
            t2 = DummyTask()
            t3 = DummyTask()

            t1.set(run_before=t2)
            t2.set(run_before=t3)

        assert f.terminal_tasks() == set([t3])

class TestPersistence:

    @pytest.fixture
    def flow(self):
        with Flow('test', schedule=prefect.schedules.IntervalSchedule(
                start_date=datetime.datetime(2017, 1, 1),
                interval=datetime.timedelta(days=1))) as f:
            t1 = Task()
            t2 = Task()
            t1.run_before(t2)
        return f

    def test_serialize_deserialize_flow(self, flow):
        f2 = Flow.deserialize(flow.serialize())
        assert [t for t in flow] == [t for t in f2]

    def test_access_schedule_from_serialized(self, flow):
        s = flow.serialize()
        schedule = prefect.schedules.deserialize(s['schedule'])
        next_date = schedule.next_n(
            on_or_after=datetime.datetime(2017, 1, 1, 1))[0]
        assert next_date == datetime.datetime(2017, 1, 2)


class TestSugar:

    def test_task_decorator(self):

        @as_task_class
        def T1(**k):
            return 1

        @as_task_class(name='test_name')
        def T2(**k):
            return 2

        with Flow('test') as f:
            t1 = T1()
            t2 = T2()

            t1.run_before(t2)

        assert isinstance(t1, Task)
        assert t1.name == 'T1'
        assert isinstance(t2, Task)
        assert t2.name == 'test_name'
