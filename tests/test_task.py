import copy
import pendulum
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
        assert t.flow.id == f.id

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

            # tasks must be valid identifiers
            with pytest.raises(ValueError):
                Task('1two')
            with pytest.raises(ValueError):
                Task('while')

        assert t1.name == 'Task_1'
        assert t2.name == 'Task_2'
        assert t3.name == 'myfn_1'
        assert t4.name == 'MyTask_1'
        assert t5.name == 'hi'

    def test_task_equality(self):
        """
        Task equality holds if task ids match.
        """
        with Flow('1') as f:
            t1 = Task()

        f2 = copy.deepcopy(f)
        assert f.get_task('Task_1') is not f2.get_task('Task_1')
        assert f.get_task('Task_1') == f2.get_task('Task_1')

    def test_task_comparisons(self):
        """
        Comparisons are based on flow order, with ties broken by task id.
        """
        with Flow('1') as f:
            t1 = Task()
            t2 = Task()

        assert t1 < t2
        assert t2 > t1
        t2.run_before(t1)
        assert t2 < t1
        assert t1 > t2

    def test_flow_context_manager(self):
        """Tests that flows can be used as context managers"""

        with Flow('test_flow') as f:
            t = Task(name='test')

            # nested context manager
            with Flow('test_flow_2') as f2:
                t2 = Task(name='test')

            # return to original context manager
            t3 = Task(name='test1')

            assert t.flow.id == f.id
            assert t in f

            assert t2.flow.id == f2.id
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


class TestRetryDelay:

    def test_retry_delay_errors(self):
        with pytest.raises(ValueError):
            prefect.task.retry_delay()

        with pytest.raises(ValueError):
            prefect.task.retry_delay(pendulum.interval(days=1), minutes=1)

    def test_retry_delay_args(self):
        delay_passed = prefect.task.retry_delay(pendulum.interval(seconds=1))
        delay_constructed = prefect.task.retry_delay(seconds=1)

        assert delay_passed(1) == delay_constructed(1)
        assert delay_passed(2) == delay_constructed(2)

    def test_constant_retry_delay(self):
        delay = prefect.task.retry_delay(seconds=1)
        assert delay(1) == delay(2) == pendulum.interval(seconds=1)

    def test_exponential_retry_delay(self):
        delay = prefect.task.retry_delay(seconds=1, exponential_backoff=True)
        assert delay(1) == delay(2) == pendulum.interval(seconds=1)
        assert delay(3) == pendulum.interval(seconds=2)
        assert delay(4) == pendulum.interval(seconds=4)

        # test max value
        delay = prefect.task.retry_delay(days=1, exponential_backoff=True)
        assert delay(10) == pendulum.interval(hours=2)
        delay = prefect.task.retry_delay(
            days=1,
            exponential_backoff=True,
            max_delay=pendulum.interval(days=10))
        assert delay(10) == pendulum.interval(days=10)


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

    def test_create_pipe(self):
        with Flow('test') as f:
            t1 = Task()
            t2 = Task()

        t2.add_pipes(x=t1)
        assert t1 in f.upstream_tasks(t2)
        assert isinstance(list(f.edges)[0], prefect.edges.Pipe)
