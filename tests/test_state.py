from prefect.state import (FlowState, FlowRunState, TaskRunState)
import pytest
import transitions


def test_equals():
    s = TaskRunState(initial_state=TaskRunState.RUNNING)
    assert s == TaskRunState.RUNNING

def test_flowstate():
    s = FlowState()
    assert s == FlowState.ACTIVE

    s.pause()
    assert s == FlowState.PAUSED

    s.archive()
    assert s == FlowState.ARCHIVED

    with pytest.raises(transitions.MachineError):
        s.activate()

    with pytest.raises(transitions.MachineError):
        s.pause()

    s.unarchive()
    assert s == FlowState.PAUSED

def test_flowrunstate():
    s = FlowRunState()
    assert s == FlowRunState.PENDING

    s.schedule()
    assert s == FlowRunState.SCHEDULED

    s.start()
    assert s == FlowRunState.RUNNING

    with pytest.raises(transitions.MachineError):
        s.schedule()

    s.succeed()
    assert s == FlowRunState.SUCCESS
    with pytest.raises(transitions.MachineError):
        s.fail()

    s = FlowRunState()
    s.fail()
    assert s == FlowRunState.FAILED

def test_taskrunstate():
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

    with pytest.raises(transitions.MachineError):
        s.fail()

    with pytest.raises(transitions.MachineError):
        s.wait_for_subtasks()

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

    with pytest.raises(transitions.MachineError):
        s.start()

    s = TaskRunState()
    assert s == TaskRunState.PENDING
    assert s.is_pending()
    assert not s.is_started()

    s.fail()
    assert s == TaskRunState.FAILED
    assert s.is_finished()
    assert s.is_failed()

    s = TaskRunState()
    s.start()
    s.wait_for_subtasks()
    s.resume_after_subtasks()
