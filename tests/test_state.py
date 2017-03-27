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
    assert not s.is_started()

    s.start()
    assert s == State.RUNNING
    assert s.is_running()

    s.succeed()
    assert s == State.SUCCESS
    assert s.is_successful()
    assert s.is_finished()

    with pytest.raises(transitions.MachineError):
        s.fail()

    s.retry()
    assert s == State.PENDING_RETRY
    assert s.is_pending()

    s.schedule()
    assert s == State.SCHEDULED
    assert s.is_pending()

    s.skip()
    assert s == State.SKIPPED
    assert s.is_skipped()
    assert s.is_finished()
    
    with pytest.raises(transitions.MachineError):
        s.start()

    s.clear()
    assert s == State.NONE
    assert s.is_pending()
    assert not s.is_started()

    s.fail()
    assert s == State.FAILED
    assert s.is_finished()
    assert s.is_failed()
