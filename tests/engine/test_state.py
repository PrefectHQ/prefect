import datetime

import pytest
import prefect
from prefect.engine.state import (
    CachedState,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TriggerFailed,
)
from prefect.utilities import json

all_states = set(
    cls
    for cls in prefect.engine.state.__dict__.values()
    if isinstance(cls, type) and issubclass(cls, prefect.engine.state.State)
)


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_no_args(cls):
    state = cls()
    assert state.result is None
    assert state.message is None


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_kwarg_data_arg(cls):
    state = cls(result=1)
    assert state.result == 1
    assert state.message is None


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_positional_message_arg(cls):
    state = cls("i am a string")
    assert state.message == "i am a string"
    assert state.result is None


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
    now = datetime.datetime.utcnow()
    assert now - Scheduled().start_time < datetime.timedelta(seconds=0.1)
    assert now - Retrying().start_time < datetime.timedelta(seconds=0.1)


def test_retry_stores_run_count():
    state = Retrying(run_count=2)
    assert state.run_count == 2


def test_retry_stores_default_run_count():
    state = Retrying()
    assert state.run_count == 1


def test_retry_stores_default_run_count_in_context():
    with prefect.context(_task_run_count=5):
        state = Retrying()
    assert state.run_count == 5


@pytest.mark.parametrize("cls", all_states)
def test_states_have_color(cls):
    assert cls.color.startswith("#")


def test_serialize():
    now = datetime.datetime.utcnow()
    cached = CachedState(
        cached_inputs=dict(x=99, p="p"),
        cached_result=dict(hi=5, bye=6),
        cached_result_expiration=now,
    )
    state = Success(result=dict(hi=5, bye=6), cached=cached)
    j = json.dumps(state)
    new_state = json.loads(j)
    assert isinstance(new_state, Success)
    assert new_state.color == state.color
    assert new_state.result == state.result
    assert isinstance(new_state.cached, CachedState)
    assert new_state.cached.cached_result_expiration == cached.cached_result_expiration
    assert new_state.cached.cached_inputs == cached.cached_inputs
    assert new_state.cached.cached_result == cached.cached_result


def test_serialization_of_cached_inputs():
    state = Pending(cached_inputs=dict(hi=5, bye=6))
    j = json.dumps(state)
    new_state = json.loads(j)
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
    assert isinstance(
        prefect.serialization.schemas.state.StateSchema().load(serialized), cls
    )


class TestStateHierarchy:
    def test_scheduled_is_pending(self):
        assert issubclass(Scheduled, Pending)

    def test_mapped_is_success(self):
        assert issubclass(Mapped, Success)

    def test_cached_is_pending(self):
        assert issubclass(CachedState, Pending)

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

    def test_skipped_is_finished(self):
        assert issubclass(Skipped, Finished)

    def test_skipped_is_success(self):
        assert issubclass(Skipped, Success)

    def test_trigger_failed_is_failed(self):
        assert issubclass(TriggerFailed, Failed)


class TestStateMethods:
    def test_state_type_methods_with_pending_state(self):
        state = Pending()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_paused_state(self):
        state = Paused()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_scheduled_state(self):
        state = Scheduled()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_retry_state(self):
        state = Retrying()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_running_state(self):
        state = Running()
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_cached_state(self):
        state = CachedState()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_mapped_state(self):
        state = Mapped()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_success_state(self):
        state = Success()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_failed_state(self):
        state = Failed(message="")
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert state.is_failed()

    def test_state_type_methods_with_trigger_failed_state(self):
        state = TriggerFailed(message="")
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_skipped()
        assert not state.is_scheduled()
        assert not state.is_successful()
        assert state.is_failed()

    def test_state_type_methods_with_skipped_state(self):
        state = Skipped()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_skipped()
        assert not state.is_scheduled()
        assert state.is_successful()
        assert not state.is_failed()
