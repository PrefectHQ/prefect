import cloudpickle
import datetime
import tempfile
import uuid

import pendulum
import pytest

from collections import defaultdict

import prefect
from prefect.engine.result import Result, NoResult
from prefect.engine.result_handlers import JSONResultHandler, LocalResultHandler
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
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.serialization.state import StateSchema

all_states = sorted(
    set(
        cls
        for cls in prefect.engine.state.__dict__.values()
        if isinstance(cls, type) and issubclass(cls, prefect.engine.state.State)
    ),
    key=lambda c: c.__name__,
)

cached_input_states = sorted(
    set(cls for cls in all_states if hasattr(cls(), "cached_inputs")),
    key=lambda c: c.__name__,
)


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_no_args(cls):
    state = cls()
    assert state.message is None
    assert state.result == NoResult


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_kwarg_data_arg(cls):
    state = cls(result=1)
    assert isinstance(state._result, Result)
    assert state._result.handled is False
    assert state._result.result_handler is None
    assert state.result == 1
    assert state.message is None
    assert isinstance(state._result, Result)


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_fully_hydrated_result(cls):
    result = Result(value=10)
    state = cls(result=result)
    assert isinstance(state._result, Result)
    assert state._result.value == 10
    assert state.result == 10


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_positional_message_arg(cls):
    state = cls("i am a string")
    assert state.message == "i am a string"
    assert state._result == NoResult


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_data_and_message(cls):
    state = cls(message="x", result="y")
    assert state.result == "y"
    assert state.message == "x"


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_data_and_error(cls):
    try:
        1 / 0
    except Exception as e:
        state = cls(result="oh no!", message=e)
    assert state.result == "oh no!"
    assert isinstance(state.message, Exception)
    assert "division by zero" in str(state.message)


def test_scheduled_states_have_default_times():
    now = pendulum.now("utc")
    assert now - Scheduled().start_time < datetime.timedelta(seconds=0.1)
    assert now - Retrying().start_time < datetime.timedelta(seconds=0.1)


@pytest.mark.parametrize("cls", all_states)
def test_only_scheduled_states_have_start_times(cls):
    """
    the start_time attribute of a scheduled state is important and used (outside Python)
    to identify when a state is scheduled
    """
    state = cls()
    if hasattr(state, "start_time"):
        assert isinstance(state, Scheduled)
        assert state.is_scheduled()
    else:
        assert not isinstance(state, Scheduled)
        assert not state.is_scheduled()


def test_retry_stores_run_count():
    state = Retrying(run_count=2)
    assert state.run_count == 2


def test_retry_stores_default_run_count():
    state = Retrying()
    assert state.run_count == 1


def test_retry_stores_default_run_count_in_context():
    with prefect.context(task_run_count=5):
        state = Retrying()
    assert state.run_count == 5


@pytest.mark.parametrize("cls", all_states)
def test_states_have_color(cls):
    assert cls.color.startswith("#")


def test_serialize_and_deserialize_on_cached_state():
    now = pendulum.now("utc")
    state = Cached(
        cached_inputs=dict(x=Result(99), p=Result("p")),
        result=dict(hi=5, bye=6),
        cached_result_expiration=now,
    )
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, Cached)
    assert new_state.color == state.color
    assert new_state.result == dict(hi=5, bye=6)
    assert new_state.cached_result_expiration == state.cached_result_expiration
    assert new_state.cached_inputs == state.cached_inputs


def test_serialization_of_cached_inputs():
    state = Pending(cached_inputs=dict(hi=Result(5), bye=Result(6)))
    serialized = state.serialize()
    new_state = State.deserialize(serialized)
    assert isinstance(new_state, Pending)
    assert new_state.cached_inputs == state.cached_inputs


def test_state_equality():
    assert State() == State()
    assert Success() == Success()
    assert Success(result=1) == Success(result=1)
    assert not State() == Success()
    assert not Success(result=1) == Success(result=2)
    assert Pending(cached_inputs=dict(x=1)) == Pending(cached_inputs=dict(x=1))
    assert not Pending(cached_inputs=dict(x=1)) == Pending(cached_inputs=dict(x=2))
    assert not Pending(cached_inputs=dict(x=1)) == Pending(cached_inputs=dict(y=1))


def test_state_equality_ignores_message():
    assert State(result=1, message="x") == State(result=1, message="y")
    assert State(result=1, message="x") != State(result=2, message="x")


def test_state_equality_with_nested_states():
    s1 = State(result=Success(result=1))
    s2 = State(result=Success(result=2))
    s3 = State(result=Success(result=1))
    assert s1 != s2
    assert s1 == s3


def test_states_are_hashable():
    assert {State(), Pending(), Success()}


def test_states_with_mutable_attrs_are_hashable():
    assert {State(result=[1]), Pending(cached_inputs=dict(a=1))}


@pytest.mark.parametrize("cls", [s for s in all_states if s is not State])
def test_serialize_method(cls):
    serialized = cls().serialize()
    assert isinstance(serialized, dict)
    assert isinstance(prefect.serialization.state.StateSchema().load(serialized), cls)


class TestStateHierarchy:
    def test_scheduled_is_pending(self):
        assert issubclass(Scheduled, Pending)

    def test_resume_is_scheduled(self):
        assert issubclass(Resume, Scheduled)

    def test_mapped_is_success(self):
        assert issubclass(Mapped, Success)

    def test_cached_is_successful(self):
        assert issubclass(Cached, Success)

    def test_retrying_is_pending(self):
        assert issubclass(Retrying, Pending)

    def test_retrying_is_scheduled(self):
        assert issubclass(Retrying, Scheduled)

    def test_success_is_finished(self):
        assert issubclass(Success, Finished)

    def test_failed_is_finished(self):
        assert issubclass(Failed, Finished)

    def test_trigger_failed_is_finished(self):
        assert issubclass(TriggerFailed, Finished)

    def test_timedout_is_finished(self):
        assert issubclass(TimedOut, Finished)

    def test_skipped_is_finished(self):
        assert issubclass(Skipped, Finished)

    def test_skipped_is_success(self):
        assert issubclass(Skipped, Success)

    def test_timedout_is_failed(self):
        assert issubclass(TimedOut, Failed)

    def test_trigger_failed_is_failed(self):
        assert issubclass(TriggerFailed, Failed)


class TestStateMethods:
    def test_state_type_methods_with_pending_state(self):
        state = Pending()
        assert state.is_pending()
        assert not state.is_cached()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_paused_state(self):
        state = Paused()
        assert state.is_pending()
        assert not state.is_cached()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_scheduled_state(self):
        state = Scheduled()
        assert state.is_pending()
        assert not state.is_cached()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_resume_state(self):
        state = Resume()
        assert state.is_pending()
        assert not state.is_cached()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_retry_state(self):
        state = Retrying()
        assert state.is_pending()
        assert not state.is_cached()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_submitted_state(self):
        state = Submitted()
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_running_state(self):
        state = Running()
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_cached()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_cached_state(self):
        state = Cached()
        assert state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_mapped_state(self):
        state = Mapped()
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()
        assert state.is_mapped()

    def test_state_type_methods_with_success_state(self):
        state = Success()
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_failed_state(self):
        state = Failed(message="")
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_timedout_state(self):
        state = TimedOut(message="")
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_trigger_failed_state(self):
        state = TriggerFailed(message="")
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_mapped()

    def test_state_type_methods_with_skipped_state(self):
        state = Skipped()
        assert not state.is_cached()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_mapped()
