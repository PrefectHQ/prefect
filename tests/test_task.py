import copy
import datetime
import prefect
from prefect.signals import PrefectError
from prefect.flow import Flow
from prefect.task import Task, TaskResult, task, retry_delay
import pytest


class TestTask:

    def test_create_task(self):
        """Test task creation"""

        # tasks require a name
        with pytest.raises(ValueError) as e:
            t1 = Task()

        # ...unless created inside a Flow
        with Flow('test'):
            t2 = Task()
        assert t2.name == 'Task'

        t3 = Task(name='test')
        assert t3.name == 'test'

    def test_task_decorator(self):
        """ Test task decorator"""

        @task
        def fn():
            raise ValueError('expected error')

        t = fn()
        with pytest.raises(ValueError):
            t.run()


    def test_task_names(self):
        """
        Test auto-assignment of Task names
        """

        @task
        def myfn():
            pass

        class MyTask(Task):
            pass

        with Flow('test') as flow:
            t1 = Task()
            t2 = Task()
            t3 = myfn()
            t4 = MyTask()
            t5 = MyTask()
            t6 = Task(name='hi')

        assert t1.name == 'Task'
        assert t2.name == 'Task-2'
        assert t3.name == 'myfn'
        assert t4.name == 'MyTask'
        assert t5.name == 'MyTask-2'
        assert t6.name == 'hi'

    def test_task_equality(self):
        """
        Task equality holds if task ids match.
        """
        with Flow('1') as f:
            t1 = Task()

        f2 = copy.deepcopy(f)
        assert f.get_task('Task') is not f2.get_task('Task')
        assert f.get_task('Task') == f2.get_task('Task')


    def test_flow_context_manager(self):
        """Tests that flows can be used as context managers"""

        with Flow('test_flow') as f:
            t = Task(name='t1')

            # nested context manager
            with Flow('test_flow_2') as f2:

                t2 = Task(name='t2')

            # return to original context manager
            t3 = Task(name='t3')

        assert t in f

        assert t2 in f2
        assert t2 not in f

        assert t3 in f


class TestRetryDelay:

    def test_retry_delay_errors(self):
        with pytest.raises(ValueError):
            prefect.tasks.retry_delay()

        with pytest.raises(ValueError):
            prefect.tasks.retry_delay(datetime.timedelta(days=1), minutes=1)

    def test_retry_delay_args(self):
        delay_passed = prefect.tasks.retry_delay(datetime.timedelta(seconds=1))
        delay_constructed = prefect.tasks.retry_delay(seconds=1)

        assert delay_passed(1) == delay_constructed(1)
        assert delay_passed(2) == delay_constructed(2)

    def test_constant_retry_delay(self):
        delay = prefect.tasks.retry_delay(seconds=1)
        assert delay(1) == delay(2) == datetime.timedelta(seconds=1)

    def test_exponential_retry_delay(self):
        delay = prefect.tasks.retry_delay(seconds=1, exponential_backoff=True)
        assert delay(1) == delay(2) == datetime.timedelta(seconds=1)
        assert delay(3) == datetime.timedelta(seconds=2)
        assert delay(4) == datetime.timedelta(seconds=4)

        # test max value
        delay = prefect.tasks.retry_delay(days=1, exponential_backoff=True)
        assert delay(10) == datetime.timedelta(hours=2)
        delay = prefect.tasks.retry_delay(
            days=1,
            exponential_backoff=True,
            max_delay=datetime.timedelta(days=10))
        assert delay(10) == datetime.timedelta(days=10)


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


class TestTaskResult:

    def test_getitem(self):
        with Flow('test') as f:
            t1 = Task()
        assert isinstance(t1['a'], TaskResult)
        assert t1['a'].task is t1 and t1['a'].index == 'a'
