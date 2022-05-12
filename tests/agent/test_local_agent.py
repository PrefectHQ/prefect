import os
import socket
import sys
import uuid
from unittest.mock import MagicMock

import pytest
from marshmallow.exceptions import ValidationError
from testfixtures.popen import MockPopen
from testfixtures import compare, LogCapture

import prefect
from prefect.agent.local import LocalAgent
from prefect.storage import (
    Docker,
    Local,
    Azure,
    GCS,
    S3,
    Webhook,
    GitLab,
    Bitbucket,
    CodeCommit,
)
from prefect.run_configs import LocalRun, KubernetesRun, UniversalRun
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult

DEFAULT_AGENT_LABELS = [
    socket.gethostname(),
]

TEST_FLOW_RUN_DATA = GraphQLResult(
    {"id": "id", "tenant_id": "tenant-id", "name": "name", "flow": {"id": "foo"}}
)


@pytest.fixture(autouse=True)
def autouse_api_key_config(config_with_api_key):
    yield config_with_api_key


def test_local_agent_init():
    agent = LocalAgent()
    assert agent.agent_config_id is None
    assert set(agent.labels) == set(DEFAULT_AGENT_LABELS)
    assert agent.name == "agent"


def test_local_agent_deduplicates_labels():
    agent = LocalAgent(labels=[socket.gethostname()])
    assert sorted(agent.labels) == sorted(DEFAULT_AGENT_LABELS)


def test_local_agent_config_options(config_with_api_key):
    agent = LocalAgent(
        name="test",
        labels=["test_label"],
        import_paths=["test_path"],
    )
    assert agent.name == "test"
    assert agent.client.api_key == config_with_api_key.cloud.api_key
    assert agent.logger
    assert agent.log_to_cloud is True
    assert agent.processes == set()
    assert agent.import_paths == ["test_path"]
    assert set(agent.labels) == {"test_label", *DEFAULT_AGENT_LABELS}


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


def test_populate_env_vars(monkeypatch, backend, config_with_api_key):
    agent = LocalAgent()

    # The python path may be a single item and we want to ensure the correct separator
    # is added so we will ensure PYTHONPATH has an item in it to start
    if not os.environ.get("PYTHONPATH", ""):
        monkeypatch.setenv("PYTHONPATH", "foobar")

    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    expected = os.environ.copy()
    expected.update(
        {
            "PYTHONPATH": os.getcwd() + os.pathsep + expected.get("PYTHONPATH", ""),
            "PREFECT__BACKEND": backend,
            "PREFECT__CLOUD__API": prefect.config.cloud.api,
            "PREFECT__CLOUD__API_KEY": config_with_api_key.cloud.api_key,
            "PREFECT__CLOUD__TENANT_ID": config_with_api_key.cloud.tenant_id,
            "PREFECT__CLOUD__AGENT__LABELS": str(DEFAULT_AGENT_LABELS),
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CONTEXT__FLOW_ID": "foo",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": "true",
            "PREFECT__LOGGING__LEVEL": "INFO",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
        }
    )

    assert env_vars == expected


@pytest.mark.parametrize("flag", [True, False])
def test_populate_env_vars_sets_log_to_cloud(flag):
    agent = LocalAgent(no_cloud_logs=flag)
    assert agent.log_to_cloud is not flag
    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)
    assert env_vars["PREFECT__CLOUD__SEND_FLOW_RUN_LOGS"] == str(not flag).lower()


def test_environment_has_api_key_from_config(config_with_api_key):
    """Check that the API key is passed through from the config via environ"""

    agent = LocalAgent()
    agent.client._get_auth_tenant = MagicMock(return_value="ID")
    env = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    assert env["PREFECT__CLOUD__API_KEY"] == config_with_api_key.cloud.api_key
    assert env["PREFECT__CLOUD__TENANT_ID"] == config_with_api_key.cloud.tenant_id


def test_environment_has_tenant_id_from_server(config_with_api_key):
    tenant_id = uuid.uuid4()

    with set_temporary_config({"cloud.tenant_id": None}):
        agent = LocalAgent()
        agent.client._get_auth_tenant = MagicMock(return_value=tenant_id)
        env = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    assert env["PREFECT__CLOUD__API_KEY"] == config_with_api_key.cloud.api_key
    assert env["PREFECT__CLOUD__TENANT_ID"] == tenant_id


def test_environment_has_api_key_from_disk(monkeypatch):
    """Check that the API key is passed through from the on disk cache"""
    tenant_id = str(uuid.uuid4())

    monkeypatch.setattr(
        "prefect.Client.load_auth_from_disk",
        MagicMock(return_value={"api_key": "TEST_KEY", "tenant_id": tenant_id}),
    )
    with set_temporary_config({"cloud.tenant_id": None}):
        agent = LocalAgent()
        env = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    assert env["PREFECT__CLOUD__API_KEY"] == "TEST_KEY"
    assert env["PREFECT__CLOUD__TENANT_ID"] == tenant_id


def test_populate_env_vars_from_agent_config():
    agent = LocalAgent(env_vars=dict(AUTH_THING="foo"))

    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    assert env_vars["AUTH_THING"] == "foo"


def test_populate_env_vars_removes_none_values():
    agent = LocalAgent(env_vars=dict(MISSING_VAR=None))

    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    assert "MISSING_VAR" not in env_vars


def test_populate_env_vars_includes_agent_labels():
    agent = LocalAgent(labels=["42", "marvin"])

    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)
    expected = str(["42", "marvin"] + DEFAULT_AGENT_LABELS)
    assert env_vars["PREFECT__CLOUD__AGENT__LABELS"] == expected


def test_populate_env_vars_import_paths():
    agent = LocalAgent(import_paths=["paths"])
    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)
    assert "paths" in env_vars["PYTHONPATH"]


def test_populate_env_vars_keep_existing_python_path(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "cool:python:path")

    agent = LocalAgent(import_paths=["paths"])
    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)

    python_path = env_vars["PYTHONPATH"]
    assert "cool:python:path" in python_path
    assert "paths" in python_path


def test_populate_env_vars_no_existing_python_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)

    agent = LocalAgent(import_paths=["paths"])
    env_vars = agent.populate_env_vars(TEST_FLOW_RUN_DATA)
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
                "flow": {"id": "foo"},
                "run_config": run.serialize(),
            }
        ),
        run,
    )
    assert env_vars["KEY1"] == "VAL1"
    assert env_vars["KEY2"] == "OVERRIDE"
    assert env_vars["PREFECT__LOGGING__LEVEL"] == "TEST"
    assert working_dir in env_vars["PYTHONPATH"]


@pytest.mark.parametrize(
    "config, agent_env_vars, run_config_env_vars, expected_logging_level",
    [
        ({"logging.level": "DEBUG"}, {}, {}, "DEBUG"),
        ({"logging.level": "DEBUG"}, {"PREFECT__LOGGING__LEVEL": "TEST2"}, {}, "TEST2"),
        (
            {"logging.level": "DEBUG"},
            {"PREFECT__LOGGING__LEVEL": "TEST2"},
            {"PREFECT__LOGGING__LEVEL": "TEST"},
            "TEST",
        ),
    ],
)
def test_prefect_logging_level_override_logic(
    config, agent_env_vars, run_config_env_vars, expected_logging_level, tmpdir
):
    with set_temporary_config(config):
        agent = LocalAgent(env_vars=agent_env_vars)
        run = LocalRun(working_dir=str(tmpdir), env=run_config_env_vars)
        env_vars = agent.populate_env_vars(
            GraphQLResult(
                {
                    "id": "id",
                    "name": "name",
                    "flow": {"id": "foo"},
                    "run_config": run.serialize(),
                }
            ),
            run,
        )
        assert env_vars["PREFECT__LOGGING__LEVEL"] == expected_logging_level


@pytest.mark.parametrize(
    "storage",
    [
        Local(directory="test"),
        GCS(bucket="test"),
        S3(bucket="test"),
        Azure(container="test"),
        GitLab("test/repo", path="path/to/flow.py"),
        Bitbucket(project="PROJECT", repo="test-repo", path="test-flow.py"),
        CodeCommit("test/repo", path="path/to/flow.py"),
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

    with pytest.raises(
        TypeError,
        match="`run_config` of type `KubernetesRun`, only `LocalRun` is supported",
    ):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "id": "id",
                    "flow": {
                        "storage": Local().serialize(),
                        "id": "foo",
                        "core_version": "0.13.0",
                    },
                    "run_config": KubernetesRun().serialize(),
                },
            )
        )

    assert not popen.called
    assert len(agent.processes) == 0


@pytest.mark.parametrize("run_config", [None, UniversalRun()])
def test_local_agent_deploy_null_or_univeral_run_config(monkeypatch, run_config):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()

    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "id": "id",
                "flow": {
                    "storage": Local().serialize(),
                    "id": "foo",
                    "core_version": "0.13.0",
                },
                "run_config": run_config.serialize() if run_config else None,
            },
        )
    )

    assert popen.called
    assert len(agent.processes) == 1


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
                    "id": "foo",
                    "core_version": "0.13.0",
                },
                "run_config": LocalRun(working_dir=working_dir).serialize(),
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
                        "id": "foo",
                        "core_version": "0.13.0",
                    },
                    "run_config": LocalRun(working_dir=working_dir).serialize(),
                },
            )
        )

    assert not popen.called
    assert not agent.processes


def test_generate_supervisor_conf_with_key():
    agent = LocalAgent()

    conf = agent.generate_supervisor_conf(
        key="key",
        tenant_id="tenant",
        labels=["label"],
        import_paths=["path"],
        env_vars={"TESTKEY": "TESTVAL"},
    )

    assert "-k key" in conf
    assert "--tenant-id tenant" in conf
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
            (("agent", "INFO", "Process PID 1234 returned non-zero exit code 1!"),),
        ),
        (
            2,
            True,
            (("agent", "INFO", "Process PID 1234 returned non-zero exit code 2!"),),
        ),
    ),
)
def test_local_agent_heartbeat(monkeypatch, returncode, show_flow_logs, logs):
    popen = MockPopen()
    # expect a process to be called with the following command (with specified behavior)
    popen.set_command(
        [sys.executable, "-m", "prefect", "execute", "flow-run"],
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
