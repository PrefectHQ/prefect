import pytest

from prefect.engine.signals import (
    DONTRUN,
    FAIL,
    RETRY,
    SKIP,
    SUCCESS,
    TRIGGERFAIL,
    PrefectStateSignal,
)
from prefect.engine.state import (
    Failed,
    Retrying,
    Skipped,
    State,
    Success,
    TriggerFailed,
)


def test_exceptions_are_displayed_with_messages():
    exc = PrefectStateSignal("you did something incorrectly")
    assert "you did something incorrectly" in repr(exc)
    assert "PrefectStateSignal" in repr(exc)


def test_signals_create_states():
    with pytest.raises(Exception) as exc:
        raise PrefectStateSignal("message")
    assert isinstance(exc.value.state, State)
    assert exc.value.state.message is exc.value
    assert str(exc.value.state.message) == "message"
    assert exc.value.state.result is None


@pytest.mark.parametrize(
    "signal,state",
    [
        (FAIL, Failed),
        (TRIGGERFAIL, TriggerFailed),
        (SUCCESS, Success),
        (RETRY, Retrying),
        (SKIP, Skipped),
        (DONTRUN, State),
    ],
)
def test_signals_creates_correct_states(signal, state):
    with pytest.raises(Exception) as exc:
        raise signal(state.__name__)
    assert isinstance(exc.value, signal)
    assert type(exc.value.state) is state
    assert exc.value.state.message is exc.value
    assert str(exc.value.state.message) == state.__name__
