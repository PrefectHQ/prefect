import pendulum
import pytest
import uuid
import os
import sys
from unittest.mock import MagicMock, call
from subprocess import CalledProcessError

import prefect
from prefect.backend.execution import (
    _fail_flow_run,
    _fail_flow_run_on_exception,
    _get_flow_run_scheduled_start_time,
    _get_next_task_run_start_time,
    _wait_for_flow_run_start_time,
    generate_flow_run_environ,
    execute_flow_run_in_subprocess,
)
from prefect.run_configs import UniversalRun
from prefect.engine.state import Failed, Scheduled, Success, Running, Submitted
from prefect.utilities.graphql import GraphQLResult
from prefect.utilities.configuration import set_temporary_config


CONFIG_TENANT_ID = str(uuid.uuid4())


@pytest.fixture()
def cloud_mocks(monkeypatch):
    class CloudMocks:
        FlowRunView = MagicMock()
        Client = MagicMock()

    mocks = CloudMocks()
    monkeypatch.setattr("prefect.backend.execution.FlowRunView", mocks.FlowRunView)
    monkeypatch.setattr("prefect.Client", mocks.Client)

    return mocks


class TestExecuteFlowRunInSubprocess:
    @pytest.fixture()
    def mocks(self, monkeypatch):
        class Mocks:
            subprocess = MagicMock()
            wait_for_flow_run_start_time = MagicMock()
            fail_flow_run = MagicMock()

        mocks = Mocks()
        monkeypatch.setattr("prefect.backend.execution.subprocess", mocks.subprocess)
        monkeypatch.setattr(
            "prefect.backend.execution._wait_for_flow_run_start_time",
            mocks.wait_for_flow_run_start_time,
        )
        monkeypatch.setattr(
            "prefect.backend.execution._fail_flow_run", mocks.fail_flow_run
        )

        # Since we mocked the module this error cannot be used in try/catch without
        # replacing it with the correct type
        mocks.subprocess.CalledProcessError = CalledProcessError

        return mocks

    @pytest.mark.parametrize("include_local_env", [True, False])
    def test_creates_subprocess_correctly(self, cloud_mocks, mocks, include_local_env):
        # Returned a scheduled flow run to start
        cloud_mocks.FlowRunView.from_flow_run_id().state = Scheduled()
        # Return a finished flow run after the first iteration
        cloud_mocks.FlowRunView().get_latest().state = Success()

        execute_flow_run_in_subprocess(
            "flow-run-id", include_local_env=include_local_env
        )

        # Should pass the correct flow run id to wait for
        mocks.wait_for_flow_run_start_time.assert_called_once_with("flow-run-id")

        # Merge the starting env and the env generated for a flow run
        base_env = os.environ.copy() if include_local_env else {}
        generated_env = {
            "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": "True",
            "PREFECT__LOGGING__LEVEL": "INFO",
            "PREFECT__LOGGING__FORMAT": "[%(asctime)s] %(levelname)s - %(name)s | %(message)s",
            "PREFECT__LOGGING__DATEFMT": "%Y-%m-%d %H:%M:%S%z",
            "PREFECT__BACKEND": "cloud",
            "PREFECT__CLOUD__API": "https://api.prefect.io",
            "PREFECT__CLOUD__TENANT_ID": "",
            "PREFECT__CLOUD__API_KEY": cloud_mocks.Client().api_key,
            "PREFECT__CLOUD__AUTH_TOKEN": cloud_mocks.Client().api_key,
            "PREFECT__CONTEXT__FLOW_RUN_ID": "flow-run-id",
            "PREFECT__CONTEXT__FLOW_ID": cloud_mocks.FlowRunView.from_flow_run_id().flow_id,
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
        }
        expected_env = {**base_env, **generated_env}

        # Calls the correct command w/ environment variables
        mocks.subprocess.run.assert_called_once_with(
            [sys.executable, "-m", "prefect", "execute", "flow-run"],
            env=expected_env,
        )

        # Return code is checked
        mocks.subprocess.run().check_returncode.assert_called_once()

    @pytest.mark.parametrize("start_state", [Submitted(), Running()])
    def test_fails_immediately_if_flow_run_is_being_executed_elsewhere(
        self, cloud_mocks, start_state, mocks
    ):
        cloud_mocks.FlowRunView.from_flow_run_id().state = start_state
        with pytest.raises(RuntimeError, match="already in state"):
            execute_flow_run_in_subprocess("flow-run-id")

    def test_handles_signal_interrupt(self, cloud_mocks, mocks):
        cloud_mocks.FlowRunView.from_flow_run_id().state = Scheduled()
        mocks.subprocess.run.side_effect = KeyboardInterrupt()

        # Keyboard interrupt should be re-raised
        with pytest.raises(KeyboardInterrupt):
            execute_flow_run_in_subprocess("flow-run-id")

        # Only tried to run once
        mocks.subprocess.run.assert_called_once()

        # Flow run is failed with the proper message
        mocks.fail_flow_run.assert_called_once_with(
            flow_run_id="flow-run-id", message="Flow run received an interrupt signal."
        )

    def test_handles_unexpected_exception(self, cloud_mocks, mocks):
        cloud_mocks.FlowRunView.from_flow_run_id().state = Scheduled()
        mocks.subprocess.run.side_effect = Exception("Foobar")

        # Re-raised as `RuntmeError`
        with pytest.raises(
            RuntimeError, match="encountered unexpected exception during execution"
        ):
            execute_flow_run_in_subprocess("flow-run-id")

        # Only tried to run once
        mocks.subprocess.run.assert_called_once()

        # Flow run is failed with the proper message
        mocks.fail_flow_run.assert_called_once_with(
            flow_run_id="flow-run-id",
            message=(
                "Flow run encountered unexpected exception during execution: "
                f"{Exception('Foobar')!r}"
            ),
        )

    def test_handles_bad_subprocess_result(self, cloud_mocks, mocks):
        cloud_mocks.FlowRunView.from_flow_run_id().state = Scheduled()
        mocks.subprocess.run.return_value.check_returncode.side_effect = (
            CalledProcessError(cmd="foo", returncode=1)
        )

        # Re-raised as `RuntmeError`
        with pytest.raises(RuntimeError, match="flow run process failed"):
            execute_flow_run_in_subprocess("flow-run-id")

        # Only tried to run once
        mocks.subprocess.run.assert_called_once()

        # Flow run is not failed at this time -- left to the FlowRunner
        mocks.fail_flow_run.assert_not_called()

    def test_loops_until_flow_run_is_finished(self, cloud_mocks, mocks):
        cloud_mocks.FlowRunView.from_flow_run_id().state = Scheduled()
        cloud_mocks.FlowRunView.from_flow_run_id().get_latest.side_effect = [
            MagicMock(state=Running()),
            MagicMock(state=Running()),
            MagicMock(state=Success()),
        ]

        execute_flow_run_in_subprocess("flow-run-id")

        # Ran the subprocess twice
        assert mocks.subprocess.run.call_count == 2
        # Waited each time
        assert mocks.wait_for_flow_run_start_time.call_count == 2


def test_generate_flow_run_environ():
    with set_temporary_config(
        {
            "cloud.send_flow_run_logs": "CONFIG_SEND_RUN_LOGS",
            "backend": "CONFIG_BACKEND",
            "cloud.api": "CONFIG_API",
            "cloud.tenant_id": CONFIG_TENANT_ID,
            # Deprecated tokens are ignored _always_ since 1.0.0
            "cloud.agent.auth_token": "CONFIG_AUTH_TOKEN",
            "cloud.auth_token": "CONFIG_AUTH_TOKEN",
        }
    ):
        result = generate_flow_run_environ(
            flow_run_id="flow-run-id",
            flow_id="flow-id",
            run_config=UniversalRun(
                env={
                    # Run config should take precendence for these values
                    "A": "RUN_CONFIG",
                    "B": "RUN_CONFIG",
                    "C": None,  # Null values are excluded
                    # Should not be overridable using a run config
                    "PREFECT__CONTEXT__FLOW_RUN_ID": "RUN_CONFIG",
                    "PREFECT__CONTEXT__FLOW_ID": "RUN_CONFIG",
                    "PREFECT__CLOUD__API_KEY": "RUN_CONFIG",
                    "PREFECT__CLOUD__TENANT_ID": "RUN_CONFIG",
                    "PREFECT__CLOUD__API": "RUN_CONFIG",
                    "PREFECT__BACKEND": "RUN_CONFIG",
                }
            ),
            run_api_key="api-key",
        )

    assert result == {
        # Passed via kwargs directly
        "PREFECT__CONTEXT__FLOW_RUN_ID": "flow-run-id",
        "PREFECT__CONTEXT__FLOW_ID": "flow-id",
        "PREFECT__CLOUD__API_KEY": "api-key",
        "PREFECT__CLOUD__AUTH_TOKEN": "api-key",  # Backwards compatibility for tokens
        # Set from prefect config
        "PREFECT__LOGGING__LEVEL": prefect.config.logging.level,
        "PREFECT__LOGGING__FORMAT": prefect.config.logging.format,
        "PREFECT__LOGGING__DATEFMT": prefect.config.logging.datefmt,
        "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": "CONFIG_SEND_RUN_LOGS",
        "PREFECT__BACKEND": "CONFIG_BACKEND",
        "PREFECT__CLOUD__API": "CONFIG_API",
        "PREFECT__CLOUD__TENANT_ID": CONFIG_TENANT_ID,
        # Overridden by run config
        "A": "RUN_CONFIG",
        "B": "RUN_CONFIG",
        # Hard-coded
        "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
    }


@pytest.mark.flaky
class TestWaitForFlowRunStartTime:
    @pytest.fixture()
    def timing_mocks(self, monkeypatch):
        class Mocks:
            get_flow_run_scheduled_start_time = MagicMock()
            get_next_task_run_start_time = MagicMock()
            sleep = MagicMock()
            now = MagicMock(return_value=pendulum.now())

        mocks = Mocks()
        monkeypatch.setattr(
            "prefect.backend.execution._get_flow_run_scheduled_start_time",
            mocks.get_flow_run_scheduled_start_time,
        )
        monkeypatch.setattr(
            "prefect.backend.execution._get_next_task_run_start_time",
            mocks.get_next_task_run_start_time,
        )
        monkeypatch.setattr("prefect.backend.execution.time.sleep", mocks.sleep)
        monkeypatch.setattr("prefect.backend.execution.pendulum.now", mocks.now)
        return mocks

    def test_flow_run_is_ready_immediately(self, timing_mocks):
        timing_mocks.get_flow_run_scheduled_start_time.return_value = None
        timing_mocks.get_next_task_run_start_time.return_value = None

        _wait_for_flow_run_start_time("flow-run-id")

        # Called timing functions
        timing_mocks.get_flow_run_scheduled_start_time.assert_called_once_with(
            "flow-run-id"
        )
        timing_mocks.get_next_task_run_start_time.assert_called_once_with("flow-run-id")

        # Returned without sleeping
        timing_mocks.sleep.assert_not_called()

    def test_flow_run_is_scheduled_in_the_future(self, timing_mocks):
        timing_mocks.get_flow_run_scheduled_start_time.return_value = (
            timing_mocks.now().add(seconds=10)
        )
        timing_mocks.get_next_task_run_start_time.return_value = None

        _wait_for_flow_run_start_time("flow-run-id")

        # Slept for the correct interval
        timing_mocks.sleep.assert_called_once_with(10)

    def test_task_run_is_scheduled_in_the_future(self, timing_mocks):
        timing_mocks.get_flow_run_scheduled_start_time.return_value = None
        timing_mocks.get_next_task_run_start_time.return_value = timing_mocks.now().add(
            seconds=10
        )

        _wait_for_flow_run_start_time("flow-run-id")

        # Slept for the correct interval
        timing_mocks.sleep.assert_called_once_with(10)

    def test_flow_and_task_run_are_scheduled_in_the_future(self, timing_mocks):
        timing_mocks.get_flow_run_scheduled_start_time.return_value = (
            timing_mocks.now().add(seconds=10)
        )
        timing_mocks.get_next_task_run_start_time.return_value = timing_mocks.now().add(
            seconds=20
        )

        _wait_for_flow_run_start_time("flow-run-id")

        # Slept for the correct interval in order
        timing_mocks.sleep.assert_has_calls([call(10), call(20)])

    def test_flow_run_is_scheduled_in_the_past(self, timing_mocks):
        timing_mocks.get_flow_run_scheduled_start_time.return_value = (
            timing_mocks.now().subtract(seconds=10)
        )
        timing_mocks.get_next_task_run_start_time.return_value = None

        _wait_for_flow_run_start_time("flow-run-id")

        # Did not sleep
        timing_mocks.sleep.assert_not_called()

    def test_task_run_is_scheduled_in_the_past(self, timing_mocks):
        timing_mocks.get_flow_run_scheduled_start_time.return_value = None
        timing_mocks.get_next_task_run_start_time.return_value = (
            timing_mocks.now().subtract(seconds=10)
        )

        _wait_for_flow_run_start_time("flow-run-id")

        # Did not sleep
        timing_mocks.sleep.assert_not_called()


def test_get_next_task_run_start_time_query_is_correct(cloud_mocks):
    # Just return nothing to simplify the test / cover malformed response
    cloud_mocks.Client().graphql.return_value = {}

    with pytest.raises(ValueError, match="Unexpected result"):
        _get_next_task_run_start_time("flow-run-id")

    cloud_mocks.Client().graphql.assert_called_once_with(
        {
            "query": {
                'task_run(where: { state_start_time: { _is_null: false }, flow_run_id: { _eq: "flow-run-id" }, flow_run: { state: { _eq: "Running" } } })': {
                    "state_start_time"
                }
            }
        }
    )


def test_get_next_task_run_start_time(cloud_mocks):
    start_time = pendulum.now("utc")
    cloud_mocks.Client().graphql.return_value = GraphQLResult(
        {
            "data": {
                "task_run": [
                    {"state_start_time": start_time.add(seconds=10).isoformat()},
                    {"state_start_time": start_time.isoformat()},
                    {"state_start_time": start_time.add(seconds=20).isoformat()},
                ]
            }
        }
    )

    result = _get_next_task_run_start_time("flow-run-id")
    assert result == start_time


def test_get_next_task_run_start_time_returns_null_when_no_task_runs(cloud_mocks):
    # WHen no task runs match the 'where' clause, `None` is returned

    cloud_mocks.Client().graphql.return_value = GraphQLResult(
        {"data": {"task_run": []}}
    )

    result = _get_next_task_run_start_time("flow-run-id")
    assert result is None


def test_get_flow_run_scheduled_start_time_from_state_time(cloud_mocks):
    start_time = pendulum.now("utc")
    states = [
        Scheduled(start_time=start_time.add(seconds=10)).serialize(),
        Scheduled(start_time=start_time).serialize(),
        Scheduled().serialize(),
    ]

    # Attach db "created" times to the states, the second one is the newest
    states[0]["created"] = pendulum.now().subtract(seconds=10).isoformat()
    states[1]["created"] = pendulum.now().isoformat()

    # The last state will have an empty start time and no created time to test handling
    # of malformed data
    states[2]["start_time"] = None

    cloud_mocks.Client().graphql.return_value = GraphQLResult(
        {
            "data": {
                "flow_run": [
                    {
                        "scheduled_start_time": (
                            start_time.subtract(seconds=10).isoformat()
                        ),
                        "states": states,
                    }
                ]
            }
        }
    )

    result = _get_flow_run_scheduled_start_time("flow-run-id")
    assert result == start_time


@pytest.mark.parametrize("with_states", [True, False])
def test_get_flow_run_scheduled_start_time_from_flow_run_scheduled_time(
    cloud_mocks, with_states
):
    # This occurs when there are no states available or when the states have no start
    # time on them
    states = []
    if with_states:
        states = [Failed().serialize()]
        states[0]["created"] = pendulum.now()

    start_time = pendulum.now("utc")

    cloud_mocks.Client().graphql.return_value = GraphQLResult(
        {
            "data": {
                "flow_run": [
                    {
                        "scheduled_start_time": start_time.isoformat(),
                        "states": states,
                    }
                ]
            }
        }
    )

    result = _get_flow_run_scheduled_start_time("flow-run-id")
    assert result == start_time


def test_get_flow_run_scheduled_start_time_query_is_correct(cloud_mocks):

    # Just return nothing to simplify the test / cover malformed response
    cloud_mocks.Client().graphql.return_value = {}

    with pytest.raises(ValueError, match="Unexpected result"):
        _get_flow_run_scheduled_start_time("flow-run-id")

    cloud_mocks.Client().graphql.assert_called_once_with(
        {
            "query": {
                'flow_run(where: { id: { _eq: "flow-run-id" } })': {
                    'states(where: { state: { _eq: "Scheduled" } })': {
                        "created",
                        "start_time",
                    },
                    "scheduled_start_time": True,
                }
            }
        }
    )


def test_get_flow_run_scheduled_start_time_raises_on_no_flow_runs(cloud_mocks):
    cloud_mocks.Client().graphql.return_value = {"data": {"flow_run": []}}

    with pytest.raises(ValueError, match="No flow run exists"):
        _get_flow_run_scheduled_start_time("flow-run-id")


def test_get_flow_run_scheduled_start_time_raises_on_multiple_flow_runs(cloud_mocks):
    cloud_mocks.Client().graphql.return_value = {"data": {"flow_run": [True, True]}}

    with pytest.raises(ValueError, match="Found more than one flow"):
        _get_flow_run_scheduled_start_time("flow-run-id")


@pytest.mark.parametrize("is_finished", [True, False])
def test_fail_flow_run_on_exception(monkeypatch, cloud_mocks, is_finished, caplog):
    monkeypatch.setattr("prefect.backend.execution._fail_flow_run", MagicMock())
    cloud_mocks.FlowRunView.from_flow_run_id().state.is_finished.return_value = (
        is_finished
    )

    with pytest.raises(ValueError):  # Reraises the exception
        with _fail_flow_run_on_exception(
            flow_run_id="flow-run-id", message="fail message: {exc}"
        ):
            raise ValueError("Exception message")

    # Fails in Cloud if the run is not finished already
    if is_finished:
        prefect.backend.execution._fail_flow_run.assert_not_called()
    else:
        prefect.backend.execution._fail_flow_run.assert_called_once_with(
            "flow-run-id",
            message=f"fail message: {ValueError('Exception message')!r}",
        )

    # Logs locally
    assert f"fail message: {ValueError('Exception message')!r}" in caplog.text
    assert "Traceback" in caplog.text


def test_fail_flow_run(cloud_mocks):
    _fail_flow_run(flow_run_id="flow-run-id", message="fail message")
    cloud_mocks.Client().set_flow_run_state.assert_called_once_with(
        flow_run_id="flow-run-id", state=Failed("fail message")
    )
    cloud_mocks.Client().write_run_logs.assert_called_once_with(
        [
            dict(
                flow_run_id="flow-run-id",
                name="prefect.backend.execution",
                message="fail message",
                level="ERROR",
            )
        ]
    )
