import pytest
from unittest.mock import MagicMock

from prefect.engine.runner import Runner, ENDRUN
from prefect.engine.state import Pending, Running


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
        TestRunner().handle_state_change(Pending(), Running())


def test_call_runner_target_handlers_calls_handlers_appropriately():
    class TestRunner(Runner):
        def call_runner_target_handlers(self, old_state, new_state):
            return new_state

    my_handler = MagicMock(return_value=Running())
    TestRunner(state_handlers=[my_handler]).handle_state_change(Pending(), Running())
    assert my_handler.call_args[0][1:] == (Pending(), Running())


def test_runner_has_logger():
    r = Runner()
    assert r.logger.name == "prefect.Runner"
