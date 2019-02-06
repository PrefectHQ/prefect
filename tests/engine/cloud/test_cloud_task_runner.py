import cloudpickle
import datetime
import tempfile
import time
import uuid
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.cloud import CloudTaskRunner, CloudResultHandler
from prefect.engine.result import NoResult, Result
from prefect.engine.result_handlers import (
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
)
from prefect.engine.runner import ENDRUN
from prefect.engine.state import (
    Cached,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Running,
    Retrying,
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
            "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
            "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
            "cloud.auth_token": "token",
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
            side_effect=lambda flow_run_id, states: states
        ),
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=cloud_client)
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=cloud_client)
    )
    yield cloud_client


def test_task_runner_doesnt_call_client_if_map_index_is_none(client):
    task = Task(name="test")

    res = CloudTaskRunner(task=task).run()

    ## assertions
    assert client.get_task_run_info.call_count == 0  # never called
    assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert [type(s).__name__ for s in states] == ["Running", "Success"]
    assert res.is_successful()


def test_task_runner_calls_get_task_run_info_if_map_index_is_not_none(client):
    task = Task(name="test")

    res = CloudTaskRunner(task=task).run(context={"map_index": 1})

    ## assertions
    assert client.get_task_run_info.call_count == 1  # never called
    assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert [type(s).__name__ for s in states] == ["Running", "Success"]


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
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
    )

    ## an ENDRUN will cause the TaskRunner to return the most recently computed state
    res = CloudTaskRunner(task=raise_error).run(context={"map_index": 1})
    assert set_task_run_state.called
    assert res.is_running()


def test_task_runner_raises_endrun_if_client_cant_receive_state_updates(monkeypatch):
    task = Task(name="test")
    get_task_run_info = MagicMock(side_effect=SyntaxError)
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
    )

    ## an ENDRUN will cause the TaskRunner to return the most recently computed state
    res = CloudTaskRunner(task=task).run(context={"map_index": 1})
    assert get_task_run_info.called
    assert res.is_failed()
    assert isinstance(res.result, SyntaxError)


def test_task_runner_raises_endrun_with_correct_state_if_client_cant_receive_state_updates(
    monkeypatch
):
    task = Task(name="test")
    get_task_run_info = MagicMock(side_effect=SyntaxError)
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
    )

    ## an ENDRUN will cause the TaskRunner to return the most recently computed state
    state = Pending(message="unique message", result=42)
    res = CloudTaskRunner(task=task).run(state=state, context={"map_index": 1})
    assert get_task_run_info.called
    assert res is state


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_task_runner_respects_the_db_state(monkeypatch, state):
    task = Task(name="test")
    db_state = state("already", result=10)
    get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
    )
    res = CloudTaskRunner(task=task).run(context={"map_index": 1})

    ## assertions
    assert get_task_run_info.call_count == 1  # one time to pull latest state
    assert set_task_run_state.call_count == 0  # never needs to update state
    assert res == db_state


def test_task_runner_uses_cached_inputs_from_db_state(monkeypatch):
    @prefect.task(name="test")
    def add_one(x):
        return x + 1

    db_state = Retrying(cached_inputs=dict(x=Result(41)))
    get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
    )
    res = CloudTaskRunner(task=add_one).run(context={"map_index": 1})

    ## assertions
    assert get_task_run_info.call_count == 1  # one time to pull latest state
    assert set_task_run_state.call_count == 2  # Pending -> Running -> Success
    assert res.is_successful()
    assert res.result == 42


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_task_runner_prioritizes_kwarg_states_over_db_states(monkeypatch, state):
    task = Task(name="test")
    db_state = state("already", result=10)
    get_task_run_info = MagicMock(return_value=MagicMock(state=db_state))
    set_task_run_state = MagicMock()
    client = MagicMock(
        get_task_run_info=get_task_run_info, set_task_run_state=set_task_run_state
    )
    monkeypatch.setattr(
        "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
    )
    res = CloudTaskRunner(task=task).run(
        state=Pending("let's do this"), context={"map_index": 1}
    )

    ## assertions
    assert get_task_run_info.call_count == 1  # one time to pull latest state
    assert set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in set_task_run_state.call_args_list]
    assert [type(s).__name__ for s in states] == ["Running", "Success"]


class TestHeartBeats:
    def test_heartbeat_traps_errors_caused_by_client(self, monkeypatch):
        client = MagicMock(update_task_run_heartbeat=MagicMock(side_effect=SyntaxError))
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )
        runner = CloudTaskRunner(task=Task(name="bad"))
        runner.task_run_id = None
        with pytest.warns(UserWarning) as warning:
            res = runner._heartbeat()
        assert res is None
        assert client.update_task_run_heartbeat.called
        w = warning.pop()
        assert "Heartbeat failed for Task 'bad'" in repr(w.message)

    def test_heartbeat_traps_errors_caused_by_bad_attributes(self, monkeypatch):
        monkeypatch.setattr("prefect.engine.cloud.task_runner.Client", MagicMock())
        runner = CloudTaskRunner(task=Task())
        with pytest.warns(UserWarning) as warning:
            res = runner._heartbeat()
        assert res is None
        w = warning.pop()
        assert "Heartbeat failed for Task 'Task'" in repr(w.message)

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat(self, executor, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )

        @prefect.task
        def sleeper():
            time.sleep(0.2)

        with set_temporary_config({"cloud.heartbeat_interval": 0.05}):
            res = CloudTaskRunner(task=sleeper).run(executor=executor)

        assert res.is_successful()
        assert client.update_task_run_heartbeat.called
        assert client.update_task_run_heartbeat.call_count >= 2

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat_only_during_execution(
        self, executor, monkeypatch
    ):
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )

        with set_temporary_config({"cloud.heartbeat_interval": 0.05}):
            runner = CloudTaskRunner(task=Task())
            runner.cache_result = lambda *args, **kwargs: time.sleep(0.2)
            res = runner.run(executor=executor)

        assert client.update_task_run_heartbeat.called
        assert client.update_task_run_heartbeat.call_count == 1

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat_with_task_run_id(self, executor, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )
        task = Task(name="test")
        res = CloudTaskRunner(task=task).run(
            executor=executor, context={"task_run_id": 1234}
        )

        assert res.is_successful()
        assert client.update_task_run_heartbeat.call_args[0][0] == 1234


class TestStateResultHandling:
    def test_task_runner_handles_outputs_prior_to_setting_state(self, client):
        @prefect.task(
            cache_for=datetime.timedelta(days=1), result_handler=JSONResultHandler()
        )
        def add(x, y):
            return x + y

        result = Result(1, handled=False, result_handler=JSONResultHandler())
        x_state, y_state = Success(result=result), Success(result=result)

        upstream_states = {
            Edge(Task(), Task(), key="x"): x_state,
            Edge(Task(), Task(), key="y"): y_state,
        }

        res = CloudTaskRunner(task=add).run(upstream_states=upstream_states)

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert (
            client.set_task_run_state.call_count == 3
        )  # Pending -> Running -> Successful -> Cached

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()
        assert states[1].is_successful()
        assert isinstance(states[2], Cached)
        assert states[2].cached_inputs == dict(x=result.write(), y=result.write())
        assert states[2].result == "2"

    def test_task_runner_handles_inputs_prior_to_setting_state(self, client):
        @prefect.task(max_retries=1, retry_delay=datetime.timedelta(days=1))
        def add(x, y):
            return x + y

        x = Result(1, handled=False, result_handler=JSONResultHandler())
        y = Result("0", handled=False, result_handler=JSONResultHandler())
        state = Pending(cached_inputs=dict(x=x, y=y))
        x_state = Success(result=1)
        y_state = Success(result=1)
        upstream_states = {
            Edge(Task(), Task(), key="x"): x_state,
            Edge(Task(), Task(), key="y"): y_state,
        }
        res = CloudTaskRunner(task=add).run(
            state=state, upstream_states=upstream_states
        )

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert (
            client.set_task_run_state.call_count == 3
        )  # Pending -> Running -> Failed -> Retrying

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()
        assert states[1].is_failed()
        assert isinstance(states[2], Retrying)
        assert states[2].cached_inputs == dict(x=x.write(), y=y.write())


def test_state_handler_failures_are_handled_appropriately(client):
    def bad(*args, **kwargs):
        raise SyntaxError("Syntax Errors are nice because they're so unique")

    @prefect.task(on_failure=bad)
    def do_nothing():
        raise ValueError("This task failed somehow")

    res = CloudTaskRunner(task=do_nothing).run()
    assert res.is_failed()
    assert "SyntaxError" in res.message
    assert isinstance(res.result, SyntaxError)

    assert client.set_task_run_state.call_count == 2
    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert states[0].is_running()
    assert states[1].is_failed()
    assert states[1].result == NoResult
