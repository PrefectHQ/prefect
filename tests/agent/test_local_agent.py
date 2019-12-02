import socket
from unittest.mock import MagicMock


from prefect.agent.local import LocalAgent
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_local_agent_init(runner_token):
    agent = LocalAgent()
    assert agent
    assert len(agent.labels) == 1
    assert agent.labels == [socket.gethostname()]
    assert agent.name == "agent"


def test_local_agent_config_options(runner_token):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent(
            name="test",
            labels=["test_label"],
            import_paths=["test_path"],
            hostname_label=False,
        )
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.processes == []
        assert agent.import_paths == ["test_path"]
        assert agent.labels == ["test_label"]


def test_local_agent_config_options_hostname(runner_token):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent(labels=["test_label"],)
        assert agent.labels == ["test_label", socket.gethostname()]


def test_populate_env_vars(runner_token):
    with set_temporary_config({"cloud.api": "api"}):
        agent = LocalAgent()

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id"}))

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AGENT__LABELS": str([socket.gethostname()]),
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_populate_env_vars_includes_agent_labels(runner_token):
    with set_temporary_config({"cloud.api": "api"}):
        agent = LocalAgent(labels=["42", "marvin"])

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id"}))

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AGENT__LABELS": str(
                ["42", "marvin", socket.gethostname()]
            ),
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_local_agent_deploy_processes(monkeypatch, runner_token):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {"storage": Local(directory="test").serialize()}
                    ),
                    "id": "id",
                }
            )
        ]
    )

    assert popen.called
    assert len(agent.processes) == 1


def test_local_agent_deploy_storage_continues_not_local(monkeypatch, runner_token):

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {"flow": GraphQLResult({"storage": Docker().serialize()}), "id": "id",}
            )
        ]
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
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {"flow": GraphQLResult({"storage": None}), "id": "id", "version": 1}
            )
        ]
    )

    assert not popen.called
    assert len(agent.processes) == 0

    assert client.called
    assert set_state.called


def test_local_agent_deploy_pwd(monkeypatch, runner_token):

    monkeypatch.setenv("PWD", "pwd")

    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {"storage": Local(directory="test").serialize()}
                    ),
                    "id": "id",
                }
            )
        ]
    )

    assert popen.called
    assert len(agent.processes) == 1
    assert "pwd" in popen.call_args[1]["env"]["PYTHONPATH"]


def test_local_agent_deploy_import_paths(monkeypatch, runner_token):
    popen = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.Popen", popen)

    agent = LocalAgent(import_paths=["paths"])
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {"storage": Local(directory="test").serialize()}
                    ),
                    "id": "id",
                }
            )
        ]
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
