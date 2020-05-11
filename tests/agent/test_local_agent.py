import os
import socket
from unittest.mock import MagicMock

import pytest
from marshmallow.exceptions import ValidationError
from testfixtures.mock import call
from testfixtures.popen import MockPopen
from testfixtures import compare, LogCapture

from prefect.agent.local import LocalAgent
from prefect.environments.storage import Docker, Local, Azure, GCS, S3
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_local_agent_init(runner_token):
    agent = LocalAgent()
    assert agent
    assert set(agent.labels) == {
        socket.gethostname(),
        "azure-flow-storage",
        "s3-flow-storage",
        "gcs-flow-storage",
    }
    assert agent.name == "agent"


def test_local_agent_config_options(runner_token):
    with set_temporary_config(
        {"cloud.agent.auth_token": "TEST_TOKEN", "logging.log_to_cloud": True}
    ):
        agent = LocalAgent(
            name="test",
            labels=["test_label"],
            import_paths=["test_path"],
            hostname_label=False,
        )
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.log_to_cloud is True
        assert agent.processes == set()
        assert agent.import_paths == ["test_path"]
        assert set(agent.labels) == {
            "azure-flow-storage",
            "s3-flow-storage",
            "gcs-flow-storage",
            "test_label",
        }


@pytest.mark.parametrize("flag", [True, False])
def test_local_agent_responds_to_logging_config(runner_token, flag):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent(no_cloud_logs=flag)
        assert agent.log_to_cloud is not flag
        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )
        assert env_vars["PREFECT__LOGGING__LOG_TO_CLOUD"] == str(not flag).lower()


def test_local_agent_config_options_hostname(runner_token):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent(labels=["test_label"])
        assert set(agent.labels) == {
            "test_label",
            socket.gethostname(),
            "azure-flow-storage",
            "s3-flow-storage",
            "gcs-flow-storage",
        }


def test_populate_env_vars_uses_user_provided_env_vars(runner_token):
    with set_temporary_config(
        {
            "cloud.api": "api",
            "logging.log_to_cloud": True,
            "cloud.agent.auth_token": "token",
        }
    ):
        agent = LocalAgent(env_vars=dict(AUTH_THING="foo"))

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

    assert env_vars["AUTH_THING"] == "foo"


def test_populate_env_vars_uses_user_provided_env_vars_removes_nones(runner_token):
    with set_temporary_config(
        {
            "cloud.api": "api",
            "logging.log_to_cloud": True,
            "cloud.agent.auth_token": "token",
        }
    ):
        agent = LocalAgent(env_vars=dict(MISSING_VAR=None))

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

    assert "MISSING_VAR" not in env_vars


def test_populate_env_vars(runner_token):
    with set_temporary_config(
        {
            "cloud.api": "api",
            "logging.log_to_cloud": True,
            "cloud.agent.auth_token": "token",
        }
    ):
        agent = LocalAgent()

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CLOUD__AGENT__LABELS": str(
                [
                    socket.gethostname(),
                    "azure-flow-storage",
                    "gcs-flow-storage",
                    "s3-flow-storage",
                ]
            ),
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CONTEXT__FLOW_ID": "foo",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_populate_env_vars_includes_agent_labels(runner_token):
    with set_temporary_config(
        {
            "cloud.api": "api",
            "logging.log_to_cloud": True,
            "cloud.agent.auth_token": "token",
        }
    ):
        agent = LocalAgent(labels=["42", "marvin"])

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CLOUD__AGENT__LABELS": str(
                [
                    "42",
                    "marvin",
                    socket.gethostname(),
                    "azure-flow-storage",
                    "gcs-flow-storage",
                    "s3-flow-storage",
                ]
            ),
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CONTEXT__FLOW_ID": "foo",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_local_agent_deploy_processes_local_storage(monkeypatch, runner_token):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": Local(directory="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1


def test_local_agent_deploy_processes_gcs_storage(monkeypatch, runner_token):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": GCS(bucket="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1


def test_local_agent_deploy_processes_s3_storage(monkeypatch, runner_token):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": GCS(bucket="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1


def test_local_agent_deploy_processes_azure_storage(monkeypatch, runner_token):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": GCS(bucket="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1


def test_local_agent_deploy_storage_raises_not_supported_storage(
    monkeypatch, runner_token
):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()

    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {"id": "id", "flow": {"storage": Docker().serialize(), "id": "foo"}},
            )
        )

    assert not popen.called
    assert len(agent.processes) == 0


def test_local_agent_deploy_storage_fails_none(monkeypatch, runner_token):

    client = MagicMock()
    set_state = MagicMock()
    client.return_value.set_flow_run_state = set_state
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()

    with pytest.raises(ValidationError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult({"storage": None, "id": "foo"}),
                    "id": "id",
                    "version": 1,
                }
            )
        )

    assert not popen.called
    assert len(agent.processes) == 0

    assert client.called


def test_local_agent_deploy_import_paths(monkeypatch, runner_token):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent(import_paths=["paths"])
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": Local(directory="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1
    assert "paths" in popen.call_args[1]["env"]["PYTHONPATH"]


def test_local_agent_deploy_keep_existing_python_path(monkeypatch, runner_token):
    monkeypatch.setenv("PYTHONPATH", "cool:python:path")

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent(import_paths=["paths"])
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": Local(directory="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    python_path = popen.call_args[1]["env"]["PYTHONPATH"]

    assert popen.called
    assert len(agent.processes) == 1
    assert "cool:python:path" in python_path
    assert "paths" in python_path


def test_local_agent_deploy_no_existing_python_path(monkeypatch, runner_token):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent(import_paths=["paths"])
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": Local(directory="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1
    assert "paths" in popen.call_args[1]["env"]["PYTHONPATH"]


def test_generate_supervisor_conf(runner_token):
    agent = LocalAgent()

    conf = agent.generate_supervisor_conf(
        token="token", labels=["label"], import_paths=["path"]
    )

    assert "-t token" in conf
    assert "-l label" in conf
    assert "-p path" in conf


@pytest.mark.parametrize(
    "returncode,show_flow_logs,logs",
    (
        (0, False, None),
        (
            1,
            False,
            (("agent", "INFO", "Process PID 1234 returned non-zero exit code"),),
        ),
        (1, True, (("agent", "INFO", "Process PID 1234 returned non-zero exit code"),)),
    ),
)
def test_local_agent_heartbeat(
    monkeypatch, runner_token, returncode, show_flow_logs, logs
):
    popen = MockPopen()
    # expect a process to be called with the following command (with specified behavior)
    popen.set_command(
        "prefect execute cloud-flow",
        stdout=b"awesome output!",
        stderr=b"blerg, eRroR!",
        returncode=returncode,
        poll_count=2,
    )
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent(import_paths=["paths"], show_flow_logs=show_flow_logs)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {"storage": Local(directory="test").serialize(), "id": "foo"}
                ),
                "id": "id",
            }
        )
    )

    process = list(agent.processes)[0]
    process_call = process.root_call

    with LogCapture() as logcap:
        agent.heartbeat()
        agent.heartbeat()
        agent.heartbeat()

    # ensure the expected logs exist (or the absense of logs)
    if logs:
        logcap.check(*logs)
    else:
        logcap.check()

    # ensure the process was opened and was polled
    compare(
        popen.all_calls,
        expected=[
            process_call,
            process_call.poll(),
            process_call.poll(),
            process_call.poll(),
        ],
    )

    # the heartbeat should stop tracking upon exit
    compare(process.returncode, returncode)
    assert len(agent.processes) == 0


def test_local_agent_start_max_polls(monkeypatch, runner_token):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.heartbeat", heartbeat)

    agent = LocalAgent(max_polls=1)
    agent.start()

    assert agent_process.called
    assert heartbeat.called


def test_local_gent_start_max_polls_count(monkeypatch, runner_token):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.heartbeat", heartbeat)

    agent = LocalAgent(max_polls=2)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 2
    assert heartbeat.call_count == 2


def test_local_agent_start_max_polls_zero(monkeypatch, runner_token):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.heartbeat", heartbeat)

    agent = LocalAgent(max_polls=0)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 0
    assert heartbeat.call_count == 0
