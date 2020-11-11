import os
import socket
from unittest.mock import MagicMock

import pytest
from marshmallow.exceptions import ValidationError
from testfixtures.popen import MockPopen
from testfixtures import compare, LogCapture

from prefect.agent.local import LocalAgent
from prefect.environments.storage import Docker, Local, Azure, GCS, S3, Webhook, GitLab
from prefect.run_configs import LocalRun, KubernetesRun
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult

DEFAULT_AGENT_LABELS = [
    socket.gethostname(),
    "azure-flow-storage",
    "gcs-flow-storage",
    "s3-flow-storage",
    "github-flow-storage",
    "webhook-flow-storage",
    "gitlab-flow-storage",
]


@pytest.fixture(autouse=True)
def mock_cloud_config(cloud_api):
    with set_temporary_config(
        {"cloud.agent.auth_token": "TEST_TOKEN", "logging.log_to_cloud": True}
    ):
        yield


def test_local_agent_init():
    agent = LocalAgent()
    assert agent.agent_config_id is None
    assert set(agent.labels) == set(DEFAULT_AGENT_LABELS)
    assert agent.name == "agent"


def test_local_agent_deduplicates_labels():
    agent = LocalAgent(labels=["azure-flow-storage"])
    assert sorted(agent.labels) == sorted(DEFAULT_AGENT_LABELS)


def test_local_agent_config_options():
    agent = LocalAgent(
        name="test",
        labels=["test_label"],
        import_paths=["test_path"],
    )
    assert agent.name == "test"
    assert agent.client.get_auth_token() == "TEST_TOKEN"
    assert agent.logger
    assert agent.log_to_cloud is True
    assert agent.processes == set()
    assert agent.import_paths == ["test_path"]
    assert set(agent.labels) == {"test_label", *DEFAULT_AGENT_LABELS}


def test_local_agent_config_no_storage_labels():
    agent = LocalAgent(
        labels=["test_label"],
        storage_labels=False,
    )
    assert set(agent.labels) == {
        socket.gethostname(),
        "test_label",
    }


@pytest.mark.parametrize("hostname_label", [True, False])
def test_local_agent_config_options_hostname(hostname_label):
    agent = LocalAgent(labels=["test_label"], hostname_label=hostname_label)
    expected = {"test_label", *DEFAULT_AGENT_LABELS}
    if not hostname_label:
        expected.discard(socket.gethostname())
    assert set(agent.labels) == expected


def test_local_agent_uses_ip_if_dockerdesktop_hostname(monkeypatch):
    monkeypatch.setattr("socket.gethostname", MagicMock(return_value="docker-desktop"))
    monkeypatch.setattr("socket.gethostbyname", MagicMock(return_value="IP"))

    agent = LocalAgent()
    assert "IP" in agent.labels


def test_populate_env_vars(monkeypatch):
    agent = LocalAgent()

    # The python path may be a single item and we want to ensure the correct separator
    # is added so we will ensure PYTHONPATH has an item in it to start
    if not os.environ.get("PYTHONPATH", ""):
        monkeypatch.setenv("PYTHONPATH", "foobar")

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )

    expected = os.environ.copy()
    expected.update(
        {
            "PYTHONPATH": os.getcwd() + os.pathsep + expected.get("PYTHONPATH", ""),
            "PREFECT__CLOUD__API": "https://api.prefect.io",
            "PREFECT__CLOUD__AUTH_TOKEN": "TEST_TOKEN",
            "PREFECT__CLOUD__AGENT__LABELS": str(DEFAULT_AGENT_LABELS),
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CONTEXT__FLOW_ID": "foo",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "INFO",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }
    )

    assert env_vars == expected


@pytest.mark.parametrize("flag", [True, False])
def test_populate_env_vars_sets_log_to_cloud(flag):
    agent = LocalAgent(no_cloud_logs=flag)
    assert agent.log_to_cloud is not flag
    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )
    assert env_vars["PREFECT__LOGGING__LOG_TO_CLOUD"] == str(not flag).lower()


def test_populate_env_vars_from_agent_config():
    agent = LocalAgent(env_vars=dict(AUTH_THING="foo"))

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )

    assert env_vars["AUTH_THING"] == "foo"


def test_populate_env_vars_removes_none_values():
    agent = LocalAgent(env_vars=dict(MISSING_VAR=None))

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )

    assert "MISSING_VAR" not in env_vars


def test_populate_env_vars_includes_agent_labels():
    agent = LocalAgent(labels=["42", "marvin"])

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )
    expected = str(["42", "marvin"] + DEFAULT_AGENT_LABELS)
    assert env_vars["PREFECT__CLOUD__AGENT__LABELS"] == expected


def test_populate_env_vars_import_paths():
    agent = LocalAgent(import_paths=["paths"])
    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )
    assert "paths" in env_vars["PYTHONPATH"]


def test_populate_env_vars_keep_existing_python_path(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "cool:python:path")

    agent = LocalAgent(import_paths=["paths"])
    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )

    python_path = env_vars["PYTHONPATH"]
    assert "cool:python:path" in python_path
    assert "paths" in python_path


def test_populate_env_vars_no_existing_python_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    agent = LocalAgent(import_paths=["paths"])
    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
    )
    assert "paths" in env_vars["PYTHONPATH"]


def test_populate_env_vars_from_run_config(tmpdir):
    agent = LocalAgent(env_vars={"KEY1": "VAL1", "KEY2": "VAL2"})
    working_dir = str(tmpdir)

    run = LocalRun(
        env={"KEY2": "OVERRIDE", "PREFECT__LOGGING__LEVEL": "TEST"},
        working_dir=working_dir,
    )

    env_vars = agent.populate_env_vars(
        GraphQLResult(
            {
                "id": "id",
                "name": "name",
                "flow": {"id": "foo", "run_config": run.serialize()},
            }
        ),
        run,
    )
    assert env_vars["KEY1"] == "VAL1"
    assert env_vars["KEY2"] == "OVERRIDE"
    assert env_vars["PREFECT__LOGGING__LEVEL"] == "TEST"
    assert working_dir in env_vars["PYTHONPATH"]


@pytest.mark.parametrize(
    "storage",
    [
        Local(directory="test"),
        GCS(bucket="test"),
        S3(bucket="test"),
        Azure(container="test"),
        GitLab("test/repo", path="path/to/flow.py"),
        Webhook(
            build_request_kwargs={"url": "test-service/upload"},
            build_request_http_method="POST",
            get_flow_request_kwargs={"url": "test-service/download"},
            get_flow_request_http_method="GET",
        ),
    ],
)
def test_local_agent_deploy_processes_valid_storage(storage, monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": storage.serialize(),
                        "id": "foo",
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
            }
        )
    )

    assert popen.called
    assert len(agent.processes) == 1


def test_local_agent_deploy_raises_unsupported_storage(monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()

    with pytest.raises(TypeError, match="Unsupported Storage type: Docker"):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "id": "id",
                    "flow": {
                        "storage": Docker().serialize(),
                        "id": "foo",
                        "core_version": "0.13.0",
                    },
                },
            )
        )

    assert not popen.called
    assert len(agent.processes) == 0


def test_local_agent_deploy_storage_fails_none(monkeypatch):
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
                    "flow": GraphQLResult(
                        {"storage": None, "id": "foo", "core_version": "0.13.0"}
                    ),
                    "id": "id",
                    "version": 1,
                }
            )
        )

    assert not popen.called
    assert len(agent.processes) == 0

    assert client.called


def test_local_agent_deploy_unsupported_run_config(monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()

    with pytest.raises(TypeError, match="Unsupported RunConfig type: Kubernetes"):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "id": "id",
                    "flow": {
                        "storage": Local().serialize(),
                        "run_config": KubernetesRun().serialize(),
                        "id": "foo",
                        "core_version": "0.13.0",
                    },
                },
            )
        )

    assert not popen.called
    assert len(agent.processes) == 0


@pytest.mark.parametrize("working_dir", [None, "existing"])
def test_local_agent_deploy_run_config_working_dir(monkeypatch, working_dir, tmpdir):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    if working_dir is not None:
        working_dir = str(tmpdir)

    agent = LocalAgent()

    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "id": "id",
                "flow": {
                    "storage": Local().serialize(),
                    "run_config": LocalRun(working_dir=working_dir).serialize(),
                    "id": "foo",
                    "core_version": "0.13.0",
                },
            },
        )
    )

    assert popen.called
    assert len(agent.processes) == 1
    assert popen.call_args[1]["cwd"] == working_dir


def test_local_agent_deploy_run_config_missing_working_dir(monkeypatch, tmpdir):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    working_dir = str(tmpdir.join("missing"))

    agent = LocalAgent()

    with pytest.raises(ValueError, match="nonexistent `working_dir`"):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "id": "id",
                    "flow": {
                        "storage": Local().serialize(),
                        "run_config": LocalRun(working_dir=working_dir).serialize(),
                        "id": "foo",
                        "core_version": "0.13.0",
                    },
                },
            )
        )

    assert not popen.called
    assert not agent.processes


def test_generate_supervisor_conf():
    agent = LocalAgent()

    conf = agent.generate_supervisor_conf(
        token="token",
        labels=["label"],
        import_paths=["path"],
        env_vars={"TESTKEY": "TESTVAL"},
    )

    assert "-t token" in conf
    assert "-l label" in conf
    assert "-p path" in conf
    assert "-e TESTKEY=TESTVAL" in conf


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
def test_local_agent_heartbeat(monkeypatch, returncode, show_flow_logs, logs):
    popen = MockPopen()
    # expect a process to be called with the following command (with specified behavior)
    popen.set_command(
        "prefect execute flow-run",
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
                    {
                        "storage": Local(directory="test").serialize(),
                        "id": "foo",
                        "core_version": "0.13.0",
                    }
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


@pytest.mark.parametrize("max_polls", [0, 1, 2])
def test_local_agent_start_max_polls(max_polls, monkeypatch, runner_token):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.LocalAgent.heartbeat", heartbeat)

    agent = LocalAgent(max_polls=max_polls)
    agent.start()

    assert agent_connect.call_count == 1
    assert agent_process.call_count == max_polls
    assert heartbeat.call_count == 1
    assert on_shutdown.call_count == 1
