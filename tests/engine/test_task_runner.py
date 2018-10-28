import collections
from datetime import datetime, timedelta
from time import sleep

import pytest

from unittest.mock import MagicMock

import prefect
from prefect.client import Secret
from prefect.core.edge import Edge
from prefect.core.task import Task
from prefect.engine import signals, cache_validators
from prefect.engine.task_runner import TaskRunner, ENDRUN
from prefect.engine.cache_validators import (
    all_inputs,
    all_parameters,
    duration_only,
    never_use,
    partial_inputs_only,
    partial_parameters_only,
)
from prefect.engine.state import (
    CachedState,
    Failed,
    Finished,
    Mapped,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TriggerFailed,
)
from prefect.utilities.tests import raise_on_exception


class SuccessTask(Task):
    def run(self):
        return 1


class ErrorTask(Task):
    def run(self):
        raise ValueError("custom-error-message")


class RaiseFailTask(Task):
    def run(self):
        raise prefect.engine.signals.FAIL("custom-fail-message")
        raise ValueError("custom-error-message")  # pylint: disable=W0101


class RaiseSkipTask(Task):
    def run(self):
        raise prefect.engine.signals.SKIP()
        raise ValueError()  # pylint: disable=W0101


class RaiseSuccessTask(Task):
    def run(self):
        raise prefect.engine.signals.SUCCESS()
        raise ValueError()  # pylint: disable=W0101


class RaiseRetryTask(Task):
    def run(self):
        raise prefect.engine.signals.RETRY()
        raise ValueError()  # pylint: disable=W0101


class AddTask(Task):
    def run(self, x, y):
        return x + y


class ListTask(Task):
    def run(self):
        return [1, 2, 3]


class SlowTask(Task):
    def run(self, secs):
        sleep(secs)


class SecretTask(Task):
    def run(self):
        s = Secret("testing")
        return s.get()


def test_task_runner_has_logger():
    r = TaskRunner(Task())
    assert r.logger.name == "prefect.TaskRunner"


def test_task_that_succeeds_is_marked_success():
    """
    Test running a task that finishes successfully and returns a result
    """
    task_runner = TaskRunner(task=SuccessTask())
    assert isinstance(task_runner.run(), Success)


def test_task_that_raises_success_is_marked_success():
    task_runner = TaskRunner(task=RaiseSuccessTask())
    assert isinstance(task_runner.run(), Success)


def test_task_that_has_an_error_is_marked_fail():
    task_runner = TaskRunner(task=ErrorTask())
    assert isinstance(task_runner.run(), Failed)


def test_task_that_raises_fail_is_marked_fail():
    task_runner = TaskRunner(task=RaiseFailTask())
    assert isinstance(task_runner.run(), Failed)
    assert not isinstance(task_runner.run(), TriggerFailed)


def test_task_that_fails_gets_retried_up_to_max_retry_time():
    """
    Test that failed tasks are marked for retry if run_count is available
    """
    err_task = ErrorTask(max_retries=2, retry_delay=timedelta(0))
    task_runner = TaskRunner(task=err_task)

    # first run should be retry
    state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.start_time, datetime)
    assert state.run_count == 1

    # second run should retry
    state = task_runner.run(state=state)
    assert isinstance(state, Retrying)
    assert isinstance(state.start_time, datetime)
    assert state.run_count == 2

    # second run should fail
    state = task_runner.run(state=state)
    assert isinstance(state, Failed)


def test_task_that_raises_retry_has_start_time_recognized():
    now = datetime.utcnow()

    class RetryNow(Task):
        def run(self):
            raise signals.RETRY()

    class Retry5Min(Task):
        def run(self):
            raise signals.RETRY(start_time=now + timedelta(minutes=5))

    state = TaskRunner(task=RetryNow()).run()
    assert isinstance(state, Retrying)
    assert now - state.start_time < timedelta(seconds=0.1)

    state = TaskRunner(task=Retry5Min()).run()
    assert isinstance(state, Retrying)
    assert state.start_time == now + timedelta(minutes=5)


def test_task_that_raises_retry_gets_retried_even_if_max_retries_is_set():
    """
    Test that tasks that raise a retry signal get retried even if they exceed max_retries
    """
    retry_task = RaiseRetryTask(max_retries=1, retry_delay=timedelta(0))
    task_runner = TaskRunner(task=retry_task)

    # first run should be retrying
    with prefect.context(_task_run_count=1):
        state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.start_time, datetime)

    # second run should also be retry because the task raises it explicitly

    with prefect.context(_task_run_count=2):
        state = task_runner.run(state=state)
    assert isinstance(state, Retrying)


def test_task_that_raises_skip_gets_skipped():
    task_runner = TaskRunner(task=RaiseSkipTask())
    assert isinstance(task_runner.run(), Skipped)


def test_task_that_has_upstream_skip_gets_skipped_with_informative_message():
    task_runner = TaskRunner(task=SuccessTask())
    edge = Edge(RaiseSkipTask(), SuccessTask(skip_on_upstream_skip=True))
    state = task_runner.run(upstream_states={edge: Skipped()})
    assert isinstance(state, Skipped)
    assert "skip_on_upstream_skip" in state.message


def test_task_that_is_running_doesnt_run():
    task_runner = TaskRunner(task=SuccessTask())
    initial_state = Running()
    assert task_runner.run(state=initial_state) is initial_state


def test_running_task_that_already_has_finished_state_doesnt_run():
    task_runner = TaskRunner(task=ErrorTask())

    # pending tasks get run (and fail)
    assert isinstance(task_runner.run(state=Pending()), Failed)

    # finished tasks don't run (just return same state)
    assert isinstance(task_runner.run(state=Success()), Success)
    assert isinstance(task_runner.run(state=Failed()), Failed)
    assert isinstance(task_runner.run(state=Skipped()), Skipped)


def test_task_runner_preserves_error_type():
    task_runner = TaskRunner(ErrorTask())
    state = task_runner.run()
    exc = state.result
    if isinstance(exc, Exception):
        assert type(exc).__name__ == "ValueError"
    else:
        assert "ValueError" in exc


def test_task_runner_raise_on_exception_when_task_errors():
    with raise_on_exception():
        with pytest.raises(ValueError):
            TaskRunner(ErrorTask()).run()


def test_task_runner_raise_on_exception_when_task_signals():
    with raise_on_exception():
        with pytest.raises(prefect.engine.signals.FAIL):
            TaskRunner(RaiseFailTask()).run()


def test_throttled_task_runner_takes_ticket_and_puts_it_back():
    q = MagicMock()
    q.get = lambda *args, **kwargs: "ticket"
    runner = TaskRunner(SuccessTask(tags=["db"]))
    state = runner.run(queues=[q])
    assert q.put.called
    assert q.put.call_args[0][0] == "ticket"


def test_throttled_task_runner_returns_ticket_even_with_error():
    q = MagicMock()
    q.get = lambda *args, **kwargs: "ticket"
    runner = TaskRunner(ErrorTask(tags=["db"]))
    state = runner.run(queues=[q])
    assert q.put.called
    assert q.put.call_args[0][0] == "ticket"


def test_task_runner_returns_tickets_to_the_right_place():
    class BadQueue:
        def __init__(self, *args, **kwargs):
            self.called = 0

        def get(self, *args, **kwargs):
            if self.called <= 2:
                self.called += 1
                raise Exception
            else:
                return "bad_ticket"

    bq = BadQueue()
    bq.put = MagicMock()
    q = MagicMock()
    q.get = lambda *args, **kwargs: "ticket"
    runner = TaskRunner(SuccessTask())
    state = runner.run(queues=[q, bq])
    assert bq.put.call_count == 1
    assert bq.put.call_args[0][0] == "bad_ticket"
    assert all([args[0][0] == "ticket" for args in q.put.call_args_list])


def test_task_runner_accepts_dictionary_of_edges():
    add = AddTask()
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(SuccessTask(), add, key="y")
    runner = TaskRunner(add)
    state = runner.run(upstream_states={ex: Success(result=1), ey: Success(result=1)})
    assert state.is_successful()
    assert state.result == 2


def test_task_runner_prioritizes_inputs():
    add = AddTask()
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(SuccessTask(), add, key="y")
    runner = TaskRunner(add)
    state = runner.run(
        upstream_states={ex: Success(result=1), ey: Success(result=1)},
        inputs=dict(x=10, y=20),
    )
    assert state.is_successful()
    assert state.result == 30


def test_task_runner_can_handle_timeouts_by_default():
    sleeper = SlowTask(timeout=timedelta(seconds=1))
    state = TaskRunner(sleeper).run(inputs=dict(secs=2))
    assert state.is_failed()
    assert "timed out" in state.message
    assert isinstance(state.result, TimeoutError)


def test_task_runner_handles_secrets():
    t = SecretTask()
    state = TaskRunner(t).run(context=dict(_secrets=dict(testing="my_private_str")))
    assert state.is_successful()
    assert state.result is "my_private_str"


def test_task_that_starts_failed_doesnt_get_retried():
    state = TaskRunner(Task()).run(state=Failed())
    assert state.is_failed()


class TestGetRunCount:
    @pytest.mark.parametrize(
        "state", [Success(), Failed(), Pending(), Scheduled(), Skipped(), CachedState()]
    )
    def test_states_without_run_count(self, state):
        with prefect.context() as ctx:
            assert "_task_run_count" not in ctx
            new_state = TaskRunner(Task()).get_run_count(state)
            assert ctx._task_run_count == 1
            assert new_state is state

    @pytest.mark.parametrize(
        "state",
        [
            Retrying(),
            Retrying(run_count=1),
            Retrying(run_count=2),
            Retrying(run_count=10),
        ],
    )
    def test_states_with_run_count(self, state):
        with prefect.context() as ctx:
            assert "_task_run_count" not in ctx
            new_state = TaskRunner(Task()).get_run_count(state)
            assert ctx._task_run_count == state.run_count + 1
            assert new_state is state


class TestCheckUpstreamFinished:
    def test_with_empty_set(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_finished(
            state=state, upstream_states_set=set()
        )
        assert new_state is state

    def test_with_two_finished(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_finished(
            state=state, upstream_states_set={Success(), Failed()}
        )
        assert new_state is state

    def test_raises_with_one_unfinished(self):
        state = Pending()
        with pytest.raises(ENDRUN):
            TaskRunner(Task()).check_upstream_finished(
                state=state, upstream_states_set={Success(), Running()}
            )


class TestCheckUpstreamSkipped:
    def test_empty_set(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_skipped(
            state=state, upstream_states_set=set()
        )
        assert new_state is state

    def test_unskipped_states(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_skipped(
            state=state, upstream_states_set={Success(), Failed()}
        )
        assert new_state is state

    def test_raises_with_skipped(self):
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(Task()).check_upstream_skipped(
                state=state, upstream_states_set={Skipped()}
            )
        assert isinstance(exc.value.state, Skipped)

    def test_doesnt_raise_with_skipped_and_flag_set(self):
        state = Pending()
        task = Task(skip_on_upstream_skip=False)
        new_state = TaskRunner(task).check_upstream_skipped(
            state=state, upstream_states_set={Skipped()}
        )
        assert new_state is state


class TestCheckTaskTrigger:
    def test_ignore_trigger(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={Success(), Failed()}, ignore_trigger=True
        )
        assert new_state is state

    def test_all_successful_pass(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={Success(), Success()}
        )
        assert new_state is state

    def test_all_successful_fail(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Success(), Failed()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "all_successful"' in str(exc.value.state)

    def test_all_successful_empty_set(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={}
        )
        assert new_state is state

    def test_all_failed_pass(self):
        task = Task(trigger=prefect.triggers.all_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={Failed(), Failed()}
        )
        assert new_state is state

    def test_all_failed_fail(self):
        task = Task(trigger=prefect.triggers.all_failed)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Success(), Failed()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "all_failed"' in str(exc.value.state)

    def test_all_failed_empty_set(self):
        task = Task(trigger=prefect.triggers.all_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={}
        )
        assert new_state is state

    def test_any_successful_pass(self):
        task = Task(trigger=prefect.triggers.any_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={Success(), Failed()}
        )
        assert new_state is state

    def test_any_successful_fail(self):
        task = Task(trigger=prefect.triggers.any_successful)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Failed(), Failed()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "any_successful"' in str(exc.value.state)

    def test_any_successful_empty_set(self):
        task = Task(trigger=prefect.triggers.any_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={}
        )
        assert new_state is state

    def test_any_failed_pass(self):
        task = Task(trigger=prefect.triggers.any_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={Success(), Failed()}
        )
        assert new_state is state

    def test_any_failed_fail(self):
        task = Task(trigger=prefect.triggers.any_failed)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Success(), Success()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "any_failed"' in str(exc.value.state)

    def test_any_failed_empty_set(self):
        task = Task(trigger=prefect.triggers.any_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={}
        )
        assert new_state is state

    def test_all_finished_pass(self):
        task = Task(trigger=prefect.triggers.all_finished)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={Success(), Failed()}
        )
        assert new_state is state

    def test_all_finished_fail(self):
        task = Task(trigger=prefect.triggers.all_finished)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Success(), Pending()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "all_finished"' in str(exc.value.state)

    def test_all_finished_empty_set(self):
        task = Task(trigger=prefect.triggers.all_finished)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={}
        )
        assert new_state is state

    def test_manual_only(self):
        task = Task(trigger=prefect.triggers.manual_only)
        state = Pending()
        with pytest.raises(signals.PAUSE) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Success(), Pending()}
            )

    def test_manual_only_empty_set(self):
        task = Task(trigger=prefect.triggers.manual_only)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states_set={}
        )
        assert new_state is state

    def test_custom_trigger_function_raise(self):
        def trigger(states):
            1 / 0

        task = Task(trigger=trigger)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states_set={Success()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert isinstance(exc.value.state.result, ZeroDivisionError)


class TestCheckTaskPending:
    @pytest.mark.parametrize("state", [Pending(), CachedState()])
    def test_pending(self, state):
        new_state = TaskRunner(task=Task()).check_task_is_pending(state=state)
        assert new_state is state

    @pytest.mark.parametrize(
        "state", [Running(), Finished(), TriggerFailed(), Skipped()]
    )
    def test_not_pending(self, state):

        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task=Task()).check_task_is_pending(state=state)
        assert exc.value.state is state


class TestCheckTaskCached:
    def test_not_cached(self):
        state = Pending()
        new_state = TaskRunner(task=Task()).check_task_is_cached(state=state, inputs={})
        assert new_state is state

    def test_cached_same_inputs(self):
        task = Task(cache_validator=cache_validators.all_inputs)
        state = CachedState(cached_inputs={"a": 1}, cached_result=2)
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_is_cached(state=state, inputs={"a": 1})
        assert isinstance(exc.value.state, Success)
        assert exc.value.state.result == 2
        assert exc.value.state.cached is state

    def test_cached_different_inputs(self):
        task = Task(cache_validator=cache_validators.all_inputs)
        state = CachedState(cached_inputs={"a": 1}, cached_result=2)
        new_state = TaskRunner(task).check_task_is_cached(state=state, inputs={"a": 2})
        assert new_state is state

    def test_cached_duration(self):
        task = Task(cache_validator=cache_validators.duration_only)
        state = CachedState(
            cached_result=2,
            cached_result_expiration=datetime.utcnow() + timedelta(minutes=1),
        )

        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_is_cached(state=state, inputs={"a": 1})
        assert isinstance(exc.value.state, Success)
        assert exc.value.state.result == 2
        assert exc.value.state.cached is state

    def test_cached_duration_fail(self):
        task = Task(cache_validator=cache_validators.duration_only)
        state = CachedState(
            cached_result=2,
            cached_result_expiration=datetime.utcnow() + timedelta(minutes=-1),
        )
        new_state = TaskRunner(task).check_task_is_cached(state=state, inputs={"a": 1})
        assert new_state is state


class TestSetTaskRunning:
    @pytest.mark.parametrize("state", [Pending(), CachedState()])
    def test_pending(self, state):
        new_state = TaskRunner(task=Task()).set_task_to_running(state=state)
        assert new_state.is_running()

    @pytest.mark.parametrize("state", [Running(), Success(), Skipped()])
    def test_not_pending(self, state):
        with pytest.raises(ENDRUN):
            TaskRunner(task=Task()).set_task_to_running(state=state)


class TestRunTaskStep:
    def test_running_state(self):
        state = Running()
        new_state = TaskRunner(task=Task()).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert new_state.is_successful()

    @pytest.mark.parametrize("state", [Pending(), CachedState(), Success(), Skipped()])
    def test_not_running_state(self, state):
        with pytest.raises(ENDRUN):
            TaskRunner(task=Task()).get_task_run_state(
                state=state, inputs={}, timeout_handler=None
            )

    def test_raise_success_signal(self):
        @prefect.task
        def fn():
            raise signals.SUCCESS()

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert new_state.is_successful()

    def test_raise_fail_signal(self):
        @prefect.task
        def fn():
            raise signals.FAIL()

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert new_state.is_failed()

    def test_raise_skip_signal(self):
        @prefect.task
        def fn():
            raise signals.SKIP()

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert isinstance(new_state, Skipped)

    def test_raise_pause_signal(self):
        @prefect.task
        def fn():
            raise signals.PAUSE()

        state = Running()
        with pytest.raises(signals.PAUSE):
            TaskRunner(task=fn).get_task_run_state(
                state=state, inputs={}, timeout_handler=None
            )

    def test_run_with_error(self):
        @prefect.task
        def fn():
            1 / 0

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert new_state.is_failed()
        assert isinstance(new_state.result, ZeroDivisionError)

    def test_inputs(self):
        @prefect.task
        def fn(x):
            return x + 1

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={"x": 1}, timeout_handler=None
        )
        assert new_state.is_successful()
        assert new_state.result == 2

    def test_invalid_inputs(self):
        @prefect.task
        def fn(x):
            return x + 1

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={"y": 1}, timeout_handler=None
        )
        assert new_state.is_failed()


class TestCheckRetryStep:
    @pytest.mark.parametrize(
        "state", [Success(), Pending(), Running(), Retrying(), Skipped()]
    )
    def test_non_failed_states(self, state):
        new_state = TaskRunner(task=Task()).check_for_retry(state=state, inputs={})
        assert new_state is state

    def test_failed_zero_max_retry(self):
        state = Failed()
        new_state = TaskRunner(task=Task()).check_for_retry(state=state, inputs={})
        assert new_state is state

    def test_failed_one_max_retry(self):
        state = Failed()
        new_state = TaskRunner(
            task=Task(max_retries=1, retry_delay=timedelta(0))
        ).check_for_retry(state=state, inputs={})
        assert isinstance(new_state, Retrying)
        assert new_state.run_count == 1

    def test_failed_one_max_retry_second_run(self):
        state = Failed()
        with prefect.context(_task_run_count=2):
            new_state = TaskRunner(
                task=Task(max_retries=1, retry_delay=timedelta(0))
            ).check_for_retry(state=state, inputs={})
            assert new_state is state

    def test_failed_retry_caches_inputs(self):
        state = Failed()
        new_state = TaskRunner(
            task=Task(max_retries=1, retry_delay=timedelta(0))
        ).check_for_retry(state=state, inputs={"x": 1})
        assert isinstance(new_state, Retrying)
        assert new_state.cached_inputs == {"x": 1}

    def test_retrying_when_run_count_greater_than_max_retries(self):
        with prefect.context(_task_run_count=10):
            state = Retrying()
            new_state = TaskRunner(
                task=Task(max_retries=1, retry_delay=timedelta(0))
            ).check_for_retry(state=state, inputs={})
            assert new_state is state

    def test_retrying_with_start_time(self):
        state = Retrying(start_time=datetime.utcnow())
        new_state = TaskRunner(
            task=Task(max_retries=1, retry_delay=timedelta(0))
        ).check_for_retry(state=state, inputs={})
        assert new_state is state

    def test_retrying_when_state_has_explicit_run_count_set(self):
        with prefect.context(_task_run_count=10):
            state = Retrying(run_count=5)
            new_state = TaskRunner(
                task=Task(max_retries=1, retry_delay=timedelta(0))
            ).check_for_retry(state=state, inputs={})
            assert new_state is state


class TestCacheResultStep:
    @pytest.mark.parametrize(
        "state", [Failed(), Skipped(), Finished(), Pending(), Running()]
    )
    def test_non_success_states(self, state):
        new_state = TaskRunner(task=Task()).cache_result(state=state, inputs={})
        assert new_state is state

    def test_success_state_with_no_cache_for(self):
        state = Success()
        new_state = TaskRunner(task=Task()).cache_result(state=state, inputs={})
        assert new_state is state

    def test_success_state(self):
        @prefect.task(cache_for=timedelta(minutes=10))
        def fn(x):
            return x + 1

        state = Success(result=2, message="hello")
        new_state = TaskRunner(task=fn).cache_result(state=state, inputs={"x": 5})
        assert new_state is not state
        assert new_state.is_successful()
        assert new_state.result == 2
        assert new_state.message == "hello"
        assert isinstance(new_state.cached, CachedState)
        assert new_state.cached.cached_result == 2
        assert new_state.cached.cached_inputs == {"x": 5}


class TestCheckScheduledStep:
    @pytest.mark.parametrize(
        "state", [Failed(), Pending(), Skipped(), Running(), Success()]
    )
    def test_non_scheduled_states(self, state):
        assert (
            TaskRunner(task=Task()).check_task_reached_start_time(state=state) is state
        )

    @pytest.mark.parametrize(
        "state", [Scheduled(start_time=None), Retrying(start_time=None)]
    )
    def test_scheduled_states_without_start_time(self, state):
        assert (
            TaskRunner(task=Task()).check_task_reached_start_time(state=state) is state
        )

    @pytest.mark.parametrize(
        "state",
        [
            Scheduled(start_time=datetime.utcnow() + timedelta(minutes=10)),
            Retrying(start_time=datetime.utcnow() + timedelta(minutes=10)),
        ],
    )
    def test_scheduled_states_with_future_start_time(self, state):
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task=Task()).check_task_reached_start_time(state=state)
        assert exc.value.state is state

    @pytest.mark.parametrize(
        "state",
        [
            Scheduled(start_time=datetime.utcnow() - timedelta(minutes=1)),
            Retrying(start_time=datetime.utcnow() - timedelta(minutes=1)),
        ],
    )
    def test_scheduled_states_with_past_start_time(self, state):
        assert (
            TaskRunner(task=Task()).check_task_reached_start_time(state=state) is state
        )

    @pytest.mark.parametrize(
        "state",
        [
            Scheduled(start_time=datetime.utcnow() + timedelta(minutes=10)),
            Retrying(start_time=datetime.utcnow() + timedelta(minutes=10)),
        ],
    )
    def test_scheduled_stategnore_trigger_with_future_start_time(self, state):
        result = TaskRunner(task=Task()).check_task_reached_start_time(
            state=state, ignore_trigger=True
        )
        assert result is state


handler_results = collections.defaultdict(lambda: 0)


@pytest.fixture(autouse=True)
def clear_handler_results():
    handler_results.clear()


def task_handler(task, old_state, new_state):
    """state change handler for tasks that increments a value by 1"""
    assert isinstance(task, Task)
    assert isinstance(old_state, State)
    assert isinstance(new_state, State)
    handler_results["Task"] += 1
    return new_state


def task_runner_handler(task_runner, old_state, new_state):
    """state change handler for task runners that increments a value by 1"""
    assert isinstance(task_runner, TaskRunner)
    assert isinstance(old_state, (type(None), State))
    assert isinstance(new_state, (type(None), State))
    handler_results["TaskRunner"] += 1
    return new_state or Pending()


class TestTaskStateHandlers:
    def test_task_handlers_are_called(self):
        task = Task(state_handlers=[task_handler])
        TaskRunner(task=task).run()
        # the task changed state twice: Pending -> Running -> Success
        assert handler_results["Task"] == 2

    def test_task_handlers_are_called_on_retry(self):
        @prefect.task(
            state_handlers=[task_handler], max_retries=1, retry_delay=timedelta(0)
        )
        def fn():
            1 / 0

        TaskRunner(task=fn).run()
        # the task changed state three times: Pending -> Running -> Failed -> Retry
        assert handler_results["Task"] == 3

    def test_task_handlers_are_called_on_failure(self):
        @prefect.task(state_handlers=[task_handler])
        def fn():
            1 / 0

        TaskRunner(task=fn).run()
        # the task changed state two times: Pending -> Running -> Failed
        assert handler_results["Task"] == 2

    def test_multiple_task_handlers_are_called(self):
        task = Task(state_handlers=[task_handler, task_handler])
        TaskRunner(task=task).run()
        # each task changed state twice: Pending -> Running -> Success
        assert handler_results["Task"] == 4

    def test_multiple_task_handlers_are_called_in_sequence(self):
        # the second task handler will assert the result of the first task handler is a state
        # and raise an error, as long as the task_handlers are called in sequence on the
        # previous result
        task = Task(state_handlers=[lambda *a: None, task_handler])
        with pytest.raises(AssertionError):
            with prefect.utilities.tests.raise_on_exception():
                TaskRunner(task=task).run()

    def test_task_handler_that_doesnt_return_state(self):
        task = Task(state_handlers=[lambda *a: None])
        # raises an attribute error because it tries to access a property of the state that
        # doesn't exist on None
        with pytest.raises(AttributeError):
            with prefect.utilities.tests.raise_on_exception():
                TaskRunner(task=task).run()


class TestTaskRunnerStateHandlers:
    def test_task_runner_handlers_are_called(self):
        TaskRunner(task=Task(), state_handlers=[task_runner_handler]).run()
        # the task changed state twice: Initialization -> Pending -> Running -> Success
        assert handler_results["TaskRunner"] == 3

    def test_task_runner_handlers_are_called_on_retry(self):
        @prefect.task(max_retries=1, retry_delay=timedelta(0))
        def fn():
            1 / 0

        TaskRunner(task=fn, state_handlers=[task_runner_handler]).run()
        # the task changed state three times: Initialization -> Pending -> Running -> Failed -> Retry
        assert handler_results["TaskRunner"] == 4

    def test_multiple_task_runner_handlers_are_called(self):
        TaskRunner(
            task=Task(), state_handlers=[task_runner_handler, task_runner_handler]
        ).run()
        # each task changed state twice: Initialization -> Pending -> Running -> Success
        assert handler_results["TaskRunner"] == 6

    def test_multiple_task_runner_handlers_are_called_in_sequence(self):
        # the second task handler will assert the result of the first task handler is a state
        # and raise an error, as long as the task_handlers are called in sequence on the
        # previous result
        with pytest.raises(AssertionError):
            with prefect.utilities.tests.raise_on_exception():
                TaskRunner(
                    task=Task(),
                    state_handlers=[lambda *a: Ellipsis, task_runner_handler],
                ).run()

    def test_task_runner_handler_that_doesnt_return_state(self):
        # raises an attribute error because it tries to access a property of the state that
        # doesn't exist on None
        with pytest.raises(AttributeError):
            with prefect.utilities.tests.raise_on_exception():
                TaskRunner(task=Task(), state_handlers=[lambda *a: None]).run()

    def test_task_handler_that_raises_signal_is_trapped(self):
        def handler(task, old, new):
            raise signals.FAIL()

        task = Task(state_handlers=[handler])
        state = TaskRunner(task=task).run()
        assert state.is_failed()

    def test_task_handler_that_has_error_is_trapped(self):
        def handler(task, old, new):
            1 / 0

        task = Task(state_handlers=[handler])
        state = TaskRunner(task=task).run()
        assert state.is_failed()


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_runner_performs_mapping(executor):
    add = AddTask()
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(ListTask(), add, key="y", mapped=True)
    runner = TaskRunner(add)
    with executor.start():
        lazy_list = runner.run(
            upstream_states={ex: Success(result=1), ey: Success(result=[1, 2, 3])},
            executor=executor,
            mapped=True,
        )
        res = executor.wait(lazy_list)
    assert isinstance(res, list)
    assert [s.result for s in res] == [2, 3, 4]


class TestCheckUpstreamsforMapping:
    def test_ends_if_non_running_state_passed(self):
        add = AddTask()
        ex = Edge(SuccessTask(), add, key="x")
        ey = Edge(ListTask(), add, key="y", mapped=True)
        runner = TaskRunner(add)
        with pytest.raises(ENDRUN) as exc:
            state = runner.check_upstreams_for_mapping(
                state=Pending(),
                upstream_states={ex: Success(result=1), ey: Success(result=[])},
            )
        assert exc.value.state.is_pending()

    def test_no_checks_if_nonstate_futurelike_obj_passed_for_only_upstream_state(self):
        add = AddTask()
        ex = Edge(SuccessTask(), add, key="x")
        ey = Edge(ListTask(), add, key="y", mapped=True)
        runner = TaskRunner(add)
        future = collections.namedtuple("futurestate", ["result", "message"])
        prestate = Running()
        state = runner.check_upstreams_for_mapping(
            state=prestate,
            upstream_states={
                ex: Success(result=1),
                ey: future(result=[], message=None),
            },
        )
        assert state is prestate

    def test_partial_checks_if_nonstate_futurelike_obj_passed_for_upstream_states(self):
        add = AddTask()
        ex = Edge(SuccessTask(), add, key="x", mapped=True)
        ey = Edge(ListTask(), add, key="y", mapped=True)
        runner = TaskRunner(add)
        future = collections.namedtuple("futurestate", ["result", "message"])
        with pytest.raises(ENDRUN) as exc:
            runner.check_upstreams_for_mapping(
                state=Running(),
                upstream_states={
                    ex: Success(result=[]),
                    ey: future(result=[], message=None),
                },
            )
        assert exc.value.state.is_skipped()

    def test_skips_if_empty_iterable_for_mapped_task(self):
        add = AddTask()
        ex = Edge(SuccessTask(), add, key="x")
        ey = Edge(ListTask(), add, key="y", mapped=True)
        runner = TaskRunner(add)
        with pytest.raises(ENDRUN) as exc:
            state = runner.check_upstreams_for_mapping(
                state=Running(),
                upstream_states={ex: Success(result=1), ey: Success(result=[])},
            )
        assert exc.value.state.is_skipped()

    def test_skips_if_no_mapped_inputs_provided_for_mapped_task(self):
        add = AddTask()
        ex = Edge(SuccessTask(), add, key="x")
        ey = Edge(ListTask(), add, key="y")
        runner = TaskRunner(add)
        with pytest.raises(ENDRUN) as exc:
            runner.check_upstreams_for_mapping(
                state=Running(),
                upstream_states={ex: Success(result=1), ey: Success(result=[])},
            )
        state = exc.value.state
        assert state.is_skipped()
        assert "No inputs" in state.message


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_runner_ignores_trigger_for_parent_mapped_task_but_not_children(executor):
    add = AddTask(trigger=prefect.triggers.all_failed)
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(ListTask(), add, key="y", mapped=True)
    runner = TaskRunner(add)
    with executor.start():
        res = executor.wait(
            runner.run(
                upstream_states={ex: Success(result=1), ey: Success(result=[1, 2, 3])},
                executor=executor,
                mapped=True,
            )
        )
    assert isinstance(res, list)
    assert all([isinstance(s, TriggerFailed) for s in res])
