from unittest.mock import MagicMock

import pytest

from prefect.agent import Agent
from prefect.engine.state import Scheduled
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.exceptions import AuthorizationError
from prefect.utilities.graphql import GraphQLResult


def test_agent_init():
    agent = Agent()
    assert agent


def test_agent_config_options():
    with set_temporary_config(
        {"cloud.agent.api_token": "TEST_TOKEN", "cloud.agent.loop_interval": 10}
    ):
        agent = Agent()
        assert agent.loop_interval == 10
        assert agent.client.token == "TEST_TOKEN"
        assert agent.logger


def test_agent_fails_no_api_token():
    with set_temporary_config({"cloud.agent.api_token": None}):
        with pytest.raises(AuthorizationError):
            agent = Agent()
            agent.query_tenant_id()


def test_query_tenant_id(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        post = MagicMock(
            return_value=MagicMock(
                json=MagicMock(return_value=dict(data=dict(tenant=[dict(id="id")])))
            )
        )
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)

        agent = Agent()
        tenant_id = agent.query_tenant_id()
        assert tenant_id == "id"


def test_query_tenant_id_not_found(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        post = MagicMock(
            return_value=MagicMock(
                json=MagicMock(return_value=dict(data=dict(tenant=[])))
            )
        )
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)

        agent = Agent()
        tenant_id = agent.query_tenant_id()
        assert not tenant_id


def test_query_flow_runs(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=MagicMock(
                    getRunsInQueue=MagicMock(flow_run_ids=["id"]),
                    flow_run=[{"id": "id"}],
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.agent.agent.Client", client)

        agent = Agent()
        flow_runs = agent.query_flow_runs(tenant_id="id")
        assert flow_runs == [{"id": "id"}]


def test_update_states_passes_empty(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=MagicMock(set_flow_run_state=None, set_task_run_state=None)
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.agent.agent.Client", client)

        agent = Agent()
        assert not agent.update_states(flow_runs=[])


def test_update_states_passes_no_task_runs(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=MagicMock(set_flow_run_state=None, set_task_run_state=None)
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.agent.agent.Client", client)

        agent = Agent()
        assert not agent.update_states(
            flow_runs=[
                GraphQLResult(
                    {
                        "id": "id",
                        "serialized_state": Scheduled().serialize(),
                        "version": 1,
                        "task_runs": [],
                    }
                )
            ]
        )


def test_update_states_passes_task_runs(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=MagicMock(set_flow_run_state=None, set_task_run_state=None)
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.agent.agent.Client", client)

        agent = Agent()
        assert not agent.update_states(
            flow_runs=[
                GraphQLResult(
                    {
                        "id": "id",
                        "serialized_state": Scheduled().serialize(),
                        "version": 1,
                        "task_runs": [
                            GraphQLResult(
                                {
                                    "id": "id",
                                    "version": 1,
                                    "serialized_state": Scheduled().serialize(),
                                }
                            )
                        ],
                    }
                )
            ]
        )


def test_deploy_flows_passes_base_agent():
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        agent = Agent()
        assert not agent.deploy_flows([])


def test_agent_connect(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        post = MagicMock(
            return_value=MagicMock(
                json=MagicMock(return_value=dict(data=dict(tenant=[dict(id="id")])))
            )
        )
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)

        agent = Agent()
        assert agent.agent_connect() == "id"


def test_agent_connect_no_tenant_id(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        post = MagicMock(
            return_value=MagicMock(
                json=MagicMock(return_value=dict(data=dict(tenant=[dict(id=None)])))
            )
        )
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)

        agent = Agent()
        with pytest.raises(ConnectionError):
            assert agent.agent_connect()


def test_agent_process(monkeypatch):
    with set_temporary_config({"cloud.agent.api_token": "token"}):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=MagicMock(
                    set_flow_run_state=None,
                    set_task_run_state=None,
                    getRunsInQueue=MagicMock(flow_run_ids=["id"]),
                    flow_run=[
                        GraphQLResult(
                            {
                                "id": "id",
                                "serialized_state": Scheduled().serialize(),
                                "version": 1,
                                "task_runs": [
                                    GraphQLResult(
                                        {
                                            "id": "id",
                                            "version": 1,
                                            "serialized_state": Scheduled().serialize(),
                                        }
                                    )
                                ],
                            }
                        )
                    ],
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.agent.agent.Client", client)

        # Assert it doesn't return everything but all functions are called properly
        agent = Agent()
        assert not agent.agent_process("id")
