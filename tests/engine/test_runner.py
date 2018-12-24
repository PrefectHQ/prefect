import pytest
from unittest.mock import MagicMock

from prefect import Task
from prefect.engine.runner import Runner, ENDRUN
from prefect.engine import state


def test_state_handlers_must_be_iterable():
    with pytest.raises(TypeError):
        Runner(state_handlers=False)
    with pytest.raises(TypeError):
        Runner(state_handlers=1)
    with pytest.raises(TypeError):
        Runner(state_handlers=lambda *a: 1)


def test_call_runner_target_handlers_gets_called_in_handle_state_change():
    """tests that the `call_runner_target_handlers` helper method is called"""

    class TestRunner(Runner):
        def call_runner_target_handlers(self, old_state, new_state):
            raise ValueError()

    with pytest.raises(ENDRUN):
        TestRunner().handle_state_change(state.Pending(), state.Running())


def test_call_runner_target_handlers_calls_handlers_appropriately():
    class TestRunner(Runner):
        def call_runner_target_handlers(self, old_state, new_state):
            return new_state

    my_handler = MagicMock(return_value=state.Running())
    TestRunner(state_handlers=[my_handler]).handle_state_change(
        state.Pending(), state.Running()
    )
    assert my_handler.call_args[0][1:] == (state.Pending(), state.Running())


def test_runner_has_logger():
    r = Runner()
    assert r.logger.name == "prefect.Runner"


class TestInitializeRun:
    def test_initialize_run_returns_state_and_context(self):
        state_, context = state.Pending(), {}
        s, c = Runner().initialize_run(state=state_, context=context)
        assert s is state_
        assert c is context

    @pytest.mark.parametrize(
        "state",
        [
            state.Success(),
            state.Failed(),
            state.Pending(),
            state.Scheduled(),
            state.Skipped(),
            state.CachedState(),
            state.Retrying(),
            state.Running(),
        ],
    )
    def test_initialize_run_returns_state(self, state):
        new_state, _ = Runner().initialize_run(state, context={})
        assert new_state is state

    @pytest.mark.parametrize(
        "state",
        [
            state.Submitted(state=state.Pending()),
            state.Submitted(state=state.Retrying()),
            state.Submitted(state=state.Scheduled()),
            state.Submitted(state=state.Resume()),
        ],
    )
    def test_initialize_run_gets_wrapped_state_from_submitted_states(self, state):
        new_state, _ = Runner().initialize_run(state, context={})
        assert new_state is state.state

    def test_initialize_run_creates_pending_if_no_state_provided(self):
        new_state, _ = Runner().initialize_run(state=None, context={})
        assert isinstance(new_state, state.Pending)
