import collections
from datetime import datetime, timedelta
from time import sleep
from unittest.mock import MagicMock

import pendulum
import pytest

import prefect
from prefect.client import Secret
from prefect.core.edge import Edge
from prefect.core.task import Task
from prefect.engine import cache_validators, signals
from prefect.engine.cache_validators import (
    all_inputs,
    all_parameters,
    duration_only,
    never_use,
    partial_inputs_only,
    partial_parameters_only,
)
from prefect.engine.result import Result, NoResult
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.state import (
    Cached,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Resume,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Submitted,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.engine.task_runner import ENDRUN, TaskRunner
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.debug import raise_on_exception
from prefect.utilities.tasks import pause_task


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


class MapTask(Task):
    def run(self):
        return prefect.context.get("map_index")


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
    now = pendulum.now("utc")

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


def test_task_that_raises_retry_with_naive_datetime_is_assumed_UTC():
    now = datetime.utcnow()
    assert now.tzinfo is None

    class Retry5Min(Task):
        def run(self):
            raise signals.RETRY(start_time=now + timedelta(minutes=5))

    state = TaskRunner(task=Retry5Min()).run()
    assert isinstance(state, Retrying)
    assert state.start_time == pendulum.instance(now, tz="UTC") + timedelta(minutes=5)
    assert state.start_time.tzinfo


def test_task_that_raises_retry_gets_retried_even_if_max_retries_is_set():
    """
    Test that tasks that raise a retry signal get retried even if they exceed max_retries
    """
    retry_task = RaiseRetryTask(max_retries=1, retry_delay=timedelta(0))
    task_runner = TaskRunner(task=retry_task)

    # first run should be retrying
    with prefect.context(task_run_count=1):
        state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.start_time, datetime)

    # second run should also be retry because the task raises it explicitly

    with prefect.context(task_run_count=2):
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


def test_task_runner_does_not_raise_on_exception_when_endrun_raised_by_mapping():
    """after mapping, an ENDRUN is raised"""
    with raise_on_exception():
        state = TaskRunner(Task()).run(
            upstream_states={Edge(1, 2, mapped=True): Success(result=[1])}
        )
    assert state.is_mapped()


@pytest.mark.parametrize("state", [Success(), Running()])
def test_task_runner_does_not_raise_on_exception_when_endrun_raised_by_state(state):
    """an ENDRUN is raised if the task can't be run, for example if it is in a SUCCESS or RUNNING state"""
    with raise_on_exception():
        new_state = TaskRunner(Task()).run(state=state)
    assert new_state is state


def test_task_runner_accepts_dictionary_of_edges():
    add = AddTask()
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(SuccessTask(), add, key="y")
    runner = TaskRunner(add)
    state = runner.run(upstream_states={ex: Success(result=1), ey: Success(result=1)})
    assert state.is_successful()
    assert state.result == 2


def test_task_runner_can_handle_timeouts_by_default():
    sleeper = SlowTask(timeout=1)
    upstream_state = Success(result=2)
    state = TaskRunner(sleeper).run(
        upstream_states={Edge(None, sleeper, key="secs"): upstream_state}
    )
    assert isinstance(state, TimedOut)
    assert "timed out" in state.message
    assert isinstance(state.result, TimeoutError)
    assert state.cached_inputs == dict(secs=Result(2))


def test_task_runner_handles_secrets():
    t = SecretTask()
    with set_temporary_config({"cloud.use_local_secrets": True}):
        state = TaskRunner(t).run(context=dict(secrets=dict(testing="my_private_str")))
    assert state.is_successful()
    assert state.result is "my_private_str"


def test_task_that_starts_failed_doesnt_get_retried():
    state = TaskRunner(Task()).run(state=Failed())
    assert state.is_failed()


def test_runner_checks_cached_inputs_correctly():
    with pytest.warns(UserWarning):
        task = AddTask(cache_validator=cache_validators.all_inputs)
    pre = Cached(cached_inputs={"x": Result(1), "y": Result(2)}, result=99)
    upstream = {
        Edge(Task(), task, key="x"): Success(result=1),
        Edge(Task(), task, key="y"): Success(result=2),
    }
    post = TaskRunner(task).run(state=pre, upstream_states=upstream)
    assert post.result == 99


class TestInitializeRun:
    @pytest.mark.parametrize(
        "state", [Success(), Failed(), Pending(), Scheduled(), Skipped(), Cached()]
    )
    def test_states_without_run_count(self, state):
        with prefect.context() as ctx:
            assert "task_run_count" not in ctx
            result = TaskRunner(Task()).initialize_run(
                state=state, context=ctx, upstream_states={}
            )
            assert ctx.task_run_count == 1
            assert result.state is state

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
            assert "task_run_count" not in ctx
            result = TaskRunner(Task()).initialize_run(
                state=state, context=ctx, upstream_states={}
            )
            assert ctx.task_run_count == state.run_count + 1
            assert result.state is state

    def test_task_runner_puts_resume_in_context_if_state_is_resume(self):
        with prefect.context() as ctx:
            assert "resume" not in ctx
            result = TaskRunner(Task()).initialize_run(
                state=Resume(), context=ctx, upstream_states={}
            )
            assert result.context.resume is True

    @pytest.mark.parametrize(
        "state", [Success(), Failed(), Pending(), Scheduled(), Skipped(), Cached()]
    )
    def test_task_runner_doesnt_put_resume_in_context_if_state_is_not_resume(
        self, state
    ):
        with prefect.context() as ctx:
            assert "resume" not in ctx
            result = TaskRunner(Task()).initialize_run(
                state=state, context=ctx, upstream_states={}
            )
            assert "resume" not in result.context

    def test_unwrap_submitted_states(self):
        state = Scheduled()
        result = TaskRunner(Task()).initialize_run(
            state=Submitted(state=state), context={}, upstream_states={}
        )
        assert result.state is state


class TestCheckUpstreamFinished:
    def test_with_empty(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_finished(
            state=state, upstream_states={}
        )
        assert new_state is state

    def test_with_two_finished(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_finished(
            state=state, upstream_states={1: Success(), 2: Failed()}
        )
        assert new_state is state

    def test_raises_with_one_unfinished(self):
        state = Pending()
        with pytest.raises(ENDRUN):
            TaskRunner(Task()).check_upstream_finished(
                state=state, upstream_states={1: Success(), 2: Running()}
            )


class TestCheckUpstreamSkipped:
    def test_empty(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_skipped(
            state=state, upstream_states={}
        )
        assert new_state is state

    def test_unskipped_states(self):
        state = Pending()
        new_state = TaskRunner(Task()).check_upstream_skipped(
            state=state, upstream_states={1: Success(), 2: Failed()}
        )
        assert new_state is state

    def test_raises_with_skipped(self):
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(Task()).check_upstream_skipped(
                state=state, upstream_states={1: Skipped()}
            )
        assert isinstance(exc.value.state, Skipped)

    def test_doesnt_raise_with_skipped_and_flag_set(self):
        state = Pending()
        task = Task(skip_on_upstream_skip=False)
        new_state = TaskRunner(task).check_upstream_skipped(
            state=state, upstream_states={1: Skipped()}
        )
        assert new_state is state


class TestCheckTaskTrigger:
    def test_all_successful_pass(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states={1: Success(), 2: Success()}
        )
        assert new_state is state

    def test_all_successful_fail(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success(), 2: Failed()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "all_successful"' in str(exc.value.state)

    def test_all_successful_empty(self):
        task = Task(trigger=prefect.triggers.all_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(state=state, upstream_states={})
        assert new_state is state

    def test_all_failed_pass(self):
        task = Task(trigger=prefect.triggers.all_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states={1: Failed(), 2: Failed()}
        )
        assert new_state is state

    def test_all_failed_fail(self):
        task = Task(trigger=prefect.triggers.all_failed)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success(), 2: Failed()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "all_failed"' in str(exc.value.state)

    def test_all_failed_empty(self):
        task = Task(trigger=prefect.triggers.all_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(state=state, upstream_states={})
        assert new_state is state

    def test_any_successful_pass(self):
        task = Task(trigger=prefect.triggers.any_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states={1: Success(), 2: Failed()}
        )
        assert new_state is state

    def test_any_successful_fail(self):
        task = Task(trigger=prefect.triggers.any_successful)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Failed(), 2: Failed()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "any_successful"' in str(exc.value.state)

    def test_any_successful_empty(self):
        task = Task(trigger=prefect.triggers.any_successful)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(state=state, upstream_states={})
        assert new_state is state

    def test_any_failed_pass(self):
        task = Task(trigger=prefect.triggers.any_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states={1: Success(), 2: Failed()}
        )
        assert new_state is state

    def test_any_failed_fail(self):
        task = Task(trigger=prefect.triggers.any_failed)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success(), 2: Success()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "any_failed"' in str(exc.value.state)

    def test_any_failed_empty(self):
        task = Task(trigger=prefect.triggers.any_failed)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(state=state, upstream_states={})
        assert new_state is state

    def test_all_finished_pass(self):
        task = Task(trigger=prefect.triggers.all_finished)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(
            state=state, upstream_states={1: Success(), 2: Failed()}
        )
        assert new_state is state

    def test_all_finished_fail(self):
        task = Task(trigger=prefect.triggers.all_finished)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success(), 2: Pending()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert 'Trigger was "all_finished"' in str(exc.value.state)

    def test_all_finished_empty(self):
        task = Task(trigger=prefect.triggers.all_finished)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(state=state, upstream_states={})
        assert new_state is state

    def test_manual_only(self):
        task = Task(trigger=prefect.triggers.manual_only)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success(), 2: Pending()}
            )
        assert isinstance(exc.value.state, Paused)

    def test_manual_only_empty(self):
        task = Task(trigger=prefect.triggers.manual_only)
        state = Pending()
        new_state = TaskRunner(task).check_task_trigger(state=state, upstream_states={})
        assert new_state is state

    def test_custom_trigger_function_raise(self):
        def trigger(states):
            1 / 0

        task = Task(trigger=trigger)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success()}
            )
        assert isinstance(exc.value.state, TriggerFailed)
        assert isinstance(exc.value.state.result, ZeroDivisionError)


class TestCheckTaskReady:
    @pytest.mark.parametrize("state", [Cached(), Pending(), Mapped()])
    def test_ready_states(self, state):
        new_state = TaskRunner(task=Task()).check_task_is_ready(state=state)
        assert new_state is state

    @pytest.mark.parametrize(
        "state",
        [Running(), Finished(), TriggerFailed(), Skipped(), Success(), Paused()],
    )
    def test_not_ready_doesnt_run(self, state):

        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task=Task()).check_task_is_ready(state=state)
        assert exc.value.state is state


class TestGetTaskInputs:
    def test_get_empty_inputs(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(), upstream_states={}
        )
        assert inputs == {}

    def test_get_unkeyed_inputs(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(), upstream_states={Edge(1, 2): Success(result=1)}
        )
        assert inputs == {}

    def test_get_inputs_from_upstream(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(), upstream_states={Edge(1, 2, key="x"): Success(result=1)}
        )
        assert inputs == {"x": Result(1)}

    def test_get_inputs_from_upstream_with_non_key_edges(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(),
            upstream_states={
                Edge(1, 2, key="x"): Success(result=1),
                Edge(1, 2): Success(result=2),
            },
        )
        assert inputs == {"x": Result(1)}

    def test_get_inputs_from_upstream_failed(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(),
            upstream_states={Edge(1, 2, key="x"): Failed(result=ValueError())},
        )
        assert isinstance(inputs["x"].value, ValueError)

    def test_get_inputs_from_upstream_mapped(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(),
            upstream_states={Edge(1, 2, key="x", mapped=True): Success(result=[1, 2])},
        )
        assert inputs == {"x": Result([1, 2])}

    def test_get_inputs_from_cached_inputs(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(cached_inputs={"x": Result(1)}), upstream_states={}
        )
        assert inputs == {"x": Result(1)}

    def test_get_inputs_from_cached_inputs_and_upstream_states(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(cached_inputs={"x": Result(1)}),
            upstream_states={Edge(1, 2, key="y"): Success(result=2)},
        )
        assert inputs == {"x": Result(1), "y": Result(2)}

    def test_get_inputs_from_cached_inputs_overwrites_upstream_states(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(cached_inputs={"x": Result(1)}),
            upstream_states={
                Edge(1, 2, key="x"): Success(result=2),
                Edge(1, 2, key="y"): Success(result=2),
            },
        )
        assert inputs == {"x": Result(1), "y": Result(2)}


class TestCheckTaskCached:
    @pytest.mark.parametrize("state", [Pending(), Success(), Retrying()])
    def test_not_cached(self, state):
        new_state = TaskRunner(task=Task()).check_task_is_cached(state=state, inputs={})
        assert new_state is state

    def test_cached_same_inputs(self):
        with pytest.warns(UserWarning):
            task = Task(cache_validator=cache_validators.all_inputs)
        state = Cached(cached_inputs={"a": Result(1)}, result=Result(2))
        new = TaskRunner(task).check_task_is_cached(
            state=state, inputs={"a": Result(1)}
        )
        assert new is state

    def test_cached_different_inputs(self):
        with pytest.warns(UserWarning):
            task = Task(cache_validator=cache_validators.all_inputs)
        state = Cached(cached_inputs={"a": Result(1)}, result=2)
        new_state = TaskRunner(task).check_task_is_cached(
            state=state, inputs={"a": Result(2)}
        )
        assert new_state.is_pending()

    def test_cached_duration(self):
        with pytest.warns(UserWarning):
            task = Task(cache_validator=cache_validators.duration_only)
        state = Cached(
            result=2,
            cached_result_expiration=pendulum.now("utc") + timedelta(minutes=1),
        )

        new = TaskRunner(task).check_task_is_cached(
            state=state, inputs={"a": Result(1)}
        )
        assert new is state

    def test_cached_duration_fail(self):
        with pytest.warns(UserWarning):
            task = Task(cache_validator=cache_validators.duration_only)
        state = Cached(
            result=2,
            cached_result_expiration=pendulum.now("utc") + timedelta(minutes=-1),
        )
        new_state = TaskRunner(task).check_task_is_cached(
            state=state, inputs={"a": Result(1)}
        )
        assert new_state.is_pending()


class TestSetTaskRunning:
    @pytest.mark.parametrize("state", [Pending()])
    def test_pending(self, state):
        new_state = TaskRunner(task=Task()).set_task_to_running(state=state)
        assert new_state.is_running()

    @pytest.mark.parametrize("state", [Cached(), Running(), Success(), Skipped()])
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

    @pytest.mark.parametrize("state", [Pending(), Cached(), Success(), Skipped()])
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
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert isinstance(new_state, Paused)

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
            state=state, inputs={"x": Result(1)}, timeout_handler=None
        )
        assert new_state.is_successful()
        assert new_state.result == 2

    def test_invalid_inputs(self):
        @prefect.task
        def fn(x):
            return x + 1

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={"y": Result(1)}, timeout_handler=None
        )
        assert new_state.is_failed()

    def test_returns_success_with_hydrated_result_obj(self):
        runner = TaskRunner(task=Task())
        state = runner.get_task_run_state(
            state=Running(), inputs={}, timeout_handler=None
        )
        assert state.is_successful()
        assert isinstance(state._result, Result)
        assert state._result == Result(
            value=None, handled=False, result_handler=runner.result_handler
        )

    def test_returns_success_with_correct_result_handler(self):
        runner = TaskRunner(task=Task(result_handler=ResultHandler()))
        state = runner.get_task_run_state(
            state=Running(), inputs={}, timeout_handler=None
        )
        assert state.is_successful()
        assert isinstance(state._result, Result)
        assert state._result.result_handler == ResultHandler()


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
        with prefect.context(task_run_count=2):
            new_state = TaskRunner(
                task=Task(max_retries=1, retry_delay=timedelta(0))
            ).check_for_retry(state=state, inputs={})
            assert new_state is state

    def test_failed_retry_caches_inputs(self):
        state = Failed()

        new_state = TaskRunner(
            task=Task(max_retries=1, retry_delay=timedelta(0))
        ).check_for_retry(state=state, inputs={"x": Result(1)})
        assert isinstance(new_state, Retrying)
        assert new_state.cached_inputs == {"x": Result(1)}

    def test_retrying_when_run_count_greater_than_max_retries(self):
        with prefect.context(task_run_count=10):
            state = Retrying()
            new_state = TaskRunner(
                task=Task(max_retries=1, retry_delay=timedelta(0))
            ).check_for_retry(state=state, inputs={})
            assert new_state is state

    def test_retrying_with_start_time(self):
        state = Retrying(start_time=pendulum.now("utc"))
        new_state = TaskRunner(
            task=Task(max_retries=1, retry_delay=timedelta(0))
        ).check_for_retry(state=state, inputs={})
        assert new_state is state

    def test_retrying_when_state_has_explicit_run_count_set(self):
        with prefect.context(task_run_count=10):
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
    def test_success_state_with_no_cache_for(self, validator):
        state = Success()
        with pytest.warns(UserWarning):
            t = Task(cache_validator=validator)
        new_state = TaskRunner(task=t).cache_result(state=state, inputs={})
        assert new_state is state

    def test_success_state(self):
        @prefect.task(cache_for=timedelta(minutes=10))
        def fn(x):
            return x + 1

        state = Success(result=2, message="hello")

        new_state = TaskRunner(task=fn).cache_result(
            state=state, inputs={"x": Result(5)}
        )
        assert new_state is not state
        assert new_state.is_successful()
        assert isinstance(new_state, Cached)
        assert new_state.message == "hello"
        assert new_state.result == 2
        assert new_state.cached_inputs == {"x": Result(5)}


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
            Scheduled(start_time=pendulum.now("utc") + timedelta(minutes=10)),
            Retrying(start_time=pendulum.now("utc") + timedelta(minutes=10)),
        ],
    )
    def test_scheduled_states_with_future_start_time(self, state):
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task=Task()).check_task_reached_start_time(state=state)
        assert exc.value.state is state

    @pytest.mark.parametrize(
        "state",
        [
            Scheduled(start_time=pendulum.now("utc") - timedelta(minutes=1)),
            Retrying(start_time=pendulum.now("utc") - timedelta(minutes=1)),
        ],
    )
    def test_scheduled_states_with_past_start_time(self, state):
        assert (
            TaskRunner(task=Task()).check_task_reached_start_time(state=state) is state
        )


class TestTaskStateHandlers:
    def test_task_handlers_are_called(self):
        task_handler = MagicMock(side_effect=lambda t, o, n: n)
        task = Task(state_handlers=[task_handler])
        TaskRunner(task=task).run()
        # the task changed state twice: Pending -> Running -> Success
        assert task_handler.call_count == 2

    def test_task_on_failure_is_not_called(self):
        on_failure = MagicMock()
        task = Task(on_failure=on_failure)
        TaskRunner(task=task).run()
        assert not on_failure.called

    def test_task_on_failure_is_called(self):
        on_failure = MagicMock()
        task = ErrorTask(on_failure=on_failure)
        TaskRunner(task=task).run()
        assert on_failure.call_count == 1
        assert on_failure.call_args[0][0] is task
        assert on_failure.call_args[0][1].is_failed()

    def test_task_on_trigger_failure_is_called(self):
        on_failure = MagicMock()
        task = Task(on_failure=on_failure)
        edge = Edge(Task(), task)
        TaskRunner(task=task).run(upstream_states={edge: Failed()})
        assert on_failure.call_count == 1
        assert on_failure.call_args[0][0] is task
        assert isinstance(on_failure.call_args[0][1], TriggerFailed)

    def test_task_handlers_are_called_on_retry(self):
        task_handler = MagicMock(side_effect=lambda t, o, n: n)

        @prefect.task(
            state_handlers=[task_handler], max_retries=1, retry_delay=timedelta(0)
        )
        def fn():
            1 / 0

        TaskRunner(task=fn).run()
        # the task changed state three times: Pending -> Running -> Failed -> Retry
        assert task_handler.call_count == 3

    def test_task_handlers_are_called_on_failure(self):
        task_handler = MagicMock(side_effect=lambda t, o, n: n)

        @prefect.task(state_handlers=[task_handler])
        def fn():
            1 / 0

        TaskRunner(task=fn).run()
        # the task changed state two times: Pending -> Running -> Failed
        assert task_handler.call_count == 2

    def test_multiple_task_handlers_are_called(self):
        task_handler = MagicMock(side_effect=lambda t, o, n: n)
        task = Task(state_handlers=[task_handler, task_handler])
        TaskRunner(task=task).run()
        # each task changed state twice: Pending -> Running -> Success
        assert task_handler.call_count == 4

    def test_multiple_task_handlers_are_called_in_sequence(self):
        def task_handler(task_runner, old_state, new_state):
            assert isinstance(new_state, State)

        # the second task handler will assert the result of the first task handler is a state
        # and raise an error, as long as the task_handlers are called in sequence on the
        # previous result
        task = Task(state_handlers=[lambda *a: None, task_handler])
        with pytest.raises(AssertionError):
            with prefect.utilities.debug.raise_on_exception():
                TaskRunner(task=task).run()

    def test_task_handler_that_doesnt_return_state(self):
        # this will raise an error because no state is returned
        task = Task(state_handlers=[lambda *a: None])
        with pytest.raises(AttributeError):
            with prefect.utilities.debug.raise_on_exception():
                TaskRunner(task=task).run()


class TestTaskRunnerStateHandlers:
    def test_task_runner_handlers_are_called(self):
        task_runner_handler = MagicMock(side_effect=lambda t, o, n: n)
        TaskRunner(task=Task(), state_handlers=[task_runner_handler]).run()
        # the task changed state two times: Pending -> Running -> Success
        assert task_runner_handler.call_count == 2

    def test_task_runner_handlers_are_called_on_retry(self):
        task_runner_handler = MagicMock(side_effect=lambda t, o, n: n)

        @prefect.task(max_retries=1, retry_delay=timedelta(0))
        def fn():
            1 / 0

        state = TaskRunner(task=fn, state_handlers=[task_runner_handler]).run()
        # the task changed state three times: Pending -> Running -> Failed -> Retry
        assert isinstance(state, Retrying)
        assert task_runner_handler.call_count == 3

    def test_task_runner_handlers_are_called_on_triggerfailed(self):
        task_runner_handler = MagicMock(side_effect=lambda t, o, n: n)

        runner = TaskRunner(
            task=Task(trigger=prefect.triggers.all_failed),
            state_handlers=[task_runner_handler],
        )
        state = runner.run(upstream_states={Edge(Task(), Task()): Success()})
        # the task changed state one time: Pending -> TriggerFailed
        assert isinstance(state, TriggerFailed)
        assert task_runner_handler.call_count == 1

    def test_task_runner_handlers_are_called_on_mapped(self):
        task_runner_handler = MagicMock(side_effect=lambda t, o, n: n)

        runner = TaskRunner(task=Task(), state_handlers=[task_runner_handler])
        state = runner.run(
            upstream_states={Edge(Task(), Task(), mapped=True): Success(result=[1])}
        )
        # the parent task changed state one time: Pending -> Mapped
        # the child task changed state one time: Pending -> Running -> Success
        assert isinstance(state, Mapped)
        assert task_runner_handler.call_count == 3

    def test_multiple_task_runner_handlers_are_called(self):
        task_runner_handler = MagicMock(side_effect=lambda t, o, n: n)
        TaskRunner(
            task=Task(), state_handlers=[task_runner_handler, task_runner_handler]
        ).run()
        # each task changed state two times: Pending -> Running -> Success
        assert task_runner_handler.call_count == 4

    def test_multiple_task_runner_handlers_are_called_in_sequence(self):
        # the second task handler will assert the result of the first task handler is a state
        # and raise an error, as long as the task_handlers are called in sequence on the
        # previous result
        def task_runner_handler(task_runner, old_state, new_state):
            assert isinstance(new_state, State)

        with pytest.raises(AssertionError):
            with prefect.utilities.debug.raise_on_exception():
                TaskRunner(
                    task=Task(),
                    state_handlers=[lambda *a: Ellipsis, task_runner_handler],
                ).run()

    def test_task_runner_handler_that_doesnt_return_state(self):
        # raises an error because the state handler doesn't return a state
        with pytest.raises(AttributeError):
            with prefect.utilities.debug.raise_on_exception():
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


class TestRunMappedStep:
    def test_run_mapped_with_empty_upstream_states(self):
        """
        Ensure infinite loop is avoided
        """
        state = TaskRunner(task=Task()).run_mapped_task(
            state=Pending(),
            upstream_states={},
            check_upstream=True,
            context={},
            executor=prefect.engine.executors.LocalExecutor(),
        )

    @pytest.mark.parametrize("state", [Pending(), Mapped(), Scheduled()])
    def test_run_mapped_returns_mapped(self, state):
        state = TaskRunner(task=Task()).run_mapped_task(
            state=Pending(),
            upstream_states={},
            check_upstream=True,
            context={},
            executor=prefect.engine.executors.LocalExecutor(),
        )
        assert state.is_mapped()


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_runner_performs_mapping(executor):
    add = AddTask()
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(ListTask(), add, key="y", mapped=True)
    runner = TaskRunner(add)
    with executor.start():
        res = runner.run(
            upstream_states={ex: Success(result=1), ey: Success(result=[1, 2, 3])},
            executor=executor,
        )
        res.map_states = executor.wait(res.map_states)
    assert isinstance(res, Mapped)
    assert [s.result for s in res.map_states] == [2, 3, 4]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_runner_skips_upstream_check_for_parent_mapped_task_but_not_children(
    executor
):
    add = AddTask(trigger=prefect.triggers.all_failed)
    ex = Edge(SuccessTask(), add, key="x")
    ey = Edge(ListTask(), add, key="y", mapped=True)
    runner = TaskRunner(add)
    with executor.start():
        res = runner.run(
            upstream_states={ex: Success(result=1), ey: Success(result=[1, 2, 3])},
            executor=executor,
        )
        res.map_states = executor.wait(res.map_states)
    assert isinstance(res, Mapped)
    assert all([isinstance(s, TriggerFailed) for s in res.map_states])


def test_task_runner_converts_pause_signal_to_paused_state_for_manual_only_triggers():
    t1, t2 = SuccessTask(), SuccessTask(trigger=prefect.triggers.manual_only)
    e = Edge(t1, t2)
    runner = TaskRunner(t2)
    out = runner.run(upstream_states={e: Success(result=1)})
    assert isinstance(out, Paused)
    assert "manual_only" in out.message


def test_task_runner_converts_pause_signal_to_paused_state_for_internally_raised_pauses():
    class WaitTask(Task):
        def run(self):
            pause_task()

    t1, t2 = SuccessTask(), WaitTask()
    e = Edge(t1, t2)
    runner = TaskRunner(t2)
    out = runner.run(upstream_states={e: Success(result=1)})
    assert isinstance(out, Paused)


def test_task_runner_bypasses_pause_when_requested():
    class WaitTask(Task):
        def run(self):
            pause_task()

    t1, t2 = SuccessTask(), WaitTask()
    e = Edge(t1, t2)
    runner = TaskRunner(t2)
    out = runner.run(upstream_states={e: Success(result=1)}, context=dict(resume=True))
    assert out.is_successful()


def test_mapped_tasks_parents_and_children_respond_to_individual_triggers():
    task_runner_handler = MagicMock(side_effect=lambda t, o, n: n)

    runner = TaskRunner(
        task=Task(trigger=prefect.triggers.all_failed),
        state_handlers=[task_runner_handler],
    )
    state = runner.run(
        upstream_states={Edge(Task(), Task(), mapped=True): Success(result=[1])}
    )
    # the parent task changed state one time: Pending -> Mapped
    # the child task changed state one time: Pending -> TriggerFailed
    assert isinstance(state, Mapped)
    assert task_runner_handler.call_count == 2
    assert isinstance(state.map_states[0], TriggerFailed)


def test_retry_has_updated_metadata():
    a, b = Success(result=15), Success(result="abc")

    runner = TaskRunner(task=AddTask(max_retries=1, retry_delay=timedelta(days=1)))
    state = runner.run(
        upstream_states={
            Edge(Task(), runner.task, key="x"): a,
            Edge(Task(), runner.task, key="y"): b,
        }
    )

    assert isinstance(state, Retrying)
    assert state.cached_inputs == dict(x=Result(15), y=Result("abc"))


def test_pending_raised_from_endrun_has_updated_metadata():
    class EndRunTask(Task):
        def run(self, x):
            raise ENDRUN(state=Pending("abc"))

    upstream_state = Success(result=15)

    runner = TaskRunner(task=EndRunTask())
    state = runner.run(upstream_states={Edge(Task(), Task(), key="x"): upstream_state})

    assert state.is_pending()
    assert state.cached_inputs == dict(x=Result(15))
