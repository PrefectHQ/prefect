import uuid
import time
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.client import Client
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.cloud import CloudFlowRunner, CloudTaskRunner

from prefect.engine.state import (
    Failed,
    Finished,
    Pending,
    Running,
    Skipped,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True)
def cloud_settings():
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "token",
            "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
            "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
        }
    ):
        yield


@pytest.fixture()
def client(monkeypatch):
    cloud_client = MagicMock(
        get_flow_run_info=MagicMock(return_value=MagicMock(state=None)),
        set_flow_run_state=MagicMock(),
        get_task_run_info=MagicMock(return_value=MagicMock(state=None)),
        set_task_run_state=MagicMock(),
        get_latest_task_run_states=MagicMock(
            side_effect=lambda flow_run_id, states, result_handler: states
        ),
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=cloud_client)
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=cloud_client)
    )
    yield cloud_client


def test_task_runner_cls_is_cloud_task_runner():
    fr = CloudFlowRunner(flow=prefect.Flow())
    assert fr.task_runner_cls is CloudTaskRunner


def test_flow_runner_calls_client_the_approriate_number_of_times(client):
    flow = prefect.Flow(name="test")

    res = CloudFlowRunner(flow=flow).run()

    ## assertions
    assert client.get_flow_run_info.call_count == 1  # one time to pull latest state
    assert client.set_flow_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_flow_run_state.call_args_list]
    assert states == [Running(), Success(result=dict())]


def test_flow_runner_raises_endrun_if_client_cant_update_state(monkeypatch):
    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(return_value=MagicMock(state=None))
    set_flow_run_state = MagicMock(side_effect=SyntaxError)
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )

    ## if ENDRUN is raised, res will be last state seen
    res = CloudFlowRunner(flow=flow).run()
    assert set_flow_run_state.called
    assert res.is_running()


def test_flow_runner_raises_endrun_if_client_cant_retrieve_state(monkeypatch):
    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(side_effect=SyntaxError)
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )

    ## if ENDRUN is raised, res will be last state seen
    res = CloudFlowRunner(flow=flow).run()
    assert get_flow_run_info.called
    assert res.is_failed()
    assert isinstance(res.result, SyntaxError)


def test_flow_runner_raises_endrun_with_correct_state_if_client_cant_retrieve_state(
    monkeypatch
):
    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(side_effect=SyntaxError)
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )

    ## if ENDRUN is raised, res will be last state seen
    state = Pending("unique message", result=22)
    res = CloudFlowRunner(flow=flow).run(state=state)
    assert get_flow_run_info.called
    assert res is state


def test_client_is_always_called_even_during_state_handler_failures(client):
    def handler(task, old, new):
        1 / 0

    flow = prefect.Flow(tasks=[prefect.Task()], state_handlers=[handler])

    ## flow run setup
    res = flow.run(state=Pending())

    ## assertions
    assert client.get_flow_run_info.call_count == 1  # one time to pull latest state
    assert client.set_flow_run_state.call_count == 1  # Failed

    flow_states = [
        call[1]["state"] for call in client.set_flow_run_state.call_args_list
    ]
    state = flow_states.pop()
    assert state.is_failed()
    assert "state handlers" in state.message
    assert isinstance(state.result, ZeroDivisionError)
    assert client.get_task_run_info.call_count == 0


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_flow_runner_respects_the_db_state(monkeypatch, state):
    flow = prefect.Flow(name="test")
    db_state = state("already", result=10)
    get_flow_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).run()

    ## assertions
    assert get_flow_run_info.call_count == 1  # one time to pull latest state
    assert set_flow_run_state.call_count == 0  # never needs to update state
    assert res == db_state


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_flow_runner_prioritizes_kwarg_states_over_db_states(monkeypatch, state):
    flow = prefect.Flow(name="test")
    db_state = state("already", result=10)
    get_flow_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).run(state=Pending("let's do this"))

    ## assertions
    assert get_flow_run_info.call_count == 1  # one time to pull latest state
    assert set_flow_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in set_flow_run_state.call_args_list]
    assert states == [Running(), Success(result=dict())]


def test_client_is_always_called_even_during_failures(client):
    @prefect.task
    def raise_me(x, y):
        raise SyntaxError("Aggressively weird error")

    with prefect.Flow() as flow:
        final = raise_me(4, 7)

    assert len(flow.tasks) == 3

    res = flow.run(state=Pending())

    ## assertions
    assert client.get_flow_run_info.call_count == 1  # one time to pull latest state
    assert client.set_flow_run_state.call_count == 2  # Pending -> Running -> Failed

    flow_states = [
        call[1]["state"] for call in client.set_flow_run_state.call_args_list
    ]
    assert flow_states == [Running(), Failed(result=dict())]

    assert (
        client.set_task_run_state.call_count == 6
    )  # (Pending -> Running -> Finished) * 3

    task_states = [
        call[1]["state"] for call in client.set_task_run_state.call_args_list
    ]
    assert len([s for s in task_states if s.is_running()]) == 3
    assert len([s for s in task_states if s.is_successful()]) == 2
    assert len([s for s in task_states if s.is_failed()]) == 1


def test_heartbeat_traps_errors_caused_by_client(monkeypatch):
    client = MagicMock(update_flow_run_heartbeat=MagicMock(side_effect=SyntaxError))
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    runner = CloudFlowRunner(flow=prefect.Flow(name="bad"))
    with pytest.warns(UserWarning) as warning:
        res = runner._heartbeat()

    assert res is None
    assert client.update_flow_run_heartbeat.called
    w = warning.pop()
    assert "Heartbeat failed for Flow 'bad'" in repr(w.message)
