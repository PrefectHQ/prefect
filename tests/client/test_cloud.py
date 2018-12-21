import pytest
from unittest.mock import MagicMock

import prefect
from prefect.client import Client
from prefect.client.result_handlers import ResultHandler
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.task_runner import TaskRunner
from prefect.engine.state import (
    Failed,
    Running,
    Pending,
    Success,
    Finished,
    TriggerFailed,
    TimedOut,
    Skipped,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True)
def cloud_settings():
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "prefect_cloud": True,
            "cloud.auth_token": "token",
        }
    ):
        yield


class TestFlowRunner:
    def test_flow_runner_calls_client_the_approriate_number_of_times(self, monkeypatch):
        flow = prefect.Flow(name="test")
        get_flow_run_info = MagicMock(return_value=MagicMock(state=None))
        set_flow_run_state = MagicMock()
        client = MagicMock(
            get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
        )
        monkeypatch.setattr(
            "prefect.engine.flow_runner.Client", MagicMock(return_value=client)
        )
        res = FlowRunner(flow=flow).run()

        ## assertions
        assert get_flow_run_info.call_count == 1  # one time to pull latest state
        assert set_flow_run_state.call_count == 2  # Pending -> Running -> Success

        states = [call[1]["state"] for call in set_flow_run_state.call_args_list]
        assert states == [Running(), Success(result=dict())]

    @pytest.mark.parametrize(
        "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
    )
    def test_flow_runner_respects_the_db_state(self, monkeypatch, state):
        flow = prefect.Flow(name="test")
        db_state = state("already", result=10)
        get_flow_run_info = MagicMock(return_value=MagicMock(state=db_state))
        set_flow_run_state = MagicMock()
        client = MagicMock(
            get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
        )
        monkeypatch.setattr(
            "prefect.engine.flow_runner.Client", MagicMock(return_value=client)
        )
        res = FlowRunner(flow=flow).run()

        ## assertions
        assert get_flow_run_info.call_count == 1  # one time to pull latest state
        assert set_flow_run_state.call_count == 0  # never needs to update state
        assert res == db_state

    @pytest.mark.parametrize(
        "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
    )
    def test_flow_runner_prioritizes_kwarg_states_over_db_states(
        self, monkeypatch, state
    ):
        flow = prefect.Flow(name="test")
        db_state = state("already", result=10)
        get_flow_run_info = MagicMock(return_value=MagicMock(state=db_state))
        set_flow_run_state = MagicMock()
        client = MagicMock(
            get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
        )
        monkeypatch.setattr(
            "prefect.engine.flow_runner.Client", MagicMock(return_value=client)
        )
        res = FlowRunner(flow=flow).run(state=Pending("let's do this"))

        ## assertions
        assert get_flow_run_info.call_count == 1  # one time to pull latest state
        assert set_flow_run_state.call_count == 2  # Pending -> Running -> Success

        states = [call[1]["state"] for call in set_flow_run_state.call_args_list]
        assert states == [Running(), Success(result=dict())]


class TestTaskRunner:
    def test_task_runner_calls_client_the_approriate_number_of_times(self, monkeypatch):
        task = prefect.Task(name="test")
        get_task_run_info = MagicMock(return_value=MagicMock(state=None))
        set_task_run_state = MagicMock()
        client = MagicMock(
            get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
        )
        monkeypatch.setattr(
            "prefect.engine.task_runner.Client", MagicMock(return_value=client)
        )
        res = TaskRunner(task=task).run()

        ## assertions
        assert get_task_run_info.call_count == 1  # one time to pull latest state
        assert set_task_run_state.call_count == 2  # Pending -> Running -> Success

        states = [call[1]["state"] for call in set_task_run_state.call_args_list]
        assert states == [Running(), Success()]

    @pytest.mark.parametrize(
        "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
    )
    def test_task_runner_respects_the_db_state(self, monkeypatch, state):
        task = prefect.Task(name="test")
        db_state = state("already", result=10)
        get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
        set_task_run_state = MagicMock()
        client = MagicMock(
            get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
        )
        monkeypatch.setattr(
            "prefect.engine.task_runner.Client", MagicMock(return_value=client)
        )
        res = TaskRunner(task=task).run()

        ## assertions
        assert get_task_run_info.call_count == 1  # one time to pull latest state
        assert set_task_run_state.call_count == 0  # never needs to update state
        assert res == db_state

    @pytest.mark.parametrize(
        "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
    )
    def test_task_runner_prioritizes_kwarg_states_over_db_states(
        self, monkeypatch, state
    ):
        task = prefect.Task(name="test")
        db_state = state("already", result=10)
        get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
        set_task_run_state = MagicMock()
        client = MagicMock(
            get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
        )
        monkeypatch.setattr(
            "prefect.engine.task_runner.Client", MagicMock(return_value=client)
        )
        res = TaskRunner(task=task).run(state=Pending("let's do this"))

        ## assertions
        assert get_task_run_info.call_count == 1  # one time to pull latest state
        assert set_task_run_state.call_count == 2  # Pending -> Running -> Success

        states = [call[1]["state"] for call in set_task_run_state.call_args_list]
        assert states == [Running(), Success()]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat(self, executor, monkeypatch):
        glob_dict = {}

        def heartbeat():
            glob_dict["was_called"] = True

        monkeypatch.setattr("prefect.engine.task_runner.Client", MagicMock())
        monkeypatch.setattr("prefect.engine.task_runner.heartbeat", heartbeat)
        task = prefect.Task(name="test")
        res = TaskRunner(task=task).run(executor=executor)
        assert glob_dict.get("was_called") is True

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat_even_when_things_go_wrong(
        self, executor, monkeypatch
    ):
        glob_dict = {}

        def heartbeat():
            glob_dict["was_called"] = True

        monkeypatch.setattr("prefect.engine.task_runner.Client", MagicMock())
        monkeypatch.setattr("prefect.engine.task_runner.heartbeat", heartbeat)

        @prefect.task
        def raise_me():
            raise AttributeError("Doesn't exist")

        res = TaskRunner(task=raise_me).run(executor=executor)
        assert res.is_failed()
        assert glob_dict.get("was_called") is True
