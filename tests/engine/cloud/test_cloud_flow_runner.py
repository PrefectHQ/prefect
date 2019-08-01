import datetime
import time
import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pendulum
import pytest

import prefect
from prefect.client import Client
from prefect.engine.cloud import CloudFlowRunner, CloudTaskRunner
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.engine.state import (
    Failed,
    Finished,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True)
def cloud_settings():
    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "token",
            "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
            "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
        }
    ):
        yield


@pytest.fixture()
def client(monkeypatch):
    cloud_client = MagicMock(
        get_flow_run_info=MagicMock(return_value=MagicMock(state=None, parameters={})),
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
    fr = CloudFlowRunner(flow=prefect.Flow(name="test"))
    assert fr.task_runner_cls is CloudTaskRunner


def test_flow_runner_calls_client_the_approriate_number_of_times(client):
    flow = prefect.Flow(name="test")

    res = CloudFlowRunner(flow=flow).run()

    ## assertions
    assert client.get_flow_run_info.call_count == 1  # one time to pull latest state
    assert client.set_flow_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_flow_run_state.call_args_list]
    assert states == [Running(), Success(result={})]


def test_flow_runner_doesnt_set_running_states_twice(client):
    task = prefect.Task()
    flow = prefect.Flow(name="test", tasks=[task])

    res = CloudFlowRunner(flow=flow).run(
        task_states={task: Retrying(start_time=pendulum.now("utc").add(days=1))}
    )

    ## assertions
    assert client.get_flow_run_info.call_count == 1  # one time to pull latest state
    assert client.set_flow_run_state.call_count == 1  # Pending -> Running


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

    flow = prefect.Flow(name="test", tasks=[prefect.Task()], state_handlers=[handler])

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


def test_flow_handlers_are_called_even_when_initialize_run_fails(client):
    class BadRunner(CloudFlowRunner):
        def initialize_run(self, *args, **kwargs):
            raise SyntaxError("bad")

    handler_results = dict(Flow=0)

    def handler(runner, old, new):
        handler_results["Flow"] += 1
        return new

    flow = prefect.Flow(name="test", state_handlers=[handler])
    with prefect.context(flow_run_version=0):
        BadRunner(flow=flow).run()

    # the flow changed state once: Pending -> Failed
    assert handler_results["Flow"] == 1


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
    assert states == [Running(), Success(result={})]


def test_flow_runner_loads_parameters_from_cloud(monkeypatch):

    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(return_value=MagicMock(parameters={"a": 1}))
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).initialize_run(
        state=Pending(), task_states={}, context={}, task_contexts={}, parameters={}
    )

    assert res.context["parameters"]["a"] == 1


def test_flow_runner_loads_context_from_cloud(monkeypatch):
    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(return_value=MagicMock(context={"a": 1}))
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).initialize_run(
        state=Pending(), task_states={}, context={}, task_contexts={}, parameters={}
    )

    assert res.context["a"] == 1


def test_flow_runner_puts_scheduled_start_time_in_context(monkeypatch):
    flow = prefect.Flow(name="test")
    date = pendulum.parse("19860920")
    get_flow_run_info = MagicMock(
        return_value=MagicMock(context={}, scheduled_start_time=date)
    )
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).initialize_run(
        state=None, task_states={}, context={}, task_contexts={}, parameters={}
    )

    assert "scheduled_start_time" in res.context
    assert isinstance(res.context["scheduled_start_time"], datetime.datetime)
    assert res.context["scheduled_start_time"].strftime("%Y-%m-%d") == "1986-09-20"


def test_flow_runner_prioritizes_user_context_over_default_context(monkeypatch):
    flow = prefect.Flow(name="test")
    get_flow_run_info = MagicMock(return_value=MagicMock(context={"today": "is a day"}))
    set_flow_run_state = MagicMock()
    client = MagicMock(
        get_flow_run_info=get_flow_run_info, set_flow_run_state=set_flow_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).initialize_run(
        state=None, task_states={}, context={}, task_contexts={}, parameters={}
    )

    assert "today" in res.context
    assert res.context["today"] == "is a day"


def test_client_is_always_called_even_during_failures(client):
    @prefect.task
    def raise_me(x, y):
        raise SyntaxError("Aggressively weird error")

    with prefect.Flow(name="test") as flow:
        final = raise_me(4, 7)

    assert len(flow.tasks) == 3

    res = flow.run(state=Pending())

    ## assertions
    assert client.get_flow_run_info.call_count == 1  # one time to pull latest state
    assert client.set_flow_run_state.call_count == 2  # Pending -> Running -> Failed

    flow_states = [
        call[1]["state"] for call in client.set_flow_run_state.call_args_list
    ]
    assert [type(s).__name__ for s in flow_states] == ["Running", "Failed"]

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


def test_task_failure_caches_inputs_automatically(client):
    @prefect.task(max_retries=2, retry_delay=timedelta(seconds=100))
    def is_p_three(p):
        if p == 3:
            raise ValueError("No thank you.")

    with prefect.Flow("test") as f:
        p = prefect.Parameter("p")
        res = is_p_three(p)

    state = CloudFlowRunner(flow=f).run(return_tasks=[res], parameters=dict(p=3))
    assert state.is_running()
    assert isinstance(state.result[res], Retrying)
    exp_res = Result(3, result_handler=JSONResultHandler())
    assert not state.result[res].cached_inputs["p"] == exp_res
    exp_res.store_safe_value()
    assert state.result[res].cached_inputs["p"] == exp_res

    last_state = client.set_task_run_state.call_args_list[-1][-1]["state"]
    assert isinstance(last_state, Retrying)
    assert last_state.cached_inputs["p"] == exp_res


def test_state_handler_failures_are_handled_appropriately(client):
    def bad(*args, **kwargs):
        raise SyntaxError("Syntax Errors are nice because they're so unique")

    @prefect.task
    def do_nothing():
        raise ValueError("This task failed somehow")

    f = prefect.Flow(name="test", tasks=[do_nothing], on_failure=bad)
    res = CloudFlowRunner(flow=f).run()
    assert res.is_failed()
    assert "SyntaxError" in res.message
    assert isinstance(res.result, SyntaxError)

    assert client.set_flow_run_state.call_count == 2
    states = [call[1]["state"] for call in client.set_flow_run_state.call_args_list]
    assert states[0].is_running()
    assert states[1].is_failed()
    assert isinstance(states[1].result, SyntaxError)
