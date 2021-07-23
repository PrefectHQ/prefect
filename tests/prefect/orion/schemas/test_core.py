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
