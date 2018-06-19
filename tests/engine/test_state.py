import datetime
import json
from prefect.engine.state import FlowState, TaskState
import pytest


class TestFlowState:
    def test_default_state(self):
        assert FlowState._default_state == FlowState.PENDING  # pylint: disable=W0212

    def test_create_no_args(self):
        state = FlowState()
        assert state.state == FlowState._default_state  # pylint: disable=W0212
        assert state.data is None

    def test_create_state(self):
        state = FlowState(FlowState.RUNNING)
        assert state.state == FlowState.RUNNING
        assert state.data is None

    def test_create_state_and_data(self):
        data = {"hi": 5}
        state = FlowState(FlowState.RUNNING, data)
        assert state.state == FlowState.RUNNING
        assert state.data == data

    def test_invalid_states(self):
        with pytest.raises(ValueError):
            FlowState("")
        with pytest.raises(ValueError):
            FlowState(1)
        with pytest.raises(ValueError):
            FlowState("running")

    def test_timestamp(self):
        state = FlowState(FlowState.SUCCESS)
        assert (datetime.datetime.utcnow() - state.timestamp).total_seconds() < 0.001

    def test_state_protected(self):
        state = FlowState()
        with pytest.raises(AttributeError):
            state.state = FlowState.SUCCESS

    def test_data_protected(self):
        state = FlowState()
        with pytest.raises(AttributeError):
            state.data = 1

    def test_timestamp_protected(self):
        state = FlowState(FlowState.SUCCESS)
        with pytest.raises(AttributeError):
            state.timestamp = 1

    def test_serialize(self):
        state = FlowState("SUCCESS", data=dict(hi=5, bye=6))
        j = json.dumps(state)
        new_state = json.loads(j)
        assert isinstance(new_state, FlowState)
        assert new_state.state == state.state
        assert new_state.data == state.data
        assert new_state.timestamp == state.timestamp


class TestFlowStateMethods:
    def test_pending_methods(self):
        state = FlowState(FlowState.PENDING)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_scheduled_methods(self):
        state = FlowState(FlowState.SCHEDULED)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_running_methods(self):
        state = FlowState(FlowState.RUNNING)
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_success_methods(self):
        state = FlowState(FlowState.SUCCESS)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_failed_methods(self):
        state = FlowState(FlowState.FAILED)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_skipped()

    def test_skipped_methods(self):
        state = FlowState(FlowState.SKIPPED)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert state.is_skipped()


class TestTaskState:
    def test_default_state(self):
        assert TaskState._default_state == TaskState.PENDING  # pylint: disable=W0212

    def test_create_no_args(self):
        state = TaskState()
        assert state.state == TaskState._default_state  # pylint: disable=W0212
        assert state.data is None

    def test_create_state(self):
        state = TaskState(TaskState.RUNNING)
        assert state.state == TaskState.RUNNING
        assert state.data is None

    def test_create_state_and_data(self):
        data = {"hi": 5}
        state = TaskState(TaskState.RUNNING, data)
        assert state.state == TaskState.RUNNING
        assert state.data == data

    def test_invalid_states(self):
        with pytest.raises(ValueError):
            TaskState("")
        with pytest.raises(ValueError):
            TaskState(1)
        with pytest.raises(ValueError):
            TaskState("running")

    def test_timestamp(self):
        state = TaskState(TaskState.SUCCESS)
        assert (datetime.datetime.utcnow() - state.timestamp).total_seconds() < 0.001

    def test_state_protected(self):
        state = TaskState()
        with pytest.raises(AttributeError):
            state.state = TaskState.SUCCESS

    def test_data_protected(self):
        state = TaskState()
        with pytest.raises(AttributeError):
            state.data = 1

    def test_timestamp_protected(self):
        state = TaskState(TaskState.SUCCESS)
        with pytest.raises(AttributeError):
            state.timestamp = 1

    def test_serialize(self):
        state = TaskState("SUCCESS", data=dict(hi=5, bye=6))
        j = json.dumps(state)
        new_state = json.loads(j)
        assert isinstance(new_state, TaskState)
        assert new_state.state == state.state
        assert new_state.data == state.data
        assert new_state.timestamp == state.timestamp


class TestTaskStateMethods:
    def test_pending_methods(self):
        state = TaskState(TaskState.PENDING)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_scheduled_methods(self):
        state = TaskState(TaskState.SCHEDULED)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_running_methods(self):
        state = TaskState(TaskState.RUNNING)
        assert not state.is_pending()
        assert state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_success_methods(self):
        state = TaskState(TaskState.SUCCESS)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()

    def test_failed_methods(self):
        state = TaskState(TaskState.FAILED)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert not state.is_successful()
        assert state.is_failed()
        assert not state.is_skipped()

    def test_skipped_methods(self):
        state = TaskState(TaskState.SKIPPED)
        assert not state.is_pending()
        assert not state.is_running()
        assert state.is_finished()
        assert state.is_successful()
        assert not state.is_failed()
        assert state.is_skipped()

    def test_pending_retry_methods(self):
        state = TaskState(TaskState.PENDING_RETRY)
        assert state.is_pending()
        assert not state.is_running()
        assert not state.is_finished()
        assert not state.is_successful()
        assert not state.is_failed()
        assert not state.is_skipped()
