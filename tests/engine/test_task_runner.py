import os
import pendulum
import pytest
import sys
import tempfile

from datetime import datetime, timedelta
from time import sleep, time
from unittest.mock import MagicMock

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
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.results import LocalResult, PrefectResult
from prefect.engine.result_handlers import (
    JSONResultHandler,
    ResultHandler,
    SecretResultHandler,
)
from prefect.engine.state import (
    Cached,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Queued,
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
    assert state.is_retrying()
    assert isinstance(state.start_time, datetime)
    assert state.run_count == 1

    # second run should retry
    state = task_runner.run(state=state)
    assert state.is_retrying()
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
    assert state.is_retrying()
    assert now - state.start_time < timedelta(seconds=0.1)

    state = TaskRunner(task=Retry5Min()).run()
    assert state.is_retrying()
    assert state.start_time == now + timedelta(minutes=5)


def test_task_that_raises_retry_with_naive_datetime_is_assumed_UTC():
    now = datetime.utcnow()
    assert now.tzinfo is None

    class Retry5Min(Task):
        def run(self):
            raise signals.RETRY(start_time=now + timedelta(minutes=5))

    state = TaskRunner(task=Retry5Min()).run()
    assert state.is_retrying()
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
    assert state.is_retrying()
    assert isinstance(state.start_time, datetime)

    # second run should also be retry because the task raises it explicitly

    with prefect.context(task_run_count=2):
        state = task_runner.run(state=state)
    assert state.is_retrying()


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


def test_task_runner_does_not_raise_when_task_signals():
    with raise_on_exception():
        state = TaskRunner(RaiseFailTask()).run()

    assert state.is_failed()


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


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_timeout_actually_stops_execution(executor):
    # Note: this is a potentially brittle test! In some cases (local and sync) signal.alarm
    # is used as the mechanism for timing out a task. This passes off the job of measuring
    # the time for the timeout to the OS, which uses the "wallclock" as reference (the real
    # amount of time passed in the real world). However, since the OS balances which processes
    # can use the CPU and for how long, it is possible when the CPU is strained for the
    # Python process running the Flow to not be given "enough" time on the CPU after the signal
    # alarm is registered with the OS. This could result in the Task.run() only percieving a small
    # amount of CPU time elapsed when in reality the full timeout period had elapsed.

    # For that reason, this test cannot validate timeout functionality by testing "how far into
    # the task implementation" we got, but instead do a simple task (create a file) and sleep.
    # This will drastically reduce the brittleness of the test (but not completely).

    with tempfile.TemporaryDirectory() as call_dir:
        # Note: a real file must be used in the case of "mthread"
        FILE = os.path.join(call_dir, "test.txt")

        @prefect.task(timeout=1)
        def slow_fn():
            with open(FILE, "w") as f:
                f.write("called!")
            sleep(2)
            with open(FILE, "a") as f:
                f.write("invalid")

        assert not os.path.exists(FILE)

        start_time = time()
        state = TaskRunner(slow_fn).run(executor=executor)
        stop_time = time()
        sleep(max(0, 3 - (stop_time - start_time)))

        assert os.path.exists(FILE)
        with open(FILE, "r") as f:
            assert "invalid" not in f.read()

    assert state.is_failed()
    assert isinstance(state, TimedOut)
    assert isinstance(state.result, TimeoutError)


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
    assert state.result == "my_private_str"


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


class TestContext:
    def test_task_runner_inits_with_current_context(self):
        runner = TaskRunner(Task())
        assert isinstance(runner.context, dict)
        assert "chris" not in runner.context

        with prefect.context(chris="foo"):
            runner2 = TaskRunner(Task())
            assert "chris" in runner2.context

        assert "chris" not in prefect.context
        assert runner2.context["chris"] == "foo"


class TestInitializeRun:
    @pytest.mark.parametrize(
        "state", [Success(), Failed(), Pending(), Scheduled(), Skipped(), Cached()]
    )
    def test_states_without_run_count(self, state):
        with prefect.context() as ctx:
            assert "task_run_count" not in ctx
            result = TaskRunner(Task()).initialize_run(state=state, context=ctx)
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
            result = TaskRunner(Task()).initialize_run(state=state, context=ctx)
            assert ctx.task_run_count == state.run_count + 1
            assert result.state is state

    def test_task_runner_puts_resume_in_context_if_state_is_resume(self):
        with prefect.context() as ctx:
            assert "resume" not in ctx
            result = TaskRunner(Task()).initialize_run(state=Resume(), context=ctx)
            assert result.context.resume is True

    def test_task_runner_puts_checkpointing_in_context(self):
        with prefect.context() as ctx:
            assert "checkpointing" not in ctx
            with set_temporary_config({"flows.checkpointing": "FOO"}):
                result = TaskRunner(Task()).initialize_run(state=None, context=ctx)
                assert result.context.checkpointing == "FOO"

    def test_task_runner_puts_task_slug_in_context(self):
        with prefect.context() as ctx:
            assert "task_slug" not in ctx
            result = TaskRunner(Task(slug="test-slug")).initialize_run(
                state=None, context=ctx
            )
            assert result.context.task_slug == "test-slug"

    def test_task_runner_puts_tags_in_context(self):
        with prefect.context() as ctx:
            assert "task_tags" not in ctx
            result = TaskRunner(Task()).initialize_run(state=None, context=ctx)
            assert result.context.task_tags == set()

        with prefect.context() as ctx:
            assert "task_tags" not in ctx
            result = TaskRunner(Task(tags=["foo", "bar"])).initialize_run(
                state=None, context=ctx
            )
            assert result.context.task_tags == {"foo", "bar"}

    @pytest.mark.parametrize(
        "state", [Success(), Failed(), Pending(), Scheduled(), Skipped(), Cached()]
    )
    def test_task_runner_doesnt_put_resume_in_context_if_state_is_not_resume(
        self, state
    ):
        with prefect.context() as ctx:
            assert "resume" not in ctx
            result = TaskRunner(Task()).initialize_run(state=state, context=ctx)
            assert "resume" not in result.context

    def test_unwrap_submitted_states(self):
        state = Scheduled()
        result = TaskRunner(Task()).initialize_run(
            state=Submitted(state=state), context={}
        )
        assert result.state is state

    def test_unwrap_queued_states(self):
        state = Retrying(run_count=1)
        result = TaskRunner(Task()).initialize_run(
            state=Queued(state=state), context={}
        )
        assert result.state is state

    def test_unwrap_nested_meta_states(self):
        state = Retrying(run_count=1)
        result = TaskRunner(Task()).initialize_run(
            state=Submitted(state=Queued(state=Submitted(state=Queued(state=state)))),
            context={},
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

    def test_raises_if_mapped_upstream_retrying(self):
        state = Pending()
        task = Task()
        with pytest.raises(ENDRUN) as exc:
            edge = Edge(1, 2, mapped=False)
            new_state = TaskRunner(task).check_upstream_finished(
                state=state,
                upstream_states={edge: Mapped(map_states=[Retrying(), Success()])},
            )

    def test_doesnt_raise_if_mapped_upstream_complete(self):
        state = Pending()
        task = Task()
        edge = Edge(1, 2, mapped=False)
        new_state = TaskRunner(task).check_upstream_finished(
            state=state,
            upstream_states={edge: Mapped(map_states=[Failed(), Success()])},
        )
        assert new_state is state


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

    def test_raises_if_single_mapped_upstream_skipped(self):
        state = Pending()
        task = Task()
        with pytest.raises(ENDRUN) as exc:
            edge = Edge(1, 2, mapped=False)
            new_state = TaskRunner(task).check_upstream_skipped(
                state=state,
                upstream_states={edge: Mapped(map_states=[Skipped(), Success()])},
            )

    def test_doesnt_raise_if_single_mapped_upstream_skipped_and_edge_is_mapped(self):
        state = Pending()
        task = Task()
        edge = Edge(1, 2, mapped=True)
        new_state = TaskRunner(task).check_upstream_skipped(
            state=state,
            upstream_states={edge: Mapped(map_states=[Skipped(), Success()])},
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
        with pytest.raises(ENDRUN) as exc:
            new_state = TaskRunner(task).check_task_trigger(
                state=state, upstream_states={}
            )
        assert isinstance(exc.value.state, Paused)

    def test_manual_passes_when_context_is_resume(self):
        task = Task(trigger=prefect.triggers.manual_only)
        state = Pending()
        with prefect.context(resume=True):
            new_state = TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success()}
            )
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

    def test_custom_trigger_returns_false(self):
        def trigger(states):
            return False

        task = Task(trigger=trigger)
        state = Pending()
        with pytest.raises(ENDRUN) as exc:
            TaskRunner(task).check_task_trigger(
                state=state, upstream_states={1: Success()}
            )
        assert isinstance(exc.value.state, TriggerFailed)


class TestCheckTaskReady:
    @pytest.mark.parametrize(
        "state", [Cached(), Pending(), Mapped(), Paused(), Scheduled()]
    )
    def test_ready_states(self, state):
        new_state = TaskRunner(task=Task()).check_task_is_ready(state=state)
        assert new_state is state

    @pytest.mark.parametrize(
        "state", [Running(), Finished(), TriggerFailed(), Skipped(), Success()]
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

    def test_cached_inputs_overwrites_upstream_states_if_they_are_noresult(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(cached_inputs={"x": Result(value=1), "y": Result(value=2)}),
            upstream_states={
                Edge(1, 2, key="x"): Success(),
                Edge(1, 2, key="y"): Success(),
            },
        )
        assert inputs == {"x": Result(1), "y": Result(2)}

    def test_cached_inputs_doesnt_overwrites_upstream_states_if_hydrated(self):
        inputs = TaskRunner(task=Task()).get_task_inputs(
            state=Pending(cached_inputs={"x": Result(value=1), "y": Result(value=2)}),
            upstream_states={
                Edge(1, 2, key="x"): Success(result=None),
                Edge(1, 2, key="y"): Success(result=5),
            },
        )
        assert inputs["x"].value == None
        assert inputs["y"].value == 5


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

    def test_reads_result_from_context_if_cached_valid(self):
        task = Task(
            cache_for=timedelta(minutes=1),
            cache_validator=cache_validators.duration_only,
            result=PrefectResult(),
        )

        result = PrefectResult(value=2)

        state = Cached(
            result=result,
            cached_result_expiration=pendulum.now("utc") + timedelta(minutes=1),
        )

        with prefect.context(caches={"Task": [state]}):
            new = TaskRunner(task).check_task_is_cached(
                state=Pending(), inputs={"a": Result(1)}
            )
        assert new is state
        assert new.result == 2

    def test_state_kwarg_is_prioritized_over_context_caches(self):
        task = Task(
            cache_for=timedelta(minutes=1),
            cache_validator=cache_validators.duration_only,
            result=PrefectResult(),
        )
        state_a = Cached(
            result=PrefectResult(value=2),
            cached_result_expiration=pendulum.now("utc") + timedelta(minutes=1),
        )
        state_b = Cached(
            result=PrefectResult(value=99),
            cached_result_expiration=pendulum.now("utc") + timedelta(minutes=1),
        )

        with prefect.context(caches={"Task": [state_a]}):
            new = TaskRunner(task).check_task_is_cached(
                state=state_b, inputs={"a": Result(1)}
            )
        assert new is state_b
        assert new.result == 99

    def test_reads_result_from_context_with_cache_key_if_cached_valid(self):
        task = Task(
            cache_for=timedelta(minutes=1),
            cache_validator=cache_validators.duration_only,
            cache_key="FOO",
        )
        result = PrefectResult(value=2)
        state = Cached(
            result=result,
            cached_result_expiration=pendulum.now("utc") + timedelta(minutes=1),
        )

        with prefect.context(caches={"FOO": [state]}):
            new = TaskRunner(task).check_task_is_cached(
                state=Pending(), inputs={"a": Result(1)}
            )
        assert new is state
        assert new.result == 2

    def test_all_of_run_context_is_available_to_custom_cache_validators(self):
        ctxt = dict()

        def custom_validator(state, inputs, parameters):
            ctxt.update(prefect.context.to_dict())
            return False

        # have to have a state worth checking to trigger the validator
        with prefect.context(caches={"Task": [State()]}):
            task = Task(
                cache_for=timedelta(seconds=10), cache_validator=custom_validator
            )
            state = TaskRunner(task).run()

        expected_subset = dict(
            map_index=None,
            task_full_name="Task",
            task_run_count=1,
            task_name="Task",
            task_tags=set(),
            task_slug=task.slug,
            checkpointing=False,
        )
        for key, val in expected_subset.items():
            assert ctxt[key] == val

        assert "config" in ctxt
        assert ctxt["logger"] is task.logger


class TestSetTaskRunning:
    @pytest.mark.parametrize("state", [Pending()])
    def test_pending(self, state):
        new_state = TaskRunner(task=Task()).set_task_to_running(
            state=state, inputs=dict()
        )
        assert new_state.is_running()
        assert new_state.cached_inputs == dict()

    @pytest.mark.parametrize("state", [Pending()])
    def test_inputs_are_cached(self, state):
        new_state = TaskRunner(task=Task()).set_task_to_running(
            state=state, inputs=dict(x=Result(42))
        )
        assert new_state.is_running()
        assert new_state.cached_inputs == dict(x=Result(42))

    @pytest.mark.parametrize("state", [Cached(), Running(), Success(), Skipped()])
    def test_not_pending(self, state):
        with pytest.raises(ENDRUN):
            TaskRunner(task=Task()).set_task_to_running(state=state, inputs=dict())


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

    def test_raise_loop_signal(self):
        @prefect.task
        def fn():
            raise signals.LOOP(result=1)

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert new_state.is_looped()
        assert new_state.result == 1
        assert new_state.loop_count == 1
        assert "looping" in new_state.message

    def test_raise_loop_signal_with_custom_message(self):
        @prefect.task
        def fn():
            raise signals.LOOP(message="My message")

        state = Running()
        new_state = TaskRunner(task=fn).get_task_run_state(
            state=state, inputs={}, timeout_handler=None
        )
        assert new_state.is_looped()
        assert "LOOP" in new_state.result
        assert new_state.loop_count == 1
        assert new_state.message == "My message"

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
        assert state._result == Result(value=None)

    def test_returns_success_with_correct_result_type(self):
        runner = TaskRunner(task=Task(result=PrefectResult()))
        state = runner.get_task_run_state(
            state=Running(), inputs={}, timeout_handler=None
        )
        assert state.is_successful()
        assert isinstance(state._result, PrefectResult)

    def test_success_state_without_checkpoint(self):
        @prefect.task(checkpoint=False)
        def fn(x):
            return x + 1

        with prefect.context(checkpointing=True):
            new_state = TaskRunner(task=fn, result=PrefectResult()).get_task_run_state(
                state=Running(), inputs={"x": Result(1)}, timeout_handler=None
            )
        assert new_state.is_successful()
        assert new_state._result.location is None

    @pytest.mark.parametrize("checkpoint", [True, None])
    def test_success_state_with_checkpointing_in_config(self, checkpoint):
        @prefect.task(checkpoint=checkpoint, result=PrefectResult())
        def fn(x):
            return x + 1

        edge = Edge(Task(), fn, key="x")
        with set_temporary_config({"flows.checkpointing": True}):
            new_state = TaskRunner(task=fn).run(
                state=None, upstream_states={edge: Success(result=Result(2))}
            )
        assert new_state.is_successful()
        assert new_state._result.location == "3"

    @pytest.mark.parametrize("checkpoint", [True, None])
    def test_success_state_with_checkpointing_in_context(self, checkpoint):
        @prefect.task(checkpoint=checkpoint, result=PrefectResult())
        def fn(x):
            return x + 1

        with prefect.context(checkpointing=True):
            new_state = TaskRunner(task=fn).get_task_run_state(
                state=Running(), inputs={"x": Result(2)}, timeout_handler=None
            )
        assert new_state.is_successful()
        assert new_state._result.location == "3"

    @pytest.mark.parametrize("checkpoint", [True, None])
    def test_success_state_is_checkpointed_if_result_handler_present(self, checkpoint):
        @prefect.task(checkpoint=checkpoint, result=PrefectResult())
        def fn():
            return 1

        ## checkpointing allows users to toggle behavior for local testing
        with prefect.context(checkpointing=False):
            new_state = TaskRunner(task=fn).get_task_run_state(
                state=Running(), inputs={}, timeout_handler=None
            )
        assert new_state.is_successful()
        assert new_state._result.location is None

        with prefect.context(checkpointing=True):
            new_state = TaskRunner(task=fn).get_task_run_state(
                state=Running(), inputs={}, timeout_handler=None
            )
        assert new_state.is_successful()
        assert new_state._result.location == "1"

    def test_success_state_for_parameter(self):
        p = prefect.Parameter("p", default=2)
        with prefect.context(checkpointing=True):
            new_state = TaskRunner(task=p).get_task_run_state(
                state=Running(), inputs={}, timeout_handler=None
            )
        assert new_state.is_successful()
        assert new_state._result.location == "2"

    @pytest.mark.parametrize("checkpoint", [True, None])
    def test_success_state_with_bad_result_results_in_failed_state(self, checkpoint):
        class BadResult(Result):
            def read(self, *args, **kwargs):
                pass

            def write(self, *args, **kwargs):
                raise SyntaxError("Oh boy")

        @prefect.task(checkpoint=checkpoint, result=BadResult())
        def fn(x):
            return x + 1

        with prefect.context(checkpointing=True):
            new_state = TaskRunner(task=fn).get_task_run_state(
                state=Running(), inputs={"x": Result(1)}, timeout_handler=None
            )
        assert new_state.is_failed()
        assert "SyntaxError" in new_state.message

    def test_success_state_with_bad_result_and_checkpointing_disabled(self):
        class BadResult(Result):
            def read(self, *args, **kwargs):
                pass

            def write(self, *args, **kwargs):
                raise SyntaxError("Oh boy")

        @prefect.task(checkpoint=False, result=BadResult())
        def fn(x):
            return x + 1

        with prefect.context(checkpointing=True):
            new_state = TaskRunner(task=fn).get_task_run_state(
                state=Running(), inputs={"x": Result(1)}, timeout_handler=None
            )
        assert new_state.is_successful()


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
        assert new_state.is_retrying()
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
        assert new_state.is_retrying()
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
        "state",
        [
            Failed(result=1),
            Skipped(result=1),
            Finished(result=1),
            Pending(result=1),
            Running(result=1),
        ],
    )
    def test_non_success_states_with_results(self, state):
        new_state = TaskRunner(task=Task()).cache_result(state=state, inputs={})
        assert new_state is state
        assert new_state._result.location is None

    @pytest.mark.parametrize(
        "state", [cls() for cls in Failed.__subclasses__() + [Failed]]
    )
    def test_non_success_states(self, state):
        new_state = TaskRunner(task=Task()).cache_result(
            state=state, inputs={"x": Result(1)}
        )
        assert new_state is state
        assert new_state._result is NoResult
        assert new_state.cached_inputs == {"x": Result(1)}

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

    def test_success_state_with_cache_for(self):
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


class TestTargetExistsStep:
    @pytest.fixture(scope="class")
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.mark.parametrize(
        "state",
        [
            Failed(result=1),
            Skipped(result=1),
            Finished(result=1),
            Pending(result=1),
            Running(result=1),
        ],
    )
    def test_check_target(self, state):
        new_state = TaskRunner(task=Task()).check_target(state=state, inputs={})
        assert new_state is state
        assert new_state._result.location is None

    def test_check_target_calls_state_handlers(self):
        glob = []

        def sh(obj, old, new):
            glob.append(new)

        res = PrefectResult(location="42")
        state = Pending()
        new_state = TaskRunner(
            task=Task(target="42", result=res, state_handlers=[sh])
        ).check_target(state=state, inputs={})

        assert new_state.is_cached()
        assert new_state.result == 42
        assert len(glob) == 1

    @pytest.mark.parametrize(
        "state",
        [
            Failed(result=1),
            Skipped(result=1),
            Finished(result=1),
            Pending(result=1),
            Running(result=1),
        ],
    )
    def test_check_target_not_exists(self, state):
        new_state = TaskRunner(
            task=Task(target="test-file", result=PrefectResult())
        ).check_target(state=state, inputs={})
        assert new_state is state
        assert new_state._result.location is None

    def test_check_target_exists(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, location="test-file")
        result.write(1)

        my_task = Task(target="test-file", result=result)

        new_state = TaskRunner(task=my_task).check_target(
            state=Running(result=result), inputs={}
        )

        assert result.exists("test-file")
        assert new_state.is_cached()
        assert new_state._result.location == "test-file"
        assert new_state.message == "Result found at task target test-file"

    def test_check_target_exists_multiple_checks(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, location="test-file")
        result.write(1)

        my_task = Task(target="test-file", result=result)

        new_state = TaskRunner(task=my_task).check_target(
            state=Running(result=result), inputs={}
        )

        assert result.exists("test-file")
        assert new_state.is_cached()
        assert new_state._result.location == "test-file"

        new_state_2 = TaskRunner(task=my_task).check_target(state=new_state, inputs={})

        assert result.exists("test-file")
        assert new_state_2.is_cached()
        assert new_state_2._result.location == "test-file"


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
            Scheduled(start_time=pendulum.now("utc").add(minutes=10)),
            Retrying(start_time=pendulum.now("utc").add(minutes=10)),
            Paused(),
            Paused(start_time=None),
            Paused(start_time=pendulum.now("utc").add(minutes=10)),
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
        assert [type(s[0][-1]).__name__ for s in task_handler.call_args_list] == [
            "Running",
            "Success",
        ]

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

    def test_task_handlers_can_return_none(self):
        task_handler = MagicMock(side_effect=lambda t, o, n: None)

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
        task = Task(state_handlers=[lambda *a: True, task_handler])
        with pytest.raises(AssertionError):
            with prefect.utilities.debug.raise_on_exception():
                TaskRunner(task=task).run()

    def test_task_handler_that_doesnt_return_state_or_none(self):
        # this will raise an error because no state is returned
        task = Task(state_handlers=[lambda *a: True])
        with pytest.raises(AttributeError):
            with prefect.utilities.debug.raise_on_exception():
                TaskRunner(task=task).run()

    def test_task_handler_errors_are_logged(self, caplog):
        def handler(*args, **kwargs):
            raise SyntaxError("oops")

        task = Task(state_handlers=[handler])
        state = TaskRunner(task=task).run()

        assert state.is_failed()

        error_logs = [r.message for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_logs) >= 1
        assert "SyntaxError" in error_logs[0]
        assert "oops" in error_logs[0]
        assert "state handler" in error_logs[0]


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
        assert state.is_retrying()
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
        # the parent task changed state two times: Pending -> Mapped -> Mapped
        # the child task changed state one time: Pending -> Running -> Success
        assert isinstance(state, Mapped)
        assert task_runner_handler.call_count == 4

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

    def test_task_runner_handler_that_doesnt_return_state_or_none(self):
        # raises an error because the state handler doesn't return a state
        with pytest.raises(AttributeError):
            with prefect.utilities.debug.raise_on_exception():
                TaskRunner(task=Task(), state_handlers=[lambda *a: True]).run()

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
            context={},
            executor=prefect.engine.executors.LocalExecutor(),
        )

    @pytest.mark.parametrize("state", [Pending(), Mapped(), Scheduled()])
    def test_run_mapped_returns_mapped(self, state):
        state = TaskRunner(task=Task()).run_mapped_task(
            state=state,
            upstream_states={},
            context={},
            executor=prefect.engine.executors.LocalExecutor(),
        )
        assert state.is_mapped()

    def test_run_mapped_preserves_result_objects(self):
        @prefect.task(cache_for=timedelta(minutes=10))
        def tt(foo):
            pass

        with prefect.context(checkpointing=True, caches={}):
            state = TaskRunner(task=tt).run_mapped_task(
                state=Pending(),
                upstream_states={
                    Edge(Task(), tt, key="foo", mapped=True): Success(
                        result=Result([1, 2], result_handler=JSONResultHandler())
                    )
                },
                context={},
                executor=prefect.engine.executors.LocalExecutor(),
            )
        assert state.is_mapped()

        one, two = state.map_states
        assert one.cached_inputs["foo"] == Result(1, result_handler=JSONResultHandler())
        assert two.cached_inputs["foo"] == Result(2, result_handler=JSONResultHandler())

    def test_run_mapped_preserves_context(self):
        @prefect.task
        def ctx():
            return prefect.context.get("special_thing")

        with prefect.context(special_thing="FOOBARRR"):
            runner = TaskRunner(task=ctx)

        state = runner.run_mapped_task(
            state=Pending(),
            upstream_states={Edge(Task(), ctx, mapped=True): Success(result=[1, 2])},
            context={},
            executor=prefect.engine.executors.LocalExecutor(),
        )
        assert state.is_mapped()
        assert [s.result for s in state.map_states] == ["FOOBARRR"] * 2


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
    executor,
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


def test_task_runner_passes_manual_only_trigger_when_resume_state_is_passed():
    t1, t2 = SuccessTask(), SuccessTask(trigger=prefect.triggers.manual_only)
    e = Edge(t1, t2)
    runner = TaskRunner(t2)
    out = runner.run(state=Resume(), upstream_states={e: Success(result=1)})
    assert isinstance(out, Success)


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
    # the parent task changed state two times: Pending -> Mapped -> Mapped
    # the child task changed state one time: Pending -> TriggerFailed
    assert isinstance(state, Mapped)
    assert task_runner_handler.call_count == 3
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

    assert state.is_retrying()
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


@pytest.mark.parametrize("checkpoint", [True, None])
def test_failures_arent_checkpointed(checkpoint):
    handler = MagicMock(store_safe_value=MagicMock(side_effect=SyntaxError))

    @prefect.task(checkpoint=checkpoint, result_handler=handler)
    def fn():
        raise TypeError("Bad types")

    with prefect.context(checkpointing=True):
        new_state = TaskRunner(task=fn).run()
    assert new_state.is_failed()
    assert isinstance(new_state.result, TypeError)


@pytest.mark.parametrize("checkpoint", [True, None])
def test_skips_arent_checkpointed(checkpoint):
    handler = MagicMock(store_safe_value=MagicMock(side_effect=SyntaxError))

    @prefect.task(checkpoint=checkpoint, result_handler=handler)
    def fn():
        return 2

    with prefect.context(checkpointing=True):
        new_state = TaskRunner(task=fn).run(
            upstream_states={Edge(Task(), Task()): Skipped()}
        )
    assert new_state.is_successful()


def test_task_runner_provides_logger():
    @prefect.task()
    def my_task():
        logger = prefect.context.get("logger")
        return logger

    state = TaskRunner(my_task).run()
    assert state.is_successful()
    assert state.result is my_task.logger


class TestLooping:
    def test_looping_works(self):
        @prefect.task
        def my_task():
            if prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP()
            else:
                return 42

        state = TaskRunner(my_task).run()
        assert state.is_successful()
        assert state.result == 42

    def test_looping_calls_state_handlers_appropriately(self):
        glob = []

        def sh(obj, old, new):
            glob.append(new)

        @prefect.task(state_handlers=[sh])
        def my_task():
            if prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP()
            else:
                return 42

        state = TaskRunner(my_task).run()
        assert state.is_successful()
        assert state.result == 42

        assert len(glob) == 6
        assert len([s for s in glob if s.is_looped()]) == 2
        assert len([s for s in glob if s.is_running()]) == 3
        assert len([s for s in glob if s.is_successful()]) == 1

    def test_looping_doesnt_aggressively_log_task_starting(self, caplog):
        @prefect.task
        def my_task():
            if prefect.context.get("task_loop_count", 1) < 10:
                raise signals.LOOP()
            else:
                return 42

        state = TaskRunner(my_task).run()
        logs = [
            log
            for log in caplog.records
            if "TaskRunner" in log.name and "Starting" in log.message
        ]
        assert len(logs) >= 1

    def test_looping_doesnt_aggressively_log_task_finished(self, caplog):
        @prefect.task
        def my_task():
            if prefect.context.get("task_loop_count", 1) < 10:
                raise signals.LOOP()
            else:
                return 42

        state = TaskRunner(my_task).run()
        logs = [
            log
            for log in caplog.records
            if "TaskRunner" in log.name and "finished" in log.message
        ]
        assert len(logs) >= 1  # a finished log was in fact created
        assert len(logs) <= 2  # but not too many were issued

    def test_looping_accumulates(self):
        @prefect.task
        def my_task():
            curr = prefect.context.get("task_loop_result", 0)
            if prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP(result=curr + 1)
            else:
                return curr + 1

        state = TaskRunner(my_task).run()
        assert state.is_successful()
        assert state.result == 3

    @pytest.mark.parametrize("checkpoint", [True, None])
    def test_looping_only_checkpoints_the_final_result(self, checkpoint):
        class Handler(ResultHandler):
            data = []

            def write(self, obj):
                self.data.append(obj)
                return self.data.index(obj)

            def read(self, idx):
                return self.data[idx]

        handler = Handler()

        @prefect.task(checkpoint=checkpoint, result_handler=handler)
        def my_task():
            curr = prefect.context.get("task_loop_result", 0)
            if prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP(result=curr + 1)
            else:
                return curr + 1

        state = TaskRunner(my_task).run(context={"checkpointing": True})
        assert state.is_successful()
        assert state.result == 3
        assert handler.data == [3]

    def test_looping_works_with_retries(self):
        @prefect.task(max_retries=2, retry_delay=timedelta(seconds=0))
        def my_task():
            if prefect.context.get("task_loop_count", 1) == 2:
                if prefect.context.get("task_run_count", 1) > 1:
                    return 42
                raise SyntaxError("failure")
            elif prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP()

        runner = TaskRunner(my_task)
        state = runner.run()
        assert state.is_retrying()

        state = runner.run(state=state)
        assert state.is_successful()

    def test_loop_results_work_with_retries(self):
        @prefect.task(max_retries=2, retry_delay=timedelta(seconds=0))
        def my_task():
            if prefect.context.get("task_loop_count", 1) == 3:
                if prefect.context.get("task_run_count", 1) > 1:
                    return prefect.context.get("task_loop_result")
                raise SyntaxError("failure")
            elif prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP(
                    result=prefect.context.get("task_loop_result", 0) + 1
                )

        runner = TaskRunner(my_task)
        state = runner.run()
        assert state.is_retrying()

        state = runner.run(state=state)
        assert state.is_successful()
        assert state.result == 2

    def test_looping_works_with_mapping(self):
        @prefect.task
        def my_task(i):
            if prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP(
                    result=prefect.context.get("task_loop_result", i) + 3
                )
            return prefect.context.get("task_loop_result")

        runner = TaskRunner(my_task)
        state = runner.run(
            upstream_states={Edge(1, 2, key="i", mapped=True): Success(result=[1, 20])}
        )

        assert state.is_mapped()
        assert [s.result for s in state.map_states] == [7, 26]

    def test_looping_works_with_mapping_and_individual_retries(self):
        @prefect.task(max_retries=1, retry_delay=timedelta(seconds=0))
        def my_task(i):
            if prefect.context.get("task_loop_result") == 4:
                raise ValueError("Can't do 4")
            if prefect.context.get("task_loop_count", 1) < 3:
                raise signals.LOOP(
                    result=prefect.context.get("task_loop_result", i) + 3
                )
            return prefect.context.get("task_loop_result")

        runner = TaskRunner(my_task)
        state = runner.run(
            upstream_states={Edge(1, 2, key="i", mapped=True): Success(result=[1, 20])}
        )

        assert state.is_mapped()
        state.map_states[0].is_retrying()
        state.map_states[1].is_successful()


def test_failure_caches_inputs():
    @prefect.task
    def fail(x):
        raise ValueError()

    upstream_states = {Edge(Task(), fail, key="x"): Success(result=Result(1))}
    new_state = TaskRunner(task=fail).run(upstream_states=upstream_states)
    assert new_state.is_failed()
    assert new_state.cached_inputs == {"x": Result(1)}


def test_task_tags_are_attached_to_all_states():
    task_handler = MagicMock(side_effect=lambda t, o, n: n)
    task = Task(state_handlers=[task_handler], tags=["alice", "bob"])
    TaskRunner(task=task).run()

    states = [s[0][-1] for s in task_handler.call_args_list]
    assert all(set(state.context["tags"]) == set(["alice", "bob"]) for state in states)


def test_task_runner_logs_stdout(caplog):
    class MyTask(Task):
        def run(self):
            print("TEST_HERE")

    task = MyTask(log_stdout=True)
    TaskRunner(task=task).run()

    logs = [r.message for r in caplog.records]
    assert logs[1] == "TEST_HERE"


def test_task_runner_logs_stdout_disabled(caplog):
    class MyTask(Task):
        def run(self):
            print("TEST_HERE")

    task = MyTask()
    TaskRunner(task=task).run()

    logs = [r.message for r in caplog.records]
    assert "TEST_HERE" not in logs


def test_task_runner_logs_map_index_for_mapped_tasks(caplog):
    class MyTask(Task):
        def run(self):
            map_index = prefect.context.get("map_index")
            self.logger.info("{}".format(map_index))

    task = MyTask()
    edge = Edge(Task(), task, mapped=True)
    new_state = TaskRunner(task=task).run(
        state=None, upstream_states={edge: Success(result=Result(list(range(10))))}
    )

    logs = [r.message for r in caplog.records if "prefect.Task:" in r.message]
    task_name = task.name
    for line in logs:
        msg = line.split("INFO")[1]
        logged_map_index = msg[-1]
        assert msg.count(logged_map_index) == 2
