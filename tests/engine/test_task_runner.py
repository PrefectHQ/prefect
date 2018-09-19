import datetime

import pytest

from unittest.mock import MagicMock

import prefect
from prefect.core.edge import Edge
from prefect.core.task import Task
from prefect.engine import TaskRunner, signals
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


class RaiseDontRunTask(Task):
    """
    This task is just for testing -- raising DONTRUN inside a task is considered bad
    """

    def run(self):
        raise prefect.engine.signals.DONTRUN()


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


def test_task_that_fails_gets_retried_up_to_1_time():
    """
    Test that failed tasks are marked for retry if run_number is available
    """
    err_task = ErrorTask(max_retries=1)
    task_runner = TaskRunner(task=err_task)

    # first run should be retrying
    with prefect.context(_task_run_number=1):
        state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.scheduled_time, datetime.datetime)

    # second run should
    with prefect.context(_task_run_number=2):
        state = task_runner.run(state=state)
    assert isinstance(state, Failed)


def test_task_that_raises_retry_gets_retried_even_if_max_retries_is_set():
    """
    Test that tasks that raise a retry signal get retried even if they exceed max_retries
    """
    retry_task = RaiseRetryTask(max_retries=1)
    task_runner = TaskRunner(task=retry_task)

    # first run should be retrying
    with prefect.context(_task_run_number=1):
        state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.scheduled_time, datetime.datetime)

    # second run should also be retry because the task raises it explicitly

    with prefect.context(_task_run_number=2):
        state = task_runner.run(state=state)
    assert isinstance(state, Retrying)


def test_task_that_raises_skip_gets_skipped():
    task_runner = TaskRunner(task=RaiseSkipTask())
    assert isinstance(task_runner.run(), Skipped)


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
    msg = state.message
    if isinstance(msg, Exception):
        assert type(msg).__name__ == "ValueError"
    else:
        assert "ValueError" in msg


def test_task_runner_raise_on_exception_when_task_errors():
    with raise_on_exception():
        with pytest.raises(ValueError):
            TaskRunner(ErrorTask()).run()


def test_task_runner_raise_on_exception_when_task_signals():
    with raise_on_exception():
        with pytest.raises(prefect.engine.signals.FAIL):
            TaskRunner(RaiseFailTask()).run()


def test_tasks_that_raise_DONTRUN_are_treated_as_skipped():
    assert isinstance(TaskRunner(task=RaiseDontRunTask()).run(), Skipped)


class TestTaskRunner_get_pre_run_state:
    """
    Tests the TaskRunner's get_pre_run_state() method
    """

    @pytest.mark.parametrize("state", [Pending(), Retrying(), Scheduled()])
    def test_returns_running_if_successful_with_pending_state(self, state):
        runner = TaskRunner(SuccessTask())
        state = runner.get_pre_run_state(
            state=state, upstream_states=set(), ignore_trigger=False, inputs={}
        )
        assert isinstance(state, Running)

    def test_ignores_cached_state_if_task_didnt_ask_for_it(self):
        runner = TaskRunner(SuccessTask())
        state = runner.get_pre_run_state(
            state=CachedState(cached_result=4),
            upstream_states=set(),
            ignore_trigger=False,
            inputs={},
        )
        assert isinstance(state, Running)

    def test_returns_running_if_cached_state_with_expired_cache(self):
        runner = TaskRunner(
            SuccessTask(
                cache_validator=duration_only, cache_for=datetime.timedelta(days=1)
            )
        )
        expiration = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        state = runner.get_pre_run_state(
            state=CachedState(cached_result=4, cached_result_expiration=expiration),
            upstream_states=set(),
            ignore_trigger=False,
            inputs={},
        )
        assert isinstance(state, Running)

    @pytest.mark.parametrize(
        "validator",
        [
            all_inputs,
            all_parameters,
            duration_only,
            partial_inputs_only,
            partial_parameters_only,
        ],
    )
    def test_returns_successful_if_cached_state_is_validated(self, validator):
        runner = TaskRunner(
            SuccessTask(cache_validator=validator, cache_for=datetime.timedelta(days=1))
        )
        expiration = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        inputs = dict(x=2, y=1)
        params = dict(p="p", q=99)
        with prefect.context(_parameters=params):
            state = runner.get_pre_run_state(
                state=CachedState(
                    cached_parameters=params,
                    cached_inputs=inputs,
                    cached_result=4,
                    cached_result_expiration=expiration,
                ),
                inputs=inputs,
                upstream_states=set(),
                ignore_trigger=False,
            )
        assert isinstance(state, Success)
        assert state.result == 4

    def test_old_cached_state_is_still_returned_when_cache_is_used(self):
        runner = TaskRunner(
            SuccessTask(
                cache_validator=duration_only, cache_for=datetime.timedelta(days=1)
            )
        )
        expiration = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        cached_state = CachedState(cached_result=4, cached_result_expiration=expiration)
        state = runner.get_pre_run_state(
            state=cached_state, upstream_states=set(), ignore_trigger=False, inputs={}
        )
        assert isinstance(state, Success)
        assert state.result == 4
        assert state.cached == cached_state

    @pytest.mark.parametrize(
        "validator",
        [
            all_inputs,
            all_parameters,
            duration_only,
            never_use,
            partial_inputs_only,
            partial_parameters_only,
        ],
    )
    def test_returns_running_if_cached_state_is_invalidated(self, validator):
        runner = TaskRunner(
            SuccessTask(cache_validator=validator, cache_for=datetime.timedelta(days=1))
        )
        expiration = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        state = runner.get_pre_run_state(
            state=CachedState(
                cached_inputs=dict(x=2),
                cached_result=4,
                cached_result_expiration=expiration,
            ),
            inputs=dict(x=1),
            upstream_states=set(),
            ignore_trigger=False,
        )
        assert isinstance(state, Running)

    def test_returns_failed_with_internal_error(self):
        runner = TaskRunner(SuccessTask())
        # pass an invalid state to the function to see if the resulting errors are caught
        state = runner.get_pre_run_state(
            state=1, upstream_states=set(), ignore_trigger=False, inputs={}
        )
        assert isinstance(state, Failed)
        assert "object has no attribute" in str(state.message).lower()

    def test_raises_dontrun_if_upstream_arent_finished(self):
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_pre_run_state(
                state=Pending(),
                upstream_states={Pending(), Success()},
                ignore_trigger=False,
                inputs={},
            )
        assert "upstream tasks are not finished" in str(exc.value).lower()

    def test_skip_on_upstream_skip_is_false(self):
        """
        Tests that tasks do NOT skip if skip_on_upstream_skip is False
        """
        task = SuccessTask(skip_on_upstream_skip=False)
        runner = TaskRunner(task)
        state = runner.get_pre_run_state(
            state=Pending(),
            upstream_states={Skipped()},
            ignore_trigger=False,
            inputs={},
        )
        assert isinstance(state, Running)

    def test_returns_skipped_if_upstream_skipped(self):
        task = SuccessTask(True)
        runner = TaskRunner(task)
        state = runner.get_pre_run_state(
            state=Pending(),
            upstream_states={Skipped()},
            ignore_trigger=False,
            inputs={},
        )
        assert isinstance(state, Skipped)
        assert "upstream task was skipped" in state.message.lower()

    def test_raises_triggerfail_if_trigger_returns_false(self):
        task = SuccessTask(trigger=lambda upstream_states: False)
        runner = TaskRunner(task)
        state = runner.get_pre_run_state(
            state=Pending(), upstream_states=set(), ignore_trigger=False, inputs={}
        )
        assert isinstance(state, TriggerFailed)

    def test_ignores_trigger(self):
        task = SuccessTask(trigger=lambda upstream_states: False)
        runner = TaskRunner(task)
        state = runner.get_pre_run_state(
            state=Pending(), ignore_trigger=True, upstream_states=set(), inputs={}
        )
        assert isinstance(state, Running)

    def test_raises_dontrun_if_state_is_running(self):
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_pre_run_state(
                state=Running(), upstream_states=set(), ignore_trigger=False, inputs={}
            )
        assert "already running" in str(exc.value).lower()

    @pytest.mark.parametrize(
        "state", [Finished(), Success(), TriggerFailed(), Failed(), Skipped()]
    )
    def test_raises_dontrun_if_state_is_finished(self, state):
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_pre_run_state(
                state=state, upstream_states=set(), ignore_trigger=False, inputs={}
            )
        assert "already finished" in str(exc.value).lower()

    def test_raises_dontrun_if_state_is_not_pending(self):
        """
        This last trap is almost impossible to hit with current states, but could
        theoretically be hit by using the base state or a custom state.
        """
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_pre_run_state(
                state=State(), upstream_states=set(), ignore_trigger=False, inputs={}
            )
        assert "not ready to run" in str(exc.value).lower()

        class MyState(State):
            pass

        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_pre_run_state(
                state=MyState(), upstream_states=set(), ignore_trigger=False, inputs={}
            )
        assert "unrecognized" in str(exc.value).lower()


class TestTaskRunner_get_run_state:
    """
    Tests the TaskRunner's get_run_state() method
    """

    @pytest.mark.parametrize(
        "state",
        [
            Pending(),
            Retrying(),
            Scheduled(),
            Failed(),
            Success(),
            Finished(),
            Skipped(),
            TriggerFailed(),
        ],
    )
    def test_raises_dontrun_if_state_is_not_running(self, state):
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_run_state(state=state, inputs={})
        assert "not in a running state" in str(exc.value).lower()

    def test_runs_task(self):
        runner = TaskRunner(SuccessTask())
        state = runner.get_run_state(state=Running(), inputs={})
        assert state == Success(result=1)
        assert "succeeded" in state.message.lower()

    def test_runs_task_with_inputs(self):
        runner = TaskRunner(AddTask())
        state = runner.get_run_state(state=Running(), inputs=dict(x=1, y=2))
        assert state == Success(result=3)

    def test_fails_if_task_with_inputs_doesnt_receive_inputs(self):
        runner = TaskRunner(AddTask())
        state = runner.get_run_state(state=Running(), inputs={})
        assert isinstance(state, Failed)
        assert isinstance(state.message, TypeError)
        assert "required positional arguments" in str(state.message).lower()

    def test_raise_dontrun_results_in_skip(self):
        class DontRunTask:
            def run(self):
                raise signals.DONTRUN()

        runner = TaskRunner(DontRunTask())
        state = runner.get_run_state(state=Running(), inputs={})
        assert isinstance(state, Skipped)
        assert "dontrun was raised" in str(state.message).lower()

    def test_ignores_cached_attribute_if_task_doesnt_ask_for_it(self):
        runner = TaskRunner(AddTask())
        state = runner.get_run_state(state=Running(), inputs=dict(x=1, y=2))
        assert state.cached is None

    def test_uses_cache_for_as_trigger_for_initializing_a_cache(self):
        with pytest.warns(UserWarning):
            runner = TaskRunner(AddTask(cache_validator=duration_only))
        state = runner.get_run_state(state=Running(), inputs=dict(x=1, y=2))
        assert state.cached is None

    def test_sets_cached_attribute_if_task_requests(self):
        now = datetime.datetime.utcnow()
        runner = TaskRunner(AddTask(cache_for=datetime.timedelta(days=1)))
        with prefect.context(_parameters=dict(qq="time")):
            state = runner.get_run_state(state=Running(), inputs=dict(x=1, y=2))
        cached = state.cached
        assert isinstance(cached, CachedState)
        assert cached.cached_result_expiration >= now + datetime.timedelta(hours=23)
        assert cached.cached_inputs == dict(x=1, y=2)
        assert cached.cached_parameters == dict(qq="time")
        assert cached.cached_result == 3


class TestTaskRunner_get_post_run_state:
    """
    Tests the TaskRunner's get_post_run_state() method
    """

    @pytest.mark.parametrize("state", [Pending(), Retrying(), Scheduled(), Running()])
    def test_raises_dontrun_if_state_is_not_finished(self, state):
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_post_run_state(state=state, inputs={})
        assert "not in a finished state" in str(exc.value).lower()

    @pytest.mark.parametrize(
        "state", [Finished(), TriggerFailed(), Success(), Skipped(), Failed()]
    )
    def test_raises_dontrun_if_state_is_finished_but_not_retry_eligable(self, state):
        runner = TaskRunner(SuccessTask())
        with pytest.raises(signals.DONTRUN) as exc:
            runner.get_post_run_state(state=state, inputs={})
        assert "requires no further processing" in str(exc.value).lower()

    def test_returns_retry_if_failed_and_retry_eligable(self):
        runner = TaskRunner(
            ErrorTask(max_retries=1, retry_delay=datetime.timedelta(minutes=1))
        )
        with prefect.context(_task_run_number=1):
            state = runner.get_post_run_state(state=Failed(), inputs={})
        assert isinstance(state, Retrying)
        assert (state.scheduled_time - datetime.datetime.utcnow()) < datetime.timedelta(
            minutes=1
        )

        with prefect.context(_task_run_number=2):
            with pytest.raises(signals.DONTRUN):
                runner.get_post_run_state(state=Failed(), inputs={})


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
