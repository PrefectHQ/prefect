import datetime
import json

import pytest

from prefect.engine.state import State, Success, Retrying, Running, Failed, Skipped, Pending, Scheduled


class TestState:
    def test_create_state_with_no_args(self):
        state = State()
        assert state.data is None

    def test_create_state_with_state_and_data(self):
        data = {"hi": 5}
        state = Running(data)
        assert state.data == data

    def test_timestamp(self):
        state = Success()
        assert (datetime.datetime.utcnow() - state.timestamp).total_seconds() < 0.001

    def test_state_protected(self):
        state = State()
        with pytest.raises(AttributeError):
            state.state = State.SUCCESS

    def test_data_protected(self):
        state = State()
        with pytest.raises(AttributeError):
            state.data = 1

    def test_timestamp_protected(self):
        state = Success()
        with pytest.raises(AttributeError):
            state.timestamp = 1

    def test_serialize(self):
        state = Success(data=dict(hi=5, bye=6))
        j = json.dumps(state)
        new_state = json.loads(j)
        assert isinstance(new_state, State)
        assert isinstance(new_state, Success)
        assert new_state.data == state.data
        assert new_state.timestamp == state.timestamp

    def test_state_equality(self):
        assert State() == State()
        assert Success() == Success()
        assert Success(data=1) == Success(data=1)
        assert not State() == Success()
        assert not Success(data=1) == Success(data=2)

    def test_states_are_hashable(self):
        assert {Success(), Failed()}


class TestStateMethods:
    def test_state_type_methods_with_pending_state(self):
        state = Pending()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_scheduled_state(self):
        state = Scheduled()
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_running_state(self):
        state = Running()
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_success_state(self):
        state = Success()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_failed_state(self):
        state = Failed()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_skipped_state(self):
        state = Skipped()
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert state.is_skipped()
