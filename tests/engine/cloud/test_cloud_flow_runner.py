import datetime
import itertools
import time
import threading
from datetime import timedelta
from unittest.mock import MagicMock

import pendulum
import pytest

import prefect
from prefect.client.client import Client, FlowRunInfoResult
from prefect.engine.cloud import CloudFlowRunner, CloudTaskRunner
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import (
    ConstantResultHandler,
    JSONResultHandler,
    ResultHandler,
    SecretResultHandler,
)
from prefect.engine.results import PrefectResult, SecretResult
from prefect.engine.runner import ENDRUN
from prefect.engine.signals import LOOP
from prefect.engine.state import (
    Cancelled,
    Cancelling,
    Failed,
    Finished,
    Pending,
    Queued,
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
from prefect.utilities.exceptions import VersionLockError


@pytest.fixture(autouse=True)
def cloud_settings(cloud_api):
    with set_temporary_config(
        {
            "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
            "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
        }
    ):
        yield


@pytest.fixture()
def client(monkeypatch):
    cloud_client = MagicMock(
        get_flow_run_info=MagicMock(return_value=MagicMock(state=None, parameters={})),
        set_flow_run_state=MagicMock(
            side_effect=lambda flow_run_id, version, state: state
        ),
        get_task_run_info=MagicMock(return_value=MagicMock(state=None)),
        set_task_run_state=MagicMock(
            side_effect=lambda task_run_id, version, state, cache_for: state
        ),
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


def test_flow_runner_calls_client_the_appropriate_number_of_times(client):
    flow = prefect.Flow(name="test")

    res = CloudFlowRunner(flow=flow).run()

    ## assertions
    assert client.get_flow_run_info.call_count == 2  # initial state & cancel check
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
    assert client.get_flow_run_info.call_count == 2  # initial state & cancel check
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
    monkeypatch,
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
    assert client.get_flow_run_info.call_count == 1  # initial state, no cancel check
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
    assert get_flow_run_info.call_count == 1  # initial state, no cancel check
    assert set_flow_run_state.call_count == 0  # never needs to update state
    assert res == db_state


@pytest.mark.parametrize(
    "state", [Finished, Success, Skipped, Failed, TimedOut, TriggerFailed]
)
def test_flow_runner_prioritizes_kwarg_states_over_db_states(
    monkeypatch, state, client
):
    flow = prefect.Flow(name="test")
    db_state = state("already", result=10)
    get_flow_run_info = MagicMock(return_value=MagicMock(state=db_state))
    client.get_flow_run_info = get_flow_run_info

    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    res = CloudFlowRunner(flow=flow).run(state=Pending("let's do this"))

    ## assertions
    assert get_flow_run_info.call_count == 2  # initial state & cancel check
    assert client.set_flow_run_state.call_count == 2  # Pending -> Running -> Success

    states = [call[1]["state"] for call in client.set_flow_run_state.call_args_list]
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


def test_flow_runner_puts_running_with_backend_in_context(client):
    @prefect.task()
    def whats_in_ctx():
        assert prefect.context.get("running_with_backend")

    flow = prefect.Flow(name="test", tasks=[whats_in_ctx])
    res = CloudFlowRunner(flow=flow).run()

    assert res.is_successful()


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


def test_flow_runner_puts_flow_run_name_in_context(monkeypatch):
    flow = prefect.Flow(name="test")

    # we can't pass a `name` argument to a mock
    # https://docs.python.org/3/library/unittest.mock.html#mock-names-and-the-name-attribute
    info_mock = MagicMock(context={})
    info_mock.name = "flow run name"
    get_flow_run_info = MagicMock(return_value=info_mock)
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

    assert res.context["flow_run_name"] == "flow run name"


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

    assert len(flow.tasks) == 1

    res = flow.run(state=Pending())

    ## assertions
    assert client.get_flow_run_info.call_count == 2  # initial state & cancel check
    assert client.set_flow_run_state.call_count == 2  # Pending -> Running -> Failed

    flow_states = [
        call[1]["state"] for call in client.set_flow_run_state.call_args_list
    ]
    assert [type(s).__name__ for s in flow_states] == ["Running", "Failed"]

    assert client.set_task_run_state.call_count == 2  # (Pending -> Running -> Finished)

    task_states = [
        call[1]["state"] for call in client.set_task_run_state.call_args_list
    ]
    assert len([s for s in task_states if s.is_running()]) == 1
    assert len([s for s in task_states if s.is_successful()]) == 0
    assert len([s for s in task_states if s.is_failed()]) == 1


def test_heartbeat_traps_errors_caused_by_client(caplog, monkeypatch):
    client = MagicMock(graphql=MagicMock(side_effect=SyntaxError))
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    runner = CloudFlowRunner(flow=prefect.Flow(name="bad"))
    res = runner._heartbeat()

    assert res is False

    log = caplog.records[0]
    assert log.levelname == "ERROR"
    assert "Heartbeat failed for Flow 'bad'" in log.message


@pytest.mark.parametrize("setting_available", [True, False])
def test_flow_runner_heartbeat_sets_command(monkeypatch, setting_available):
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )

    client.graphql.return_value.data.flow_run_by_pk.flow.settings = (
        dict(heartbeat_enabled=True) if setting_available else {}
    )

    runner = CloudFlowRunner(flow=prefect.Flow(name="test"))
    with prefect.context(flow_run_id="foo"):
        res = runner._heartbeat()

    assert res is True
    assert runner.heartbeat_cmd == ["prefect", "heartbeat", "flow-run", "-i", "foo"]


def test_flow_runner_does_not_have_heartbeat_if_disabled(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    client.graphql.return_value.data.flow_run_by_pk.flow.settings = dict(
        heartbeat_enabled=False
    )

    # set up the CloudFlowRunner
    runner = CloudFlowRunner(flow=prefect.Flow(name="test"))
    # confirm the runner's heartbeat respects the heartbeat toggle
    assert runner._heartbeat() is False


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


def test_starting_at_arbitrary_loop_index_from_cloud_context(client):
    @prefect.task
    def looper(x):
        if prefect.context.get("task_loop_count", 1) < 20:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + x)
        return prefect.context.get("task_loop_result", 0) + x

    @prefect.task
    def downstream(l):
        return l ** 2

    with prefect.Flow(name="looping", result_handler=JSONResultHandler()) as f:
        inter = looper(10)
        final = downstream(inter)

    client.get_flow_run_info = MagicMock(
        return_value=MagicMock(context={"task_loop_count": 20})
    )

    flow_state = CloudFlowRunner(flow=f).run(return_tasks=[inter, final])

    assert flow_state.is_successful()
    assert flow_state.result[inter].result == 10
    assert flow_state.result[final].result == 100


def test_cloud_task_runners_submitted_to_remote_machines_respect_original_config(
    monkeypatch,
):
    """
    This test is meant to simulate the behavior of running a Cloud Flow against an external
    cluster which has _not_ been configured for Prefect.  The idea is that the configuration
    settings which were present on the original machine are respected in the remote job, reflected
    here by having the CloudHandler called during logging and the special values present in context.
    """
    from prefect.engine.flow_runner import run_task

    def my_run_task(*args, **kwargs):
        with prefect.utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": False, "cloud.auth_token": ""}
        ):
            return run_task(*args, **kwargs)

    calls = []

    class Client(MagicMock):
        def write_run_logs(self, *args, **kwargs):
            calls.append(args)

        def set_task_run_state(self, *args, **kwargs):
            return kwargs.get("state")

        def set_flow_run_state(self, *args, **kwargs):
            return kwargs.get("state")

        def get_flow_run_info(self, *args, **kwargs):
            return MagicMock(
                id="flow_run_id",
                task_runs=[MagicMock(task_slug="log_stuff-1", id="TESTME")],
            )

    monkeypatch.setattr("prefect.engine.flow_runner.run_task", my_run_task)
    monkeypatch.setattr("prefect.client.Client", Client)
    monkeypatch.setattr("prefect.engine.cloud.task_runner.Client", Client)
    monkeypatch.setattr("prefect.engine.cloud.flow_runner.Client", Client)
    prefect.utilities.logging.prefect_logger.handlers[-1].client = Client()

    @prefect.task(result=PrefectResult())
    def log_stuff():
        logger = prefect.context.get("logger")
        logger.critical("important log right here")
        return (
            prefect.context.config.special_key,
            prefect.context.config.cloud.auth_token,
        )

    with prefect.utilities.configuration.set_temporary_config(
        {
            "logging.log_to_cloud": True,
            "special_key": 42,
            "cloud.auth_token": "original",
        }
    ):
        # captures config at init
        flow = prefect.Flow("test", tasks=[log_stuff])
        flow_state = flow.run(task_contexts={log_stuff: dict(special_key=99)})

    assert flow_state.is_successful()
    assert flow_state.result[log_stuff].result == (42, "original")

    time.sleep(0.75)
    logs = [log for call in calls for log in call[0]]
    assert len(logs) >= 5  # actual number of logs

    loggers = [c["name"] for c in logs]
    assert set(loggers) == {
        "prefect.CloudTaskRunner",
        "prefect.CloudFlowRunner",
        "prefect.log_stuff",
    }

    task_run_ids = [c["task_run_id"] for c in logs if c["task_run_id"]]
    assert set(task_run_ids) == {"TESTME"}


class TestCloudFlowRunnerQueuedState:
    queue_time = 55
    check_cancellation_interval = 8

    def do_mocked_run(
        self, client, monkeypatch, n_attempts=None, n_queries=None, query_end_state=None
    ):
        """Mock out a cloud flow run that starts in a queued state and either
        succeeds or exits early due to a state change."""
        mock_sleep = MagicMock()

        def run(*args, **kwargs):
            if n_attempts is None or mock_run.call_count < n_attempts:
                info = get_flow_run_info()
                if info.state.is_queued():
                    return Queued(
                        start_time=pendulum.now("UTC").add(seconds=self.queue_time)
                    )
                return info.state
            return Success()

        mock_run = MagicMock(side_effect=run)

        def get_flow_run_info(*args, **kwargs):
            if n_queries is None or mock_get_flow_run_info.call_count < n_queries:
                state = Queued()
            else:
                state = query_end_state
            return MagicMock(version=mock_get_flow_run_info.call_count, state=state)

        mock_get_flow_run_info = MagicMock(side_effect=get_flow_run_info)

        client.get_flow_run_info = mock_get_flow_run_info
        monkeypatch.setattr("prefect.engine.cloud.flow_runner.FlowRunner.run", mock_run)
        monkeypatch.setattr("prefect.engine.cloud.flow_runner.time_sleep", mock_sleep)

        @prefect.task
        def return_one():
            return 1

        with prefect.Flow("test-cloud-flow-runner-with-queues") as flow:
            return_one()

        with set_temporary_config(
            {"cloud.check_cancellation_interval": self.check_cancellation_interval}
        ):
            state = CloudFlowRunner(flow=flow).run()
        return state, mock_sleep, mock_run

    @pytest.mark.parametrize("n_attempts", [5, 10])
    def test_rety_queued_state_until_success(self, client, monkeypatch, n_attempts):
        state, mock_sleep, mock_run = self.do_mocked_run(
            client, monkeypatch, n_attempts=n_attempts
        )

        assert state.is_successful()
        assert mock_run.call_count == n_attempts
        sleep_times = [i[0][0] for i in mock_sleep.call_args_list]
        assert max(sleep_times) == self.check_cancellation_interval
        total_sleep_time = sum(sleep_times)
        expected_sleep_time = (n_attempts - 1) * self.queue_time
        # Slept for approximately the right amount of time. Due to processing time,
        # the amount of time spent in sleep may be slightly less.
        assert expected_sleep_time - 2 < total_sleep_time < expected_sleep_time + 2

    @pytest.mark.parametrize("n_queries", [5, 10])
    @pytest.mark.parametrize("final_state", [Cancelled(), Success()])
    def test_exit_queued_loop_early_if_no_longer_queued(
        self, client, monkeypatch, n_queries, final_state
    ):
        state, mock_sleep, mock_run = self.do_mocked_run(
            client, monkeypatch, n_queries=n_queries, query_end_state=final_state
        )

        assert type(state) == type(final_state)
        sleep_times = [i[0][0] for i in mock_sleep.call_args_list]
        assert max(sleep_times) == self.check_cancellation_interval
        total_sleep_time = sum(sleep_times)
        expected_sleep_time = n_queries * self.check_cancellation_interval
        # Slept for approximately the right amount of time. Due to processing time,
        # the amount of time spent in sleep may be slightly less.
        assert expected_sleep_time - 2 < total_sleep_time < expected_sleep_time + 2


def test_flowrunner_handles_version_lock_error(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=client)
    )
    client.set_flow_run_state.side_effect = VersionLockError()

    flow = prefect.Flow(name="test")
    runner = CloudFlowRunner(flow=flow)

    # successful state
    client.get_flow_run_state.return_value = Success()
    res = runner.call_runner_target_handlers(Pending(), Running())
    assert res.is_successful()

    # currently running
    client.get_flow_run_state.return_value = Running()
    with pytest.raises(ENDRUN):
        runner.call_runner_target_handlers(Pending(), Running())


class TestCloudFlowRunnerCancellation:
    def test_cancelling_mid_flow_run_exits_early(self, client, monkeypatch):
        trigger = threading.Event()

        def get_flow_run_info(*args, _version=itertools.count(), **kwargs):
            state = Cancelling() if trigger.is_set() else Running()
            return MagicMock(version=next(_version), state=state)

        client.get_flow_run_info = get_flow_run_info

        @prefect.task
        def inc(x):
            time.sleep(0.5)
            return x + 1

        ran_longer_than_expected = False

        @prefect.task
        def set_trigger(x):
            trigger.set()
            time.sleep(10)
            nonlocal ran_longer_than_expected
            ran_longer_than_expected = True
            return x + 1

        with prefect.Flow("test") as flow:
            a = inc(1)
            b = set_trigger(a)
            c = inc(b)

        with set_temporary_config({"cloud.check_cancellation_interval": 0.1}):
            res = CloudFlowRunner(flow=flow).run()

        assert isinstance(res, Cancelled)
        assert not ran_longer_than_expected

    def test_check_interrupt_loop_robust_to_api_errors(self, client, monkeypatch):
        trigger = threading.Event()

        error_was_raised = False

        def get_flow_run_info(*args, _call_count=itertools.count(), **kwargs):
            call_count = next(_call_count)
            import inspect

            caller_name = inspect.currentframe().f_back.f_code.co_name
            if caller_name == "interrupt_if_cancelling" and call_count % 2:
                nonlocal error_was_raised
                error_was_raised = True
                raise ValueError("Woops!")
            state = Cancelling() if trigger.is_set() else Running()
            return MagicMock(version=call_count, state=state)

        client.get_flow_run_info = get_flow_run_info

        ran_longer_than_expected = False

        @prefect.task
        def set_trigger(x):
            trigger.set()
            time.sleep(10)
            nonlocal ran_longer_than_expected
            ran_longer_than_expected = True
            return x + 1

        with prefect.Flow("test") as flow:
            set_trigger(1)

        with set_temporary_config({"cloud.check_cancellation_interval": 0.1}):
            res = CloudFlowRunner(flow=flow).run()

        assert isinstance(res, Cancelled)
        assert error_was_raised
        assert not ran_longer_than_expected

    def test_check_interrupt_loop_logging_calls_have_orig_prefect_context(
        self, client, monkeypatch
    ):
        """Cloud logging relies on many things stored in the context, we need
        to ensure the background thread has the context loaded so that logging
        works properly"""
        calls = []

        def emit(*args, **kwargs):
            calls.append(prefect.context.config.get("special_key") == 42)

        @prefect.task
        def inc(x):
            time.sleep(1)
            return x + 1

        with prefect.Flow("test") as flow:
            inc(1)

        with set_temporary_config(
            {
                "cloud.check_cancellation_interval": 0.1,
                "logging.log_to_cloud": True,
                "special_key": 42,
            }
        ):
            monkeypatch.setattr("prefect.utilities.logging.CloudHandler.emit", emit)
            CloudFlowRunner(flow=flow).run()

        # The logging was called, and all logging calls were successful
        assert calls
        assert all(calls)
