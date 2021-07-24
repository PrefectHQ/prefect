import pytest
import pendulum
import prefect.orion.schemas.core as core


class TestState:
    def test_state_takes_name_from_type(self):
        state = core.State(type=core.StateType.RUNNING)
        assert state.name == "Running"

    def test_state_custom_name(self):
        state = core.State(type=core.StateType.RUNNING, name="My Running State")
        assert state.name == "My Running State"

    def test_state_default_timestamp(self):
        dt = pendulum.now()
        state = core.State(type=core.StateType.RUNNING)
        assert state.timestamp > dt


class TestStateTypeFunctions:
    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_scheduled(self, state_type):
        state = core.State(type=state_type)
        assert state.is_scheduled() == (
            state_type in (core.StateType.SCHEDULED, core.StateType.AWAITING_RETRY)
        )

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_pending(self, state_type):
        state = core.State(type=state_type)
        assert state.is_pending() == (state_type == core.StateType.PENDING)

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_running(self, state_type):
        state = core.State(type=state_type)
        assert state.is_running() == (
            state_type in (core.StateType.RUNNING, core.StateType.RETRYING)
        )

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_retrying(self, state_type):
        state = core.State(type=state_type)
        assert state.is_retrying() == (state_type == core.StateType.RETRYING)

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_completed(self, state_type):
        state = core.State(type=state_type)
        assert state.is_completed() == (state_type == core.StateType.COMPLETED)

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_failed(self, state_type):
        state = core.State(type=state_type)
        assert state.is_failed() == (state_type == core.StateType.FAILED)

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_cancelled(self, state_type):
        state = core.State(type=state_type)
        assert state.is_cancelled() == (state_type == core.StateType.CANCELLED)

    @pytest.mark.parametrize("state_type", core.StateType)
    def test_is_awaiting_retry(self, state_type):
        state = core.State(type=state_type)
        assert state.is_awaiting_retry() == (
            state_type == core.StateType.AWAITING_RETRY
        )
