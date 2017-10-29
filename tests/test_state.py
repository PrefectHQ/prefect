from prefect.state import (
    FlowState, FlowRunState, TaskRunState)
import pytest


def test_equals():
    s = TaskRunState(state=TaskRunState.RUNNING)
    assert s == TaskRunState.RUNNING


def test_FlowState():
    s = FlowState()
    assert s == FlowState.PAUSED

    s.activate()
    assert s == FlowState.ACTIVE

    s.pause()
    assert s == FlowState.PAUSED

    s.archive()
    assert s == FlowState.ARCHIVED

    with pytest.raises(ValueError):
        s.activate()

    s.unarchive()
    assert s == FlowState.PAUSED


def test_FlowRunState():
    s = FlowRunState()
    assert s == FlowRunState.PENDING

    s.set_state(state=FlowRunState.RUNNING)
    assert s == FlowRunState.RUNNING
    assert not s in [FlowRunState.RUNNING]
    assert s.state == FlowRunState.RUNNING
    assert s.state in [FlowRunState.RUNNING]

    assert s == FlowRunState(state=FlowRunState.RUNNING)

    s.set_state(result=3)
    assert s.result == 3


def test_TaskRunState():
    s = TaskRunState()
    assert s == TaskRunState.PENDING
    assert s.is_pending()
    assert not s.is_started()

    s.start()
    assert s == TaskRunState.RUNNING
    assert s.is_running()

    s.succeed()
    assert s == TaskRunState.SUCCESS
    assert s.is_successful()
    assert s.is_finished()

    with pytest.raises(ValueError):
        s.fail()

    s.state = TaskRunState.FAILED
    s.retry()
    assert s == TaskRunState.PENDING_RETRY
    assert s.is_pending()

    s.schedule()
    assert s == TaskRunState.SCHEDULED
    assert s.is_pending()

    s.skip()
    assert s == TaskRunState.SKIPPED
    assert s.is_skipped()
    assert s.is_finished()

    with pytest.raises(ValueError):
        s.start()

    s = TaskRunState()
    assert s == TaskRunState.PENDING
    assert s.is_pending()
    assert not s.is_started()

    s.start()
    s.fail()
    assert s == TaskRunState.FAILED
    assert s.is_finished()
    assert s.is_failed()

