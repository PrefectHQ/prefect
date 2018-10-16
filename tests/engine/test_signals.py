import datetime
import pytest

from prefect.engine.signals import (
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


def test_signals_pass_arguments_to_states():
    with pytest.raises(PrefectStateSignal) as exc:
        raise SUCCESS("you did it!", result=100)
    assert exc.value.state.message is exc.value
    assert exc.value.state.result == 100
    assert str(exc.value.state.message) == "you did it!"


def test_signals_dont_pass_invalid_arguments_to_states():
    with pytest.raises(TypeError):
        raise SUCCESS(bad_result=100)


def test_retry_signals_can_set_retry_time():
    date = datetime.datetime(2019, 1, 1)
    with pytest.raises(PrefectStateSignal) as exc:
        raise RETRY(start_time=date)
    assert exc.value.state.start_time == date


@pytest.mark.parametrize(
    "signal,state",
    [
        (FAIL, Failed),
        (TRIGGERFAIL, TriggerFailed),
        (SUCCESS, Success),
        (RETRY, Retrying),
        (SKIP, Skipped),
    ],
)
def test_signals_creates_correct_states(signal, state):
    with pytest.raises(Exception) as exc:
        raise signal(state.__name__)
    assert isinstance(exc.value, signal)
    assert type(exc.value.state) is state
    assert exc.value.state.message is exc.value
    assert str(exc.value.state.message) == state.__name__


def test_retry_signals_carry_default_retry_time_on_state():
    with pytest.raises(Exception) as exc:
        raise RETRY()
    assert exc.value.state.start_time is not None
    now = datetime.datetime.utcnow()
    assert now - exc.value.state.start_time < datetime.timedelta(seconds=0.1)
