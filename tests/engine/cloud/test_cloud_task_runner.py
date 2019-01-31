import cloudpickle
import tempfile
import time
import uuid
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.cloud import CloudTaskRunner, CloudResultHandler
from prefect.engine.result_handlers import JSONResultHandler, LocalResultHandler
from prefect.engine.runner import ENDRUN
from prefect.engine.state import (
    CachedState,
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


class TestInitializeRun:
    def test_ensures_all_upstream_states_are_raw(self, client):
        serialized_handler = ResultHandlerSchema().dump(LocalResultHandler())

        with tempfile.NamedTemporaryFile() as tmp:
            with open(tmp.name, "wb") as f:
                cloudpickle.dump(42, f)

            a, b, c = (
                Success(result=tmp.name),
                Failed(result=55),
                Pending(result=tmp.name),
            )
            a._metadata["result"] = dict(raw=False, result_handler=serialized_handler)
            c._metadata["result"] = dict(raw=False, result_handler=serialized_handler)
            result = CloudTaskRunner(Task()).initialize_run(
                state=Success(), context={}, upstream_states={1: a, 2: b, 3: c}
            )

        assert result.upstream_states[1].result == 42
        assert result.upstream_states[2].result == 55
        assert result.upstream_states[3].result == 42

    def test_ensures_provided_initial_state_is_raw(self, client):
        serialized_handler = ResultHandlerSchema().dump(LocalResultHandler())

        with tempfile.NamedTemporaryFile() as tmp:
            with open(tmp.name, "wb") as f:
                cloudpickle.dump(42, f)

            state = Success(result=tmp.name)
            state._metadata["result"] = dict(
                raw=False, result_handler=serialized_handler
            )
            result = CloudTaskRunner(Task()).initialize_run(
                state=state, context={}, upstream_states={}
            )

        assert result.state.result == 42


def test_task_runner_doesnt_call_client_if_map_index_is_none(client):
    task = Task(name="test")

    res = CloudTaskRunner(task=task).run()

    ## assertions
    assert client.get_task_run_info.call_count == 0  # never called
    assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert states == [Running(), Success()]
    assert res.is_successful()


def test_task_runner_calls_get_task_run_info_if_map_index_is_not_none(client):
    task = Task(name="test")

    res = CloudTaskRunner(task=task).run(context={"map_index": 1})

    ## assertions
    assert client.get_task_run_info.call_count == 1  # never called
    assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
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

    db_state = Retrying(cached_inputs=dict(x=41))
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
    assert states == [Running(), Success()]


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
