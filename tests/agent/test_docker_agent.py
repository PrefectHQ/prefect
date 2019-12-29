from unittest.mock import MagicMock

import pytest

from prefect import context
from prefect.agent.docker import DockerAgent
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_docker_agent_init(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    agent = DockerAgent()
    assert agent
    assert agent.labels == []
    assert agent.name == "agent"


def test_docker_agent_config_options(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)
    monkeypatch.setattr("prefect.agent.docker.agent.platform", "osx")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = DockerAgent(name="test")
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert not agent.no_pull
        assert api.call_args[1]["base_url"] == "unix://var/run/docker.sock"


def test_docker_agent_daemon_url_responds_to_system(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)
    monkeypatch.setattr("prefect.agent.docker.agent.platform", "win32")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = DockerAgent()
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert not agent.no_pull
        assert api.call_args[1]["base_url"] == "npipe:////./pipe/docker_engine"


def test_docker_agent_config_options_populated(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = DockerAgent(base_url="url", no_pull=True)
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.no_pull
        assert api.call_args[1]["base_url"] == "url"


def test_docker_agent_no_pull(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    agent = DockerAgent()
    assert not agent.no_pull

    agent = DockerAgent(no_pull=True)
    assert agent.no_pull

    with context(no_pull=True):
        agent = DockerAgent()
        assert agent.no_pull

    with context(no_pull=False):
        agent = DockerAgent(no_pull=True)
        assert agent.no_pull

    with context(no_pull=False):
        agent = DockerAgent(no_pull=False)
        assert not agent.no_pull


def test_docker_agent_ping(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    monkeypatch.setattr(
        "prefect.agent.docker.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = DockerAgent()
    assert api.ping.called


def test_docker_agent_ping_exception(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    api.ping.side_effect = Exception()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.docker.APIClient", MagicMock(return_value=api)
    )

    with pytest.raises(Exception):
        agent = DockerAgent()


def test_populate_env_vars_uses_user_provided_env_vars(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": True,
        }
    ):
        agent = DockerAgent(env_vars=dict(AUTH_THING="foo"))

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id", "name": "name"}))

    assert env_vars["AUTH_THING"] == "foo"


def test_populate_env_vars(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": True,
        }
    ):
        agent = DockerAgent()

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id", "name": "name"}))

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CLOUD__AGENT__LABELS": "[]",
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_populate_env_vars_includes_agent_labels(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": True,
        }
    ):
        agent = DockerAgent(labels=["42", "marvin"])

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id", "name": "name"}))

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AGENT__LABELS": "['42', 'marvin']",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


@pytest.mark.parametrize("flag", [True, False])
def test_populate_env_vars_is_responsive_to_logging_config(
    monkeypatch, runner_token, flag
):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", api)

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": flag,
        }
    ):
        agent = DockerAgent(labels=["42", "marvin"])

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id", "name": "name"}))
    assert env_vars["PREFECT__LOGGING__LOG_TO_CLOUD"] == str(flag).lower()


def test_docker_agent_deploy_flow(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize()
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert api.pull.called
    assert api.create_container.called
    assert api.start.called

    assert api.create_container.call_args[1]["command"] == "prefect execute cloud-flow"
    assert api.start.call_args[1]["container"] == "container_id"


def test_docker_agent_deploy_flow_storage_raises(monkeypatch, runner_token):

    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock())
    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = DockerAgent()

    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult({"storage": Local().serialize()}),
                    "id": "id",
                    "name": "name",
                    "version": "version",
                }
            )
        )

    assert not api.pull.called


def test_docker_agent_deploy_flow_no_pull(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = DockerAgent(no_pull=True)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize()
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert not api.pull.called
    assert api.create_container.called
    assert api.start.called


def test_docker_agent_deploy_flow_no_registry_does_not_pull(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize()
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert not api.pull.called
    assert api.create_container.called
    assert api.start.called
