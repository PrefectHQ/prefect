from unittest.mock import MagicMock

import pytest

from prefect import context
from prefect.agent.local import LocalAgent
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_local_agent_init(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", api)

    agent = LocalAgent()
    assert agent
    assert agent.labels == []
    assert agent.name == "agent"


def test_local_agent_config_options(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", api)
    monkeypatch.setattr("prefect.agent.local.agent.platform", "osx")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent(name="test")
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert not agent.no_pull
        assert api.call_args[1]["base_url"] == "unix://var/run/docker.sock"


def test_local_agent_daemon_url_responds_to_system(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", api)
    monkeypatch.setattr("prefect.agent.local.agent.platform", "win32")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent()
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert not agent.no_pull
        assert api.call_args[1]["base_url"] == "npipe:////./pipe/docker_engine"


def test_local_agent_config_options_populated(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", api)

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = LocalAgent(base_url="url", no_pull=True)
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.no_pull
        assert api.call_args[1]["base_url"] == "url"


def test_local_agent_no_pull(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", api)

    agent = LocalAgent()
    assert not agent.no_pull

    agent = LocalAgent(no_pull=True)
    assert agent.no_pull

    with context(no_pull=True):
        agent = LocalAgent()
        assert agent.no_pull

    with context(no_pull=False):
        agent = LocalAgent(no_pull=True)
        assert agent.no_pull

    with context(no_pull=False):
        agent = LocalAgent(no_pull=False)
        assert not agent.no_pull


def test_local_agent_ping(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    monkeypatch.setattr(
        "prefect.agent.local.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = LocalAgent()
    assert api.ping.called


def test_local_agent_ping_exception(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    api.ping.side_effect = Exception()
    monkeypatch.setattr(
        "prefect.agent.local.agent.docker.APIClient", MagicMock(return_value=api)
    )

    with pytest.raises(Exception):
        agent = LocalAgent()


def test_populate_env_vars(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", api)

    with set_temporary_config({"cloud.agent.auth_token": "token", "cloud.api": "api"}):
        agent = LocalAgent()

        env_vars = agent.populate_env_vars(GraphQLResult({"id": "id"}))

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_local_agent_deploy_flows(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.local.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = LocalAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Docker(
                                registry_url="test", image_name="name", image_tag="tag"
                            ).serialize()
                        }
                    ),
                    "id": "id",
                }
            )
        ]
    )

    assert api.pull.called
    assert api.create_container.called
    assert api.start.called

    assert api.create_container.call_args[1]["command"] == "prefect execute cloud-flow"
    assert api.start.call_args[1]["container"] == "container_id"


def test_local_agent_deploy_flows_storage_continues(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.local.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = LocalAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {"flow": GraphQLResult({"storage": Local().serialize()}), "id": "id"}
            )
        ]
    )

    assert not api.pull.called


def test_local_agent_deploy_flows_no_pull(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.local.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = LocalAgent(no_pull=True)
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Docker(
                                registry_url="test", image_name="name", image_tag="tag"
                            ).serialize()
                        }
                    ),
                    "id": "id",
                }
            )
        ]
    )

    assert not api.pull.called
    assert api.create_container.called
    assert api.start.called


def test_local_agent_deploy_flows_no_registry_does_not_pull(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.local.agent.docker.APIClient", MagicMock(return_value=api)
    )

    agent = LocalAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Docker(
                                registry_url="", image_name="name", image_tag="tag"
                            ).serialize()
                        }
                    ),
                    "id": "id",
                }
            )
        ]
    )

    assert not api.pull.called
    assert api.create_container.called
    assert api.start.called
