from unittest.mock import MagicMock

import pytest

from prefect.agent.nomad import NomadAgent
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_nomad_agent_init():
    agent = NomadAgent()
    assert agent


def test_nomad_agent_config_options():
    with set_temporary_config(
        {"cloud.agent.api_token": "TEST_TOKEN", "cloud.agent.loop_interval": 10}
    ):
        agent = NomadAgent()
        assert agent
        assert agent.loop_interval == 10
        assert agent.client.token == "TEST_TOKEN"
        assert agent.logger


def test_nomad_agent_deploy_flows(monkeypatch):
    requests = MagicMock()
    monkeypatch.setattr("prefect.agent.nomad.agent.requests", requests)

    with set_temporary_config({"cloud.agent.api_token": "token"}):
        agent = NomadAgent()
        agent.deploy_flows(
            flow_runs=[
                GraphQLResult(
                    {
                        "flow": GraphQLResult(
                            {
                                "storage": Docker(
                                    registry_url="test",
                                    image_name="name",
                                    image_tag="tag",
                                ).serialize(),
                                "id": "id",
                            }
                        ),
                        "id": "id",
                    }
                )
            ]
        )

    assert requests.post.called
    assert requests.post.call_args[1]["json"]


def test_nomad_agent_deploy_flows_continues(monkeypatch):
    requests = MagicMock()
    monkeypatch.setattr("prefect.agent.nomad.agent.requests", requests)

    with set_temporary_config({"cloud.agent.api_token": "token"}):
        agent = NomadAgent()
        agent.deploy_flows(
            flow_runs=[
                GraphQLResult(
                    {
                        "flow": GraphQLResult(
                            {"storage": Local().serialize(), "id": "id"}
                        ),
                        "id": "id",
                    }
                )
            ]
        )

    assert not requests.post.called


def test_nomad_agent_replace_yaml():
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        flow_run = GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                    }
                ),
                "id": "id",
            }
        )

        agent = NomadAgent()
        job = agent.replace_job_spec_json(flow_run)

        assert job["Job"]["TaskGroups"][0]["Tasks"][0]["Name"] == "id"
        assert (
            job["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]["image"]
            == "test/name:tag"
        )

        env = job["Job"]["TaskGroups"][0]["Tasks"][0]["Env"]
        assert env["PREFECT__CLOUD__API"] == "https://api.prefect.io"
        assert env["PREFECT__CLOUD__AGENT__API_TOKEN"] == "token"
        assert env["PREFECT__CONTEXT__FLOW_RUN_ID"] == "id"
        assert env["PREFECT__CONTEXT__NAMESPACE"] == "default"
