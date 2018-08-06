import datetime
from prefect.utilities import json

import pytest

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

all_states = [
    CachedState,
    State,
    Pending,
    Running,
    Finished,
    Success,
    Skipped,
    Failed,
    TriggerFailed,
    Scheduled,
    Retrying,
]


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_no_args(cls):
    state = cls()
    assert state.result is None
    assert state.message is None


@pytest.mark.parametrize("cls", all_states)
def test_create_state_with_positional_data_arg(cls):
    state = cls(1)
    assert state.result == 1
    assert state.message is None


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


def test_timestamp_is_created_at_creation():
    state = Success()
    assert (datetime.datetime.utcnow() - state.timestamp).total_seconds() < 0.001


def test_timestamp_protected():
    state = Success()
    with pytest.raises(AttributeError):
        state.timestamp = 1


def test_timestamp_is_serialized():
    state = Success()
    deserialized_state = json.loads(json.dumps(state))
    assert state.timestamp == deserialized_state.timestamp


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
    assert new_state.result == state.result
    assert new_state.timestamp == state.timestamp
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
    assert new_state.timestamp == state.timestamp


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
    s1 = State(result=Success(1))
    s2 = State(result=Success(2))
    s3 = State(result=Success(1))
    assert s1 != s2
    assert s1 == s3


def test_states_are_hashable():
    assert {State(), Pending(), Success()}


def test_states_with_mutable_attrs_are_hashable():
    assert {State(result=[1]), Pending(cached_inputs=dict(a=1))}


class TestStateHierarchy:
    def test_scheduled_is_pending(self):
        assert issubclass(Scheduled, Pending)

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
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_scheduled_state(self):
        state = Scheduled()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_running_state(self):
        state = Running()
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_cached_state(self):
        state = CachedState()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_success_state(self):
        state = Success()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()

    def test_state_type_methods_with_failed_state(self):
        state = Failed(message="")
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_successful()
        assert state.is_failed()

    def test_state_type_methods_with_trigger_failed_state(self):
        state = TriggerFailed(message="")
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_successful()
        assert state.is_failed()

    def test_state_type_methods_with_skipped_state(self):
        state = Skipped()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
