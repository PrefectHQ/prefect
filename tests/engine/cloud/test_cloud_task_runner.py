import datetime
import json
import os
import tempfile
import time
import uuid
from unittest.mock import MagicMock

import cloudpickle
import pytest

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.cache_validators import all_inputs
from prefect.engine.cloud import CloudTaskRunner
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.engine.runner import ENDRUN
from prefect.engine.signals import LOOP
from prefect.engine.state import (
    Cached,
    ClientFailed,
    Failed,
    Finished,
    Queued,
    Mapped,
    Paused,
    Pending,
    Retrying,
    Running,
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
        set_task_run_state=MagicMock(
            side_effect=lambda task_run_id, version, state, cache_for: state
        ),
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


def test_task_runner_puts_cloud_in_context(client):
    @prefect.task
    def whats_in_ctx():
        return prefect.context.get("checkpointing")

    res = CloudTaskRunner(task=whats_in_ctx).run()

    assert res.is_successful()
    assert res.result is True


def test_task_runner_doesnt_call_client_if_map_index_is_none(client):
    task = Task(name="test")

    res = CloudTaskRunner(task=task).run()

    ## assertions
    assert client.get_task_run_info.call_count == 0  # never called
    assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Success
    assert client.get_latest_cached_states.call_count == 0

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert [type(s).__name__ for s in states] == ["Running", "Success"]
    assert res.is_successful()
    assert states[0].context == dict(tags=[])
    assert states[1].context == dict(tags=[])


def test_task_runner_places_task_tags_in_state_context_and_serializes_them(monkeypatch):
    task = Task(name="test", tags=["1", "2", "tag"])
    session = MagicMock()
    monkeypatch.setattr("prefect.client.client.GraphQLResult", MagicMock())
    monkeypatch.setattr(
        "prefect.client.client.requests.Session", MagicMock(return_value=session)
    )

    res = CloudTaskRunner(task=task).run()
    assert res.is_successful()

    ## extract the variables payload from the calls to POST
    call_vars = [
        json.loads(call[1]["json"]["variables"]) for call in session.post.call_args_list
    ]

    # do some mainpulation to get the state payloads
    inputs = [c["input"]["states"][0] for c in call_vars if c is not None]
    assert inputs[0]["state"]["type"] == "Running"
    assert set(inputs[0]["state"]["context"]["tags"]) == set(["1", "2", "tag"])
    assert inputs[-1]["state"]["type"] == "Success"
    assert set(inputs[-1]["state"]["context"]["tags"]) == set(["1", "2", "tag"])


def test_task_runner_calls_get_task_run_info_if_map_index_is_not_none(client):
    task = Task(name="test")

    res = CloudTaskRunner(task=task).run(context={"map_index": 1})

    ## assertions
    assert client.get_task_run_info.call_count == 1  # never called
    assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert [type(s).__name__ for s in states] == ["Running", "Success"]


def test_task_runner_sets_mapped_state_prior_to_executor_mapping(client):
    upstream_states = {
        Edge(Task(), Task(), key="foo", mapped=True): Success(result=[1, 2])
    }

    class MyExecutor(prefect.engine.executors.LocalExecutor):
        def map(self, *args, **kwargs):
            raise SyntaxError("oops")

    with pytest.raises(SyntaxError):
        CloudTaskRunner(task=Task()).run_mapped_task(
            state=Pending(),
            upstream_states=upstream_states,
            context={},
            executor=MyExecutor(),
        )

    ## assertions
    assert client.get_task_run_info.call_count == 0  # never called
    assert client.set_task_run_state.call_count == 1  # Pending -> Mapped
    assert client.get_latest_cached_states.call_count == 0

    last_set_state = client.set_task_run_state.call_args_list[-1][1]["state"]
    assert last_set_state.map_states == [None, None]
    assert last_set_state.is_mapped()
    assert "Preparing to submit 2" in last_set_state.message


def test_task_runner_raises_endrun_if_client_cant_communicate_during_state_updates(
    monkeypatch,
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
    assert isinstance(res, ClientFailed)
    assert res.state.is_running()


def test_task_runner_queries_for_cached_states_if_task_has_caching(client):
    @prefect.task(cache_for=datetime.timedelta(minutes=1))
    def cached_task():
        return 42

    state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(days=1),
        result=Result(99, JSONResultHandler()),
    )
    old_state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        - datetime.timedelta(days=1),
        result=13,
    )
    client.get_latest_cached_states = MagicMock(return_value=[state, old_state])

    res = CloudTaskRunner(task=cached_task).run()
    assert client.get_latest_cached_states.called
    assert res.is_successful()
    assert res.is_cached()
    assert res.result == 99


def test_task_runner_validates_cached_states_if_task_has_caching(client):
    @prefect.task(
        cache_for=datetime.timedelta(minutes=1), result_handler=JSONResultHandler()
    )
    def cached_task():
        return 42

    state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        - datetime.timedelta(minutes=2),
        result=Result(99, JSONResultHandler()),
    )
    old_state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        - datetime.timedelta(days=1),
        result=Result(13, JSONResultHandler()),
    )
    client.get_latest_cached_states = MagicMock(return_value=[state, old_state])

    res = CloudTaskRunner(task=cached_task).run()
    assert client.get_latest_cached_states.called
    assert res.is_successful()
    assert res.is_cached()
    assert res.result == 42


def test_task_runner_validates_cached_state_inputs_if_task_has_caching(client):
    @prefect.task(
        cache_for=datetime.timedelta(minutes=1),
        cache_validator=all_inputs,
        result_handler=JSONResultHandler(),
    )
    def cached_task(x):
        return 42

    dull_state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(minutes=2),
        result=SafeResult("-1", JSONResultHandler()),
    )
    state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(minutes=2),
        result=SafeResult("99", JSONResultHandler()),
        cached_inputs={"x": SafeResult("2", result_handler=JSONResultHandler())},
    )
    client.get_latest_cached_states = MagicMock(return_value=[dull_state, state])

    res = CloudTaskRunner(task=cached_task).check_task_is_cached(
        Pending(), inputs={"x": Result(2, result_handler=JSONResultHandler())}
    )
    assert client.get_latest_cached_states.called
    assert res.is_successful()
    assert res.is_cached()
    assert res.result == 99


def test_task_runner_validates_cached_state_inputs_with_upstream_handlers_if_task_has_caching(
    client,
):
    class Handler(ResultHandler):
        def read(self, val):
            return 1337

    @prefect.task(
        cache_for=datetime.timedelta(minutes=1),
        cache_validator=all_inputs,
        result_handler=JSONResultHandler(),
    )
    def cached_task(x):
        return 42

    dull_state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(minutes=2),
        result=SafeResult("-1", JSONResultHandler()),
    )
    state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(minutes=2),
        result=SafeResult("99", JSONResultHandler()),
        cached_inputs={"x": SafeResult("2", result_handler=JSONResultHandler())},
    )
    client.get_latest_cached_states = MagicMock(return_value=[dull_state, state])

    res = CloudTaskRunner(task=cached_task).check_task_is_cached(
        Pending(), inputs={"x": Result(2, result_handler=Handler())}
    )
    assert client.get_latest_cached_states.called
    assert res.is_pending()


def test_task_runner_validates_cached_state_inputs_if_task_has_caching_and_uses_task_handler(
    client,
):
    class Handler(ResultHandler):
        def read(self, val):
            return 1337

    @prefect.task(
        cache_for=datetime.timedelta(minutes=1),
        cache_validator=all_inputs,
        result_handler=Handler(),
    )
    def cached_task(x):
        return 42

    dull_state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(minutes=2),
        result=SafeResult("-1", JSONResultHandler()),
    )
    state = Cached(
        cached_result_expiration=datetime.datetime.utcnow()
        + datetime.timedelta(minutes=2),
        result=SafeResult("99", JSONResultHandler()),
        cached_inputs={"x": SafeResult("2", result_handler=JSONResultHandler())},
    )
    client.get_latest_cached_states = MagicMock(return_value=[dull_state, state])

    res = CloudTaskRunner(task=cached_task).check_task_is_cached(
        Pending(), inputs={"x": Result(2, result_handler=JSONResultHandler())}
    )
    assert client.get_latest_cached_states.called
    assert res.is_successful()
    assert res.is_cached()
    assert res.result == 1337


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
    monkeypatch,
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
    set_task_run_state = MagicMock(
        side_effect=lambda task_run_id, version, state, cache_for: state
    )
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
    set_task_run_state = MagicMock(
        side_effect=lambda task_run_id, version, state, cache_for: state
    )
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
        with tempfile.TemporaryDirectory() as call_dir:
            fname = os.path.join(call_dir, "heartbeat.txt")

            def update(*args, **kwargs):
                with open(fname, "a") as f:
                    f.write("called\n")

            @prefect.task
            def sleeper():
                time.sleep(2)

            def multiprocessing_helper(executor):
                set_task_run_state = MagicMock(
                    side_effect=lambda task_run_id, version, state, cache_for: state
                )
                client = MagicMock(set_task_run_state=set_task_run_state)
                monkeypatch.setattr(
                    "prefect.engine.cloud.task_runner.Client",
                    MagicMock(return_value=client),
                )
                runner = CloudTaskRunner(task=sleeper)
                runner._heartbeat = update
                with set_temporary_config({"cloud.heartbeat_interval": 0.025}):
                    return runner.run(executor=executor)

            with executor.start():
                fut = executor.submit(multiprocessing_helper, executor=executor)
                res = executor.wait(fut)

            with open(fname, "r") as g:
                results = g.read()

        assert res.is_successful()
        assert len(results.split()) >= 50

    @pytest.mark.parametrize("executor", ["local", "sync", "mthread"], indirect=True)
    def test_task_runner_has_a_heartbeat_with_timeouts(self, executor, monkeypatch):
        with tempfile.TemporaryDirectory() as call_dir:
            fname = os.path.join(call_dir, "heartbeat.txt")

            def update(*args, **kwargs):
                with open(fname, "a") as f:
                    f.write("called\n")

            @prefect.task(timeout=1)
            def sleeper():
                time.sleep(2)

            def multiprocessing_helper(executor):
                set_task_run_state = MagicMock(
                    side_effect=lambda task_run_id, version, state, cache_for: state
                )
                client = MagicMock(set_task_run_state=set_task_run_state)
                monkeypatch.setattr(
                    "prefect.engine.cloud.task_runner.Client",
                    MagicMock(return_value=client),
                )
                runner = CloudTaskRunner(task=sleeper)
                runner._heartbeat = update
                with set_temporary_config({"cloud.heartbeat_interval": 0.025}):
                    return runner.run(executor=executor)

            with executor.start():
                fut = executor.submit(multiprocessing_helper, executor=executor)
                res = executor.wait(fut)

            with open(fname, "r") as g:
                results = g.read()

        assert isinstance(res, TimedOut)
        assert len(results.split()) >= 30

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_task_runner_has_a_heartbeat_only_during_execution(
        self, executor, monkeypatch
    ):
        with tempfile.TemporaryDirectory() as call_dir:
            fname = os.path.join(call_dir, "heartbeat.txt")

            def update(*args, **kwargs):
                with open(fname, "a") as f:
                    f.write("called\n")

            def multiprocessing_helper(executor):
                set_task_run_state = MagicMock(
                    side_effect=lambda task_run_id, version, state, cache_for: state
                )
                client = MagicMock(set_task_run_state=set_task_run_state)
                monkeypatch.setattr(
                    "prefect.engine.cloud.task_runner.Client",
                    MagicMock(return_value=client),
                )
                runner = CloudTaskRunner(task=Task())
                runner.cache_result = lambda *args, **kwargs: time.sleep(0.2)
                runner._heartbeat = update
                with set_temporary_config({"cloud.heartbeat_interval": 0.05}):
                    return runner.run(executor=executor)

            with executor.start():
                fut = executor.submit(multiprocessing_helper, executor=executor)
                res = executor.wait(fut)

            with open(fname, "r") as g:
                results = g.read()

        assert len(results.split()) == 1

    def test_task_runner_has_a_heartbeat_with_task_run_id(self, monkeypatch):
        set_task_run_state = MagicMock(
            side_effect=lambda task_run_id, version, state, cache_for: state
        )
        client = MagicMock(set_task_run_state=set_task_run_state)
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )
        task = Task(name="test")
        res = CloudTaskRunner(task=task).run(context={"task_run_id": 1234})

        assert res.is_successful()
        assert client.update_task_run_heartbeat.call_args[0][0] == 1234


class TestStateResultHandling:
    def test_task_runner_handles_outputs_prior_to_setting_state(self, client):
        @prefect.task(
            cache_for=datetime.timedelta(days=1), result_handler=JSONResultHandler()
        )
        def add(x, y):
            return x + y

        result = Result(1, result_handler=JSONResultHandler())
        assert result.safe_value is NoResult

        x_state, y_state = Success(result=result), Success(result=result)

        upstream_states = {
            Edge(Task(), Task(), key="x"): x_state,
            Edge(Task(), Task(), key="y"): y_state,
        }

        res = CloudTaskRunner(task=add).run(upstream_states=upstream_states)
        assert result.safe_value != NoResult  # proves was handled

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert (
            client.set_task_run_state.call_count == 3
        )  # Pending -> Running -> Successful -> Cached

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()
        assert states[1].is_successful()
        assert isinstance(states[2], Cached)
        assert states[2].cached_inputs == dict(x=result, y=result)
        assert states[2].result == 2

    def test_task_runner_errors_if_no_result_provided_as_input(self, client):
        @prefect.task
        def add(x, y):
            return x + y

        base_state = prefect.serialization.state.StateSchema().load({"type": "Success"})
        x_state, y_state = base_state, base_state

        upstream_states = {
            Edge(Task(), Task(), key="x"): x_state,
            Edge(Task(), Task(), key="y"): y_state,
        }

        res = CloudTaskRunner(task=add).run(upstream_states=upstream_states)
        assert res.is_failed()
        assert "unsupported operand" in res.message

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert client.set_task_run_state.call_count == 2  # Pending -> Running -> Failed

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()  # this isn't ideal, it's a little confusing
        assert states[1].is_failed()
        assert "unsupported operand" in states[1].message

    def test_task_runner_sends_checkpointed_success_states_to_cloud(self, client):
        handler = JSONResultHandler()

        @prefect.task(checkpoint=True, result_handler=handler)
        def add(x, y):
            return x + y

        x_state, y_state = Success(result=Result(1)), Success(result=Result(1))

        upstream_states = {
            Edge(Task(), Task(), key="x"): x_state,
            Edge(Task(), Task(), key="y"): y_state,
        }

        res = CloudTaskRunner(task=add).run(upstream_states=upstream_states)

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert (
            client.set_task_run_state.call_count == 2
        )  # Pending -> Running -> Successful

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()
        assert states[1].is_successful()
        assert states[1]._result.safe_value == SafeResult("2", result_handler=handler)

    def test_task_runner_handles_inputs_prior_to_setting_state(self, client):
        @prefect.task(max_retries=1, retry_delay=datetime.timedelta(days=1))
        def add(x, y):
            return x + y

        x = Result(1, result_handler=JSONResultHandler())
        y = Result("0", result_handler=JSONResultHandler())
        state = Pending(cached_inputs=dict(x=x, y=y))
        x_state = Success()
        y_state = Success()
        upstream_states = {
            Edge(Task(), Task(), key="x"): x_state,
            Edge(Task(), Task(), key="y"): y_state,
        }
        res = CloudTaskRunner(task=add).run(
            state=state, upstream_states=upstream_states
        )
        assert x.safe_value != NoResult
        assert y.safe_value != NoResult

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert (
            client.set_task_run_state.call_count == 3
        )  # Pending -> Running -> Failed -> Retrying

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()
        assert states[1].is_failed()
        assert isinstance(states[2], Retrying)
        assert states[2].cached_inputs == dict(x=x, y=y)


def test_state_handler_failures_are_handled_appropriately(client, caplog):
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
    assert isinstance(states[1].result, SyntaxError)

    error_logs = [r.message for r in caplog.records if r.levelname == "ERROR"]
    assert len(error_logs) == 2
    assert "This task failed somehow" in error_logs[0]
    assert "SyntaxError" in error_logs[-1]
    assert "unique" in error_logs[-1]
    assert "state handler" in error_logs[-1]


def test_task_runner_performs_retries_for_short_delays(client):
    global_list = []

    @prefect.task(max_retries=1, retry_delay=datetime.timedelta(seconds=0))
    def noop():
        if global_list:
            return
        else:
            global_list.append(0)
            raise ValueError("oops")

    client.get_task_run_info.side_effect = [MagicMock(version=i) for i in range(4, 7)]
    res = CloudTaskRunner(task=noop).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={},
        executor=prefect.engine.executors.LocalExecutor(),
    )

    ## assertions
    assert res.is_successful()
    assert client.get_task_run_info.call_count == 1  # called once on the retry
    assert (
        client.set_task_run_state.call_count == 5
    )  # Pending -> Running -> Failed -> Retrying -> Running -> Success
    versions = [call[1]["version"] for call in client.set_task_run_state.call_args_list]
    assert versions == [1, 2, 3, 4, 5]


def test_task_runner_handles_looping(client):
    @prefect.task
    def looper():
        if prefect.context.get("task_loop_count", 1) < 3:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + 10)
        return prefect.context.get("task_loop_result")

    res = CloudTaskRunner(task=looper).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={},
        executor=prefect.engine.executors.LocalExecutor(),
    )

    ## assertions
    assert res.is_successful()
    assert client.get_task_run_info.call_count == 0
    assert (
        client.set_task_run_state.call_count == 6
    )  # Pending -> Running -> Looped (1) -> Running -> Looped (2) -> Running -> Success
    versions = [call[1]["version"] for call in client.set_task_run_state.call_args_list]
    assert versions == [1, 2, 3, 4, 5, 6]


def test_task_runner_handles_looping_with_no_result(client):
    @prefect.task
    def looper():
        if prefect.context.get("task_loop_count", 1) < 3:
            raise LOOP()
        return 42

    res = CloudTaskRunner(task=looper).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={},
        executor=prefect.engine.executors.LocalExecutor(),
    )

    ## assertions
    assert res.is_successful()
    assert client.get_task_run_info.call_count == 0
    assert (
        client.set_task_run_state.call_count == 6
    )  # Pending -> Running -> Looped (1) -> Running -> Looped (2) -> Running -> Success
    versions = [call[1]["version"] for call in client.set_task_run_state.call_args_list]
    assert versions == [1, 2, 3, 4, 5, 6]


def test_task_runner_handles_looping_with_retries_with_no_result(client):
    # note that looping with retries _requires_ a result handler in Cloud
    @prefect.task(
        max_retries=1,
        retry_delay=datetime.timedelta(seconds=0),
        result_handler=JSONResultHandler(),
    )
    def looper():
        if (
            prefect.context.get("task_loop_count") == 2
            and prefect.context.get("task_run_count", 1) == 1
        ):
            raise ValueError("Stop")
        if prefect.context.get("task_loop_count", 1) < 3:
            raise LOOP()
        return 42

    client.get_task_run_info.side_effect = [MagicMock(version=i) for i in range(6, 9)]
    res = CloudTaskRunner(task=looper).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={},
        executor=prefect.engine.executors.LocalExecutor(),
    )

    ## assertions
    assert res.is_successful()
    assert client.get_task_run_info.call_count == 1  # called once for retry
    assert (
        client.set_task_run_state.call_count == 9
    )  # Pending -> Running -> Looped (1) -> Running -> Failed -> Retrying -> Running -> Looped(2) -> Running -> Success
    versions = [call[1]["version"] for call in client.set_task_run_state.call_args_list]
    assert versions == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_task_runner_handles_looping_with_retries(client):
    # note that looping _requires_ a result handler in Cloud
    @prefect.task(
        max_retries=1,
        retry_delay=datetime.timedelta(seconds=0),
        result_handler=JSONResultHandler(),
    )
    def looper():
        if (
            prefect.context.get("task_loop_count") == 2
            and prefect.context.get("task_run_count", 1) == 1
        ):
            raise ValueError("Stop")
        if prefect.context.get("task_loop_count", 1) < 3:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + 10)
        return prefect.context.get("task_loop_result")

    client.get_task_run_info.side_effect = [MagicMock(version=i) for i in range(6, 9)]
    res = CloudTaskRunner(task=looper).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={},
        executor=prefect.engine.executors.LocalExecutor(),
    )

    ## assertions
    assert res.is_successful()
    assert client.get_task_run_info.call_count == 1  # called once for retry
    assert (
        client.set_task_run_state.call_count == 9
    )  # Pending -> Running -> Looped (1) -> Running -> Failed -> Retrying -> Running -> Looped(2) -> Running -> Success
    versions = [call[1]["version"] for call in client.set_task_run_state.call_args_list]
    assert versions == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_cloud_task_runner_respects_queued_states_from_cloud(client):
    calls = []

    def queued_mock(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return Queued()  # immediate start time
        else:
            return kwargs.get("state")

    client.set_task_run_state = queued_mock

    @prefect.task
    def tagged_task():
        pass

    res = CloudTaskRunner(task=tagged_task).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={},
        executor=prefect.engine.executors.LocalExecutor(),
    )

    assert res.is_successful()
    assert len(calls) == 3  # Running -> Running -> Success
    assert [type(c["state"]).__name__ for c in calls] == [
        "Running",
        "Running",
        "Success",
    ]


def test_cloud_task_runner_handles_retries_with_queued_states_from_cloud(client):
    calls = []

    def queued_mock(*args, **kwargs):
        calls.append(kwargs)
        # first retry attempt will get queued
        if len(calls) == 4:
            return Queued()  # immediate start time
        else:
            return kwargs.get("state")

    client.set_task_run_state = queued_mock

    @prefect.task(max_retries=2, retry_delay=datetime.timedelta(seconds=0))
    def tagged_task(x):
        if prefect.context.get("task_run_count", 1) == 1:
            raise ValueError("gimme a sec")
        return x

    upstream_result = Result(value=42, result_handler=JSONResultHandler())
    res = CloudTaskRunner(task=tagged_task).run(
        context={"task_run_version": 1},
        state=None,
        upstream_states={
            Edge(Task(), tagged_task, key="x"): Success(result=upstream_result)
        },
        executor=prefect.engine.executors.LocalExecutor(),
    )

    assert res.is_successful()
    assert res.result == 42
    assert (
        len(calls) == 6
    )  # Running -> Failed -> Retrying -> Queued -> Running -> Success
    assert [type(c["state"]).__name__ for c in calls] == [
        "Running",
        "Failed",
        "Retrying",
        "Running",
        "Running",
        "Success",
    ]

    # ensures result handler was called and persisted
    assert calls[2]["state"].cached_inputs["x"].safe_value.value == "42"
