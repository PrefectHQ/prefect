import datetime

import pendulum
import pytest

import prefect
from prefect.engine.signals import (
    FAIL,
    LOOP,
    PAUSE,
    RETRY,
    SKIP,
    SUCCESS,
    TRIGGERFAIL,
    VALIDATIONFAIL,
    PrefectStateSignal,
    signal_from_state,
)
from prefect.engine.state import (
    Failed,
    Looped,
    Paused,
    Retrying,
    Skipped,
    State,
    Success,
    TriggerFailed,
    ValidationFailed,
)
from prefect.exceptions import PrefectSignal


def test_exceptions_are_displayed_with_messages():
    exc = PrefectStateSignal("you did something incorrectly")
    assert "you did something incorrectly" in repr(exc)
    assert "PrefectStateSignal" in repr(exc)


def test_signals_create_states():
    with pytest.raises(PrefectSignal) as exc:
        raise PrefectStateSignal("message")
    assert isinstance(exc.value.state, State)
    assert exc.value.state.result is exc.value
    assert exc.value.state.message == "message"


def test_signals_create_states_with_results():
    with pytest.raises(PrefectSignal) as exc:
        raise PrefectStateSignal("message", result=5)
    assert isinstance(exc.value.state, State)
    assert exc.value.state.result == 5
    assert exc.value.state.message == "message"


def test_signals_dont_pass_invalid_arguments_to_states():
    with pytest.raises(TypeError):
        raise SUCCESS(bad_result=100)


def test_retry_signals_can_set_retry_time():
    date = pendulum.datetime(2019, 1, 1)
    with pytest.raises(PrefectStateSignal) as exc:
        raise RETRY(start_time=date)
    assert exc.value.state.start_time == date


def test_retry_signals_accept_run_count():
    with pytest.raises(PrefectStateSignal) as exc:
        raise RETRY(run_count=5)
    assert exc.value.state.run_count == 5


def test_retry_signals_take_run_count_from_context():
    with prefect.context(task_run_count=5):
        with pytest.raises(PrefectStateSignal) as exc:
            raise RETRY()
    assert exc.value.state.run_count == 5


def test_retry_signals_prefer_supplied_run_count_to_context():
    with prefect.context(task_run_count=5):
        with pytest.raises(PrefectStateSignal) as exc:
            raise RETRY(run_count=6)
    assert exc.value.state.run_count == 6


@pytest.mark.parametrize(
    "signal,state",
    [
        (FAIL, Failed),
        (TRIGGERFAIL, TriggerFailed),
        (VALIDATIONFAIL, ValidationFailed),
        (SUCCESS, Success),
        (PAUSE, Paused),
        (RETRY, Retrying),
        (SKIP, Skipped),
    ],
)
def test_signals_creates_correct_states(signal, state):
    with pytest.raises(PrefectSignal) as exc:
        raise signal(state.__name__)
    assert isinstance(exc.value, signal)
    assert type(exc.value.state) is state
    assert exc.value.state.result is exc.value
    assert exc.value.state.message == state.__name__


def test_signals_creates_correct_states_for_looped():
    with pytest.raises(PrefectSignal) as exc:
        raise LOOP("signal")
    assert isinstance(exc.value, LOOP)
    assert type(exc.value.state) is Looped
    assert exc.value.state.result == repr(exc.value)
    assert exc.value.state.message == "signal"


def test_retry_signals_carry_default_retry_time_on_state():
    with pytest.raises(PrefectSignal) as exc:
        raise RETRY()
    assert exc.value.state.start_time is not None
    now = pendulum.now("utc")
    assert now - exc.value.state.start_time < datetime.timedelta(seconds=0.1)


@pytest.mark.parametrize(
    "signal,state",
    [
        (FAIL, Failed),
        (TRIGGERFAIL, TriggerFailed),
        (VALIDATIONFAIL, ValidationFailed),
        (SUCCESS, Success),
        (PAUSE, Paused),
        (RETRY, Retrying),
        (SKIP, Skipped),
    ],
)
def test_signal_from_state_returns_correct_signal(signal, state):
    assert signal_from_state(state("Dummy message")) == signal
