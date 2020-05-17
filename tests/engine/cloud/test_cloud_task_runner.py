import datetime
import json
import os
import sys
import tempfile
import time
import uuid
from unittest.mock import MagicMock

import cloudpickle
import pendulum
import pytest
import requests
from box import Box

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.cache_validators import all_inputs, duration_only
from prefect.engine.cloud import CloudTaskRunner
from prefect.engine.result import NoResult, Result, SafeResult, NoResult
from prefect.engine.results import PrefectResult, SecretResult

from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.engine.runner import ENDRUN
from prefect.engine.signals import LOOP
from prefect.engine.state import (
    Cached,
    Cancelled,
    ClientFailed,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Queued,
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
    @prefect.task(result_handler=ResultHandler())
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
    monkeypatch.setattr("requests.Session", MagicMock(return_value=session))

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


class TestCheckTaskCached:
    def test_reads_result_if_cached_valid(self, client):
        result = PrefectResult(location="2")

        with pytest.warns(UserWarning):
            task = Task(cache_validator=duration_only, result=PrefectResult())

        state = Cached(
            result=result, cached_result_expiration=pendulum.now("utc").add(minutes=1),
        )

        client.get_latest_cached_states = MagicMock(return_value=[])

        new = CloudTaskRunner(task).check_task_is_cached(
            state=state, inputs={"a": PrefectResult(value=1)}
        )
        assert new is state
        assert new.result == 2

    def test_reads_result_using_handler_attribute_if_cached_valid(self, client):
        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.value = 53
                return self

        with pytest.warns(UserWarning):
            task = Task(cache_validator=duration_only, result=MyResult())
        result = PrefectResult(location="2")
        state = Cached(
            result=result, cached_result_expiration=pendulum.now("utc").add(minutes=1),
        )

        client.get_latest_cached_states = MagicMock(return_value=[])

        new = CloudTaskRunner(task).check_task_is_cached(
            state=state, inputs={"a": Result(1)}
        )
        assert new is state
        assert new.result == 53

    def test_reads_result_if_cached_valid_using_task_result(task, client):
        class MyResult(Result):
            def read(self, *args, **kwargs):
                self.value = 53
                return self

        task = Task(
            result=MyResult(),
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=duration_only,
        )
        state = Cached(
            result=PrefectResult(location="2"),
            cached_result_expiration=pendulum.now("utc").add(minutes=1),
        )

        client.get_latest_cached_states = MagicMock(return_value=[state])
        new = CloudTaskRunner(task).check_task_is_cached(
            state=Pending(), inputs={"a": Result(1)}
        )
        assert new is state
        assert new.result == 53

    def test_state_kwarg_is_prioritized_over_db_caches(self, client):
        task = Task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=duration_only,
            result=PrefectResult(),
        )
        state_a = Cached(
            result=PrefectResult(location="2"),
            cached_result_expiration=pendulum.now("utc").add(minutes=1),
        )
        state_b = Cached(
            result=PrefectResult(location="99"),
            cached_result_expiration=pendulum.now("utc").add(minutes=1),
        )

        client.get_latest_cached_states = MagicMock(return_value=[state_a])
        new = CloudTaskRunner(task).check_task_is_cached(
            state=state_b, inputs={"a": Result(1)}
        )
        assert new is state_b
        assert new.result == 99

    def test_task_runner_validates_cached_state_inputs_if_task_has_caching(
        self, client
    ):
        @prefect.task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=all_inputs,
            result=PrefectResult(),
        )
        def cached_task(x):
            return 42

        dull_state = Cached(
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(minutes=2),
            result=PrefectResult(location="-1"),
        )
        state = Cached(
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(minutes=2),
            result=PrefectResult(location="99"),
            cached_inputs={"x": PrefectResult(location="2")},
        )
        client.get_latest_cached_states = MagicMock(return_value=[dull_state, state])

        res = CloudTaskRunner(task=cached_task).check_task_is_cached(
            Pending(), inputs={"x": PrefectResult(value=2)}
        )
        assert client.get_latest_cached_states.called
        assert res.is_successful()
        assert res.is_cached()
        assert res.result == 99

    def test_task_runner_validates_cached_state_inputs_with_upstream_handlers_if_task_has_caching(
        self, client
    ):
        class MyResult(Result):
            def read(self, *args, **kwargs):
                new = self.copy()
                new.value = 1337
                return new

        @prefect.task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=all_inputs,
            result=PrefectResult(),
        )
        def cached_task(x):
            return 42

        dull_state = Cached(
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(minutes=2),
            result=PrefectResult(location="-1"),
        )
        state = Cached(
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(minutes=2),
            result=PrefectResult(location="99"),
            cached_inputs={"x": PrefectResult(location="2")},
        )
        client.get_latest_cached_states = MagicMock(return_value=[dull_state, state])

        res = CloudTaskRunner(task=cached_task).check_task_is_cached(
            Pending(), inputs={"x": MyResult(value=2)}
        )
        assert client.get_latest_cached_states.called
        assert res.is_pending()

    def test_task_runner_validates_cached_state_inputs_if_task_has_caching_and_uses_task_handler(
        self, client
    ):
        class MyResult(Result):
            def read(self, *args, **kwargs):
                new = self.copy()
                new.value = 1337
                return new

        @prefect.task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=all_inputs,
            result=MyResult(),
        )
        def cached_task(x):
            return 42

        dull_state = Cached(
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(minutes=2),
            result=PrefectResult(location="-1"),
        )
        state = Cached(
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(minutes=2),
            result=PrefectResult(location="99"),
            cached_inputs={"x": PrefectResult(location="2")},
        )
        client.get_latest_cached_states = MagicMock(return_value=[dull_state, state])

        res = CloudTaskRunner(task=cached_task).check_task_is_cached(
            Pending(), inputs={"x": PrefectResult(value=2)}
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
    @prefect.task(name="test", result=PrefectResult())
    def add_one(x):
        return x + 1

    db_state = Retrying(cached_inputs=dict(x=PrefectResult(value=41)))
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
    def test_heartbeat_traps_errors_caused_by_client(self, caplog, monkeypatch):
        client = MagicMock(graphql=MagicMock(side_effect=SyntaxError))
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )
        runner = CloudTaskRunner(task=Task(name="bad"))
        runner.task_run_id = None
        res = runner._heartbeat()
        assert res is False

        log = caplog.records[0]
        assert log.levelname == "ERROR"
        assert "Heartbeat failed for Task 'bad'" in log.message

    def test_heartbeat_traps_errors_caused_by_bad_attributes(self, caplog, monkeypatch):
        monkeypatch.setattr("prefect.engine.cloud.task_runner.Client", MagicMock())
        runner = CloudTaskRunner(task=Task())
        res = runner._heartbeat()
        assert res is False

        log = caplog.records[0]
        assert log.levelname == "ERROR"
        assert "Heartbeat failed for Task 'Task'" in log.message

    @pytest.mark.parametrize("setting_available", [True, False])
    def test_task_runner_heartbeat_sets_command(self, monkeypatch, setting_available):
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )
        client.graphql.return_value.data.flow_run_by_pk.flow.settings = (
            dict(heartbeat_enabled=True) if setting_available else {}
        )

        runner = CloudTaskRunner(task=Task())
        runner.task_run_id = "foo"
        res = runner._heartbeat()
        assert res is True
        assert runner.task_run_id == "foo"
        assert runner.heartbeat_cmd == ["prefect", "heartbeat", "task-run", "-i", "foo"]

    def test_task_runner_does_not_have_heartbeat_if_disabled(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=client)
        )
        client.graphql.return_value.data.flow_run_by_pk.flow.settings = dict(
            heartbeat_enabled=False
        )
        runner = CloudTaskRunner(task=Task())
        runner.task_run_id = "foo"
        res = runner._heartbeat()
        assert res is False


class TestStateResultHandling:
    def test_task_runner_handles_outputs_prior_to_setting_state(self, client):
        @prefect.task(cache_for=datetime.timedelta(days=1), result=PrefectResult())
        def add(x, y):
            return x + y

        result = PrefectResult(value=1)
        assert result.location is None

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

    @pytest.mark.parametrize("checkpoint", [True, None])
    def test_task_runner_sends_checkpointed_success_states_to_cloud(
        self, client, checkpoint
    ):
        @prefect.task(checkpoint=checkpoint, result=PrefectResult())
        def add(x, y):
            return x + y

        x_state, y_state = (
            Success(result=PrefectResult(value=1)),
            Success(result=PrefectResult(value=1)),
        )

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
        assert states[1]._result.location == "2"

    def test_task_runner_preserves_location_of_inputs_when_retrying(self, client):
        """
        If a user opts out of checkpointing via checkpoint=False, we don't want to
        surprise them by storing the result in cached_inputs.  This test ensures
        that whatever location is provided to a downstream task is the one that is used.
        """

        @prefect.task(max_retries=1, retry_delay=datetime.timedelta(days=1))
        def add(x, y):
            return x + y

        x = PrefectResult(value=1)
        y = PrefectResult(value="0", location="foo")
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

        ## assertions
        assert client.get_task_run_info.call_count == 0  # never called
        assert (
            client.set_task_run_state.call_count == 3
        )  # Pending -> Running -> Failed -> Retrying

        states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
        assert states[0].is_running()
        assert states[1].is_failed()
        assert isinstance(states[2], Retrying)
        assert states[2].cached_inputs["x"].location is None
        assert states[2].cached_inputs["y"].location == "foo"


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
    assert len(error_logs) >= 2
    assert any("This task failed somehow" in elog for elog in error_logs)
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
    @prefect.task(result_handler=ResultHandler())
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
    @prefect.task(result_handler=ResultHandler())
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

    @prefect.task(
        max_retries=2,
        retry_delay=datetime.timedelta(seconds=0),
        result=PrefectResult(),
    )
    def tagged_task(x):
        if prefect.context.get("task_run_count", 1) == 1:
            raise ValueError("gimme a sec")
        return x

    upstream_result = PrefectResult(value=42, location="42")
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

    assert calls[2]["state"].cached_inputs["x"].value == 42


class TestLoadResults:
    def test_load_results_from_upstream_reads_results(self):
        result = PrefectResult(location="1")
        state = Success(result=result)

        assert result.value is None

        t = Task(result=PrefectResult())
        edge = Edge(t, 2, key="x")
        new_state, upstreams = CloudTaskRunner(task=Task()).load_results(
            state=Pending(), upstream_states={edge: state}
        )
        assert upstreams[edge].result == 1

    def test_load_results_from_upstream_reads_results_using_upstream_handlers(self):
        class CustomResult(Result):
            def read(self, *args, **kwargs):
                return "foo-bar-baz".split("-")

        state = Success(result=PrefectResult(location="1"))
        edge = Edge(Task(result=CustomResult()), 2, key="x")
        new_state, upstreams = CloudTaskRunner(task=Task()).load_results(
            state=Pending(), upstream_states={edge: state},
        )
        assert upstreams[edge].result == ["foo", "bar", "baz"]

    def test_load_results_from_upstream_reads_secret_results(self):
        secret_result = SecretResult(prefect.tasks.secrets.PrefectSecret(name="foo"))

        state = Success(result=PrefectResult(location="foo"))

        with prefect.context(secrets=dict(foo=42)):
            edge = Edge(Task(result=secret_result), 2, key="x")
            new_state, upstreams = CloudTaskRunner(task=Task()).load_results(
                state=Pending(), upstream_states={edge: state},
            )

        assert upstreams[edge].result == 42

    def test_load_results_from_upstream_reads_cached_inputs_using_upstream_results(
        self,
    ):
        class CustomResult(Result):
            def read(self, *args, **kwargs):
                self.value = 99
                return self

        result = PrefectResult(location="1")
        state = Pending(cached_inputs=dict(x=result))
        edge = Edge(Task(result=CustomResult()), 2, key="x")
        new_state, upstreams = CloudTaskRunner(
            task=Task(result=PrefectResult())
        ).load_results(state=state, upstream_states={edge: Success(result=result)})

        assert new_state.cached_inputs["x"].value == 99


def test_task_runner_uses_upstream_result_handlers(client):
    class MyResult(Result):
        def read(self, *args, **kwargs):
            self.value = "cool"
            return self

        def write(self, *args, **kwargs):
            return self

    @prefect.task(result=PrefectResult())
    def t(x):
        return x

    success = Success(result=PrefectResult(location="1"))
    upstream_states = {Edge(Task(result=MyResult()), t, key="x"): success}
    state = CloudTaskRunner(task=t).run(upstream_states=upstream_states)
    assert state.is_successful()
    assert state.result == "cool"


def test_task_runner_doesnt_use_upstream_result_handlers_if_value_present(client):
    class MyResult(Result):
        def read(self, *args, **kwargs):
            self.value = "cool"
            return self

        def write(self, *args, **kwargs):
            return self

    @prefect.task(result=PrefectResult())
    def t(x):
        return x

    success = Success(result=PrefectResult(value=1))
    upstream_states = {Edge(Task(result=MyResult()), t, key="x"): success}
    state = CloudTaskRunner(task=t).run(upstream_states=upstream_states)
    assert state.is_successful()
    assert state.result == 1


def test_task_runner_gracefully_handles_load_results_failures(client):
    class MyResult(Result):
        def read(self, *args, **kwargs):
            raise TypeError("something is wrong!")

    @prefect.task(result=PrefectResult())
    def t(x):
        return x

    success = Success(result=MyResult(location="foo.txt"))
    upstream_states = {Edge(Task(result=MyResult()), t, key="x"): success}
    state = CloudTaskRunner(task=t).run(upstream_states=upstream_states)

    assert state.is_failed()
    assert "task results" in state.message
    assert client.set_task_run_state.call_count == 1  # Pending -> Failed

    states = [call[1]["state"] for call in client.set_task_run_state.call_args_list]
    assert [type(s).__name__ for s in states] == ["Failed"]
