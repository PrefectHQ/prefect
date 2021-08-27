import pydantic
import pytest
import pendulum
from uuid import uuid4, UUID

from prefect.orion.schemas.states import State, StateType, AwaitingRetry, Retrying


class TestState:
    def test_state_takes_name_from_type(self):
        state = State(type=StateType.RUNNING)
        assert state.name == "Running"

    def test_state_raises_validation_error_for_invalid_type(self):
        with pytest.raises(
            pydantic.ValidationError, match="(value is not a valid enumeration member)"
        ):
            State(type="Running")

    def test_state_custom_name(self):
        state = State(type=StateType.RUNNING, name="My Running State")
        assert state.name == "My Running State"

    def test_state_default_timestamp(self):
        dt = pendulum.now("UTC")
        state = State(type=StateType.RUNNING)
        assert state.timestamp > dt

    def test_state_copy_creates_insertable_object(self):
        dt = pendulum.now("UTC")
        state = State(
            type=StateType.RUNNING, timestamp=dt, id=uuid4(), created=dt, updated=dt
        )
        new_state = state.copy()
        # New UUID
        assert new_state.id != state.id
        assert isinstance(new_state.id, UUID)
        # New state timestamp
        assert new_state.timestamp > dt
        # Database generated fields
        assert new_state.created is None
        assert new_state.updated is None


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

    @pytest.mark.parametrize("state_type", StateType)
    def test_is_cancelled(self, state_type):
        state = State(type=state_type)
        assert state.is_cancelled() == (state_type == StateType.CANCELLED)


class TestStateConvenienceFunctions:
    def test_awaiting_retry(self):
        dt = pendulum.now("UTC")
        state = AwaitingRetry(scheduled_time=dt)
        assert state.type == StateType.SCHEDULED
        assert state.name == "Awaiting Retry"
        assert state.state_details.scheduled_time == dt

    def test_retrying(self):
        state = Retrying()
        assert state.type == StateType.RUNNING
        assert state.name == "Retrying"
