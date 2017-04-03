import copy
import prefect
from prefect.exceptions import PrefectError
from prefect.flow import Flow
from prefect.task import Task, TaskResult
import pytest


class TestBasics:

    def test_create_task(self):
        """Test task creation"""

        # tasks require Flows
        with pytest.raises(ValueError) as e:
            t = Task()

        f = Flow('test_flow')
        t = Task(name='test', flow=f)
        assert t.flow_id == f.flow_id

    def test_task_names(self):
        """
        Test auto-assignment of Task names
        """

        def myfn():
            pass

        class MyTask(Task):
            pass

        with Flow('test') as flow:
            t1 = Task()
            t2 = Task()
            t3 = Task(fn=myfn)
            t4 = MyTask()
            t5 = Task('hi')

        assert t1.name == 'Task-1'
        assert t2.name == 'Task-2'
        assert t3.name == 'myfn-1'
        assert t4.name == 'MyTask-1'
        assert t5.name == 'hi'

    def test_task_equality(self):
        """
        Task equality holds if task ids match.
        """
        with Flow('1') as f:
            t1 = Task()

        f2 = copy.deepcopy(f)
        assert f.get_task('Task-1') is not f2.get_task('Task-1')
        assert f.get_task('Task-1') == f2.get_task('Task-1')

    def test_flow_context_manager(self):
        """Tests that flows can be used as context managers"""

        with Flow('test_flow') as f:
            t = Task(name='test')

            # nested context manager
            with Flow('test_flow_2') as f2:
                t2 = Task(name='test')

            # return to original context manager
            t3 = Task(name='test1')

            assert t.flow_id == f.flow_id
            assert t in f

            assert t2.flow_id == f2.flow_id
            assert t2 in f2
            assert t2 not in f

            assert t3.flow is f
            assert t3 in f

    def test_add_task_to_flow_after_flow_assigned(self):
        with Flow('test_flow') as f:
            t = Task(name='test')

        with pytest.raises(ValueError) as e:
            t2 = Task(name='test', flow=f)
        assert 'already exists in this Flow' in str(e)

        with pytest.raises(ValueError) as e:
            f2 = Flow('test_flow_2')
            f2.add_task(t)
        assert 'already in another Flow' in str(e)

    def test_task_equality(self):
        with Flow('test') as f:
            t = Task(name='test')


class TestTaskRelationships:

    def test_task_relationships(self):
        """Test task relationships"""
        with Flow('test') as f:
            before = Task(name='before')
            after = Task(name='after')

        before.run_before(after)
        assert before in f
        assert after in f
        assert before in f.upstream_tasks(after)

        # same test, calling `run_after`
        with Flow('test') as f:
            before = Task(name='before')
            before2 = Task(name='before_2')
            after = Task(name='after')

        after.run_after([before, before2])
        assert before in f
        assert before2 in f
        assert after in f
        assert before in f.upstream_tasks(after)
        assert before2 in f.upstream_tasks(after)

    def test_shift_relationship_sugar(self):
        """Test task relationships with | and >> and << sugar"""
        with Flow('test') as f:
            before = Task()
            mid1 = Task()
            mid2 = Task()
            after = Task()

        (before | (mid1, mid2) | after)
        assert before in f
        assert mid1 in f
        assert mid2 in f
        assert after in f
        assert set([mid1, mid2]) == f.downstream_tasks(before)
        assert set([mid1, mid2]) == f.upstream_tasks(after)

        with Flow('test') as f:
            before = Task()
            mid1 = Task()
            mid2 = Task()
            after = Task()

        before >> (mid1, mid2) >> after
        assert before in f
        assert mid1 in f
        assert mid2 in f
        assert after in f
        assert set([mid1, mid2]) == f.downstream_tasks(before)
        assert set([mid1, mid2]) == f.upstream_tasks(after)

        # same test, calling `run_after`
        with Flow('test') as f:
            before = Task()
            mid1 = Task()
            mid2 = Task()
            after = Task()

        after << (mid1, mid2) << before
        assert before in f
        assert mid1 in f
        assert mid2 in f
        assert after in f
        assert set([mid1, mid2]) == f.downstream_tasks(before)
        assert set([mid1, mid2]) == f.upstream_tasks(after)

    def test_save(self):
        name = 'test-save-task'
        with Flow(name) as f:
            t1 = Task()
        with pytest.raises(PrefectError):
            t1.save()
        f.save()
        t1.save()
        assert t1.id is not None


class TestTaskResult:

    def test_getitem(self):
        with Flow('test') as f:
            t1 = Task()
        assert isinstance(t1['a'], TaskResult)
        assert t1['a'].task is t1 and t1['a'].index == 'a'

    def test_create_pipe(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()

        t2.add_pipes(x=t1)
        assert t1 in f.upstream_tasks(t2)
        assert isinstance(list(f.edges)[0], prefect.edges.Pipe)
