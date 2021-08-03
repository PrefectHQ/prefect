import pytest
import pendulum
from prefect.orion.schemas.states import State, StateType, AwaitingRetry, Retrying


class TestState:
    def test_state_takes_name_from_type(self):
        state = State(type=StateType.RUNNING)
        assert state.name == "Running"

    def test_state_custom_name(self):
        state = State(type=StateType.RUNNING, name="My Running State")
        assert state.name == "My Running State"

    def test_state_default_timestamp(self):
        dt = pendulum.now()
        state = State(type=StateType.RUNNING)
        assert state.timestamp > dt


class TestStateTypeFunctions:
    @pytest.mark.parametrize("state_type", StateType)
    def test_is_scheduled(self, state_type):
        state = State(type=state_type)
        assert state.is_scheduled() == (state_type == StateType.SCHEDULED)

    @pytest.mark.parametrize("state_type", StateType)
    def test_is_pending(self, state_type):
        state = State(type=state_type)
        assert state.is_pending() == (state_type == StateType.PENDING)

    @pytest.mark.parametrize("state_type", StateType)
    def test_is_running(self, state_type):
        state = State(type=state_type)
        assert state.is_running() == (state_type == StateType.RUNNING)

    @pytest.mark.parametrize("state_type", StateType)
    def test_is_completed(self, state_type):
        state = State(type=state_type)
        assert state.is_completed() == (state_type == StateType.COMPLETED)

    @pytest.mark.parametrize("state_type", StateType)
    def test_is_failed(self, state_type):
        state = State(type=state_type)
        assert state.is_failed() == (state_type == StateType.FAILED)


class TestStateConvenienceFunctions:
    def test_awaiting_retry(self):
        dt = pendulum.now()
        state = AwaitingRetry(scheduled_time=dt)
        assert state.type == StateType.SCHEDULED
        assert state.name == "AwaitingRetry"
        assert state.state_details.scheduled_time == dt

    def test_retrying(self):
        state = Retrying()
        assert state.type == StateType.RUNNING
        assert state.name == "Retrying"
