import pytest
import time
from unittest.mock import MagicMock

import prefect
from prefect.client import Client
from prefect.client.result_handlers import ResultHandler
from prefect.engine.cloud_runners import CloudFlowRunner, CloudTaskRunner
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


def test_flow_runner_calls_client_the_approriate_number_of_times(monkeypatch):
    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(return_value=MagicMock(state=None))
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).run()

    ## assertions
    assert get_flow_run_info.call_count == 1  # one time to pull latest state
    assert set_flow_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in set_flow_run_state.call_args_list]
    assert states == [Running(), Success(result=dict())]


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
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
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
        "prefect.engine.cloud_runners.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).run(state=Pending("let's do this"))

    ## assertions
    assert get_flow_run_info.call_count == 1  # one time to pull latest state
    assert set_flow_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in set_flow_run_state.call_args_list]
    assert states == [Running(), Success(result=dict())]


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
