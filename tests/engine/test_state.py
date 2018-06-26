import datetime
import json

import pytest

from prefect.engine.state import State


class TestState:
    def test_default_state(self):
        assert State._default_state == State.PENDING  # pylint: disable=W0212

    def test_create_state_with_no_args(self):
        state = State()
        assert state.state == State._default_state  # pylint: disable=W0212
        assert state.data is None

    def test_create_state_with_no_data(self):
        state = State(State.RUNNING)
        assert state.state == State.RUNNING
        assert state.data is None

    def test_create_state_with_state_and_data(self):
        data = {"hi": 5}
        state = State(State.RUNNING, data)
        assert state.state == State.RUNNING
        assert state.data == data

    def test_invalid_states(self):
        with pytest.raises(ValueError):
            State("")
        with pytest.raises(ValueError):
            State(1)
        with pytest.raises(ValueError):
            State("running")

    def test_timestamp(self):
        state = State(State.SUCCESS)
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
        state = State(State.SUCCESS)
        with pytest.raises(AttributeError):
            state.timestamp = 1

    def test_serialize(self):
        state = State("SUCCESS", data=dict(hi=5, bye=6))
        j = json.dumps(state)
        new_state = json.loads(j)
        assert isinstance(new_state, State)
        assert new_state.state == state.state
        assert new_state.data == state.data
        assert new_state.timestamp == state.timestamp

    def test_state_equality(self):
        assert State() == State()
        assert State(State.SUCCESS) == State(State.SUCCESS)
        assert State(State.SUCCESS, data=1) == State(State.SUCCESS, data=1)
        assert not State() == State(State.SUCCESS)
        assert not State(State.SUCCESS, data=1) == State(State.SUCCESS, data=2)

    def test_states_are_hashable(self):
        assert {State(State.SUCCESS), State(State.FAILED)}

class TestStateMethods:
    def test_state_type_methods_with_pending_state(self):
        state = State(State.PENDING)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_scheduled_state(self):
        state = State(State.SCHEDULED)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_running_state(self):
        state = State(State.RUNNING)
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_success_state(self):
        state = State(State.SUCCESS)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_failed_state(self):
        state = State(State.FAILED)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_skipped()

    def test_state_type_methods_with_skipped_state(self):
        state = State(State.SKIPPED)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert state.is_skipped()
