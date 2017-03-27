from prefect.state import State
import pytest
import transitions


def test_all_count():
    assert len(State.all_states()) == 8


def test_equals():
    s = State(initial_state=State.RUNNING)
    assert s == State.RUNNING


def test_transitions():
    s = State()
    assert s == State.NONE
    assert s.is_pending()

    s.start()
    assert s == State.RUNNING
    assert s.is_running()

    s.succeed()
    assert s == State.SUCCESS
    assert s.is_successful()

    with pytest.raises(transitions.MachineError):
        s.fail()

    s.retry()
    assert s == State.PENDING_RETRY

    s.schedule()
    assert s == State.SCHEDULED

    s.skip()
    assert s == State.SKIPPED

    s.clear()
    assert s == State.NONE

    s.fail()
    assert s == State.FAILED
