from prefect.state import (FlowStatus, FlowState, TaskState)
import pytest


def test_equals():
    s = TaskState(state=TaskState.RUNNING)
    assert s == TaskState.RUNNING

def test_FlowStatus():
    s = FlowStatus()
    assert s == FlowStatus.PAUSED

    s.activate()
    assert s == FlowStatus.ACTIVE

    s.pause()
    assert s == FlowStatus.PAUSED

    s.archive()
    assert s == FlowStatus.ARCHIVED

    with pytest.raises(ValueError):
        s.activate()

    s.unarchive()
    assert s == FlowStatus.PAUSED

def test_FlowState():
    s = FlowState()
    assert s == FlowState.PENDING

    s.schedule()
    assert s == FlowState.SCHEDULED

    s.start()
    assert s == FlowState.RUNNING

    with pytest.raises(ValueError):
        s.schedule()

    s.succeed()
    assert s == FlowState.SUCCESS
    with pytest.raises(ValueError):
        s.fail()

    s = FlowState()
    s.start()
    s.fail()
    assert s == FlowState.FAILED

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
