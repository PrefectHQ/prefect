from prefect.engine.state import FlowState, TaskState
import pytest


def test_equals():
    s = TaskState(state=TaskState.RUNNING)
    assert s == TaskState.RUNNING



def test_FlowState():
    s = FlowState()
    assert s == FlowState.PENDING

    s.set_state(state=FlowState.RUNNING)
    assert s == FlowState.RUNNING
    assert not s in [FlowState.RUNNING]
    assert s.state == FlowState.RUNNING
    assert s.state in [FlowState.RUNNING]

    assert s == FlowState(state=FlowState.RUNNING)

    s.set_state(result=3)
    assert s.result == 3


def test_TaskState():
    s = TaskState()
    assert s == TaskState.PENDING
    assert s.is_pending()
    assert not s.is_started()

    s.start()
    assert s == TaskState.RUNNING
    assert s.is_running()

    s.succeed()
    assert s == TaskState.SUCCESS
    assert s.is_successful()
    assert s.is_finished()

    with pytest.raises(ValueError):
        s.fail()

    s.state = TaskState.FAILED
    s.retry()
    assert s == TaskState.PENDING_RETRY
    assert s.is_pending()

    s.schedule()
    assert s == TaskState.SCHEDULED
    assert s.is_pending()

    s.skip()
    assert s == TaskState.SKIPPED
    assert s.is_skipped()
    assert s.is_finished()

    with pytest.raises(ValueError):
        s.start()

    s = TaskState()
    assert s == TaskState.PENDING
    assert s.is_pending()
    assert not s.is_started()

    s.start()
    s.fail()
    assert s == TaskState.FAILED
    assert s.is_finished()
    assert s.is_failed()
