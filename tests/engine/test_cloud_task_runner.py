import pytest
import time
from unittest.mock import MagicMock

import prefect
from prefect.client import Client
from prefect.client.result_handlers import ResultHandler
from prefect.engine.cloud_runners import CloudTaskRunner
from prefect.engine.runner import ENDRUN
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


def test_task_runner_calls_client_the_approriate_number_of_times(monkeypatch):
    task = prefect.Task(name="test")
    get_task_run_info = MagicMock(return_value=MagicMock(state=None))
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )
    res = CloudTaskRunner(task=task).run()

    ## assertions
    assert get_task_run_info.call_count == 1  # one time to pull latest state
    assert set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in set_task_run_state.call_args_list]
    assert states == [Running(), Success()]


def test_task_runner_raises_endrun_if_client_cant_communicate_during_state_updates(
    monkeypatch
):
    @prefect.task(name="test")
    def raise_error():
        raise NameError("I don't exist")

    get_task_run_info = MagicMock(return_value=MagicMock(state=None))
    set_task_run_state = MagicMock(side_effect=SyntaxError)
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )

    ## an ENDRUN will cause the TaskRunner to return the most recently computed state
    res = CloudTaskRunner(task=raise_error).run()
    assert res.is_running()


def test_task_runner_raises_endrun_if_client_cant_receive_state_updates(monkeypatch):
    task = prefect.Task(name="test")
    get_task_run_info = MagicMock(side_effect=SyntaxError)
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )
    with pytest.raises(ENDRUN):
        res = CloudTaskRunner(task=task).run()


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_task_runner_respects_the_db_state(monkeypatch, state):
    task = prefect.Task(name="test")
    db_state = state("already", result=10)
    get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )
    res = CloudTaskRunner(task=task).run()

    ## assertions
    assert get_task_run_info.call_count == 1  # one time to pull latest state
    assert set_task_run_state.call_count == 0  # never needs to update state
    assert res == db_state


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_task_runner_prioritizes_kwarg_states_over_db_states(monkeypatch, state):
    task = prefect.Task(name="test")
    db_state = state("already", result=10)
    get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )
    res = CloudTaskRunner(task=task).run(state=Pending("let's do this"))

    ## assertions
    assert get_task_run_info.call_count == 1  # one time to pull latest state
    assert set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in set_task_run_state.call_args_list]
    assert states == [Running(), Success()]


class TestHeartBeats:
    def test_heartbeat_traps_errors_caused_by_client(self, monkeypatch):
        client = MagicMock(update_task_run_heartbeat=MagicMock(side_effect=SyntaxError))
        monkeypatch.setattr(
            "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
        )
        runner = CloudTaskRunner(task=prefect.Task(name="bad"))
        runner.task_run_id = None
        with pytest.warns(UserWarning) as warning:
            res = runner._heartbeat()
        assert res is None
        assert client.update_task_run_heartbeat.called
        w = warning.pop()
        assert "Heartbeat failed for bad" in repr(w.message)

    def test_heartbeat_traps_errors_caused_by_bad_attributes(self, monkeypatch):
        monkeypatch.setattr("prefect.engine.cloud_runners.Client", MagicMock())
        runner = CloudTaskRunner(task=prefect.Task())
        with pytest.warns(UserWarning) as warning:
            res = runner._heartbeat()
        assert res is None
        w = warning.pop()
        assert "Heartbeat failed for Task" in repr(w.message)

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat(self, executor, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
        )

        @prefect.task
        def sleeper():
            time.sleep(2)

        with set_temporary_config({"cloud.heartbeat_interval": 1.0}):
            res = CloudTaskRunner(task=sleeper).run(executor=executor)

        assert res.is_successful()
        assert client.update_task_run_heartbeat.called
        assert client.update_task_run_heartbeat.call_count >= 2

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat_with_task_run_id(self, executor, monkeypatch):
        get_task_run_info = MagicMock(return_value=MagicMock(id="1234", version=0))
        client = MagicMock(get_task_run_info=get_task_run_info)
        monkeypatch.setattr(
            "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
        )
        task = prefect.Task(name="test")
        with set_temporary_config({"prefect_cloud": True}):
            res = CloudTaskRunner(task=task).run(executor=executor)

        assert res.is_successful()
        assert client.update_task_run_heartbeat.call_args[0][0] == "1234"


def test_client_is_always_called_even_during_failures(monkeypatch):
    @prefect.task
    def raise_me(x, y):
        raise SyntaxError("Aggressively weird error")

    with prefect.Flow() as flow:
        final = raise_me(4, 7)

    assert len(flow.tasks) == 3

    ## flow run setup
    get_flow_run_info = MagicMock(return_value=MagicMock(state=None))
    set_flow_run_state = MagicMock()
    get_task_run_info = MagicMock(return_value=MagicMock(state=None))
    set_task_run_state = MagicMock()
    cloud_client = MagicMock(
        get_flow_run_info=get_flow_run_info,
        set_flow_run_state=set_flow_run_state,
        get_task_run_info=get_task_run_info,
        set_task_run_state=set_task_run_state,
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=cloud_client)
    )
    res = flow.run(state=Pending())

    ## assertions
    assert get_flow_run_info.call_count == 1  # one time to pull latest state
    assert set_flow_run_state.call_count == 2  # Pending -> Running -> Failed

    flow_states = [call[1]["state"] for call in set_flow_run_state.call_args_list]
    assert flow_states == [Running(), Failed(result=dict())]

    assert get_task_run_info.call_count == 3  # three time to pull latest states
    assert set_task_run_state.call_count == 6  # (Pending -> Running -> Finished) * 3

    task_states = [call[1]["state"] for call in set_task_run_state.call_args_list]
    assert len([s for s in task_states if s.is_running()]) == 3
    assert len([s for s in task_states if s.is_successful()]) == 2
    assert len([s for s in task_states if s.is_failed()]) == 1
