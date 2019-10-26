from unittest.mock import MagicMock

import pytest

from prefect.agent import Agent
from prefect.engine.state import Scheduled
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.exceptions import AuthorizationError
from prefect.utilities.graphql import GraphQLResult


def test_agent_init(runner_token):
    agent = Agent()
    assert agent


def test_agent_config_options(runner_token):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent()
        assert agent.labels == []
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.name == "agent"
        assert agent.logger
        assert agent.logger.name == "agent"


def test_agent_name_set_options(runner_token, monkeypatch):
    # Default
    agent = Agent()
    assert agent.name == "agent"
    assert agent.logger.name == "agent"

    # Init arg
    agent = Agent(name="test1")
    assert agent.name == "test1"
    assert agent.logger.name == "test1"

    # Config
    with set_temporary_config({"cloud.agent.name": "test2"}):
        agent = Agent()
        assert agent.name == "test2"
        assert agent.logger.name == "test2"


def test_agent_log_level(runner_token):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent()
        assert agent.logger.level == 20


def test_agent_log_level_responds_to_config(runner_token):
    with set_temporary_config(
        {"cloud.agent.auth_token": "TEST_TOKEN", "cloud.agent.level": "DEBUG"}
    ):
        agent = Agent()
        assert agent.logger.level == 10


def test_agent_labels(runner_token):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent(labels=["test", "2"])
        assert agent.labels == ["test", "2"]


def test_agent_labels_from_config_var(runner_token):
    with set_temporary_config({"cloud.agent.labels": "['test', '2']"}):
        agent = Agent()
        assert agent.labels == ["test", "2"]


def test_agent_log_level_debug(runner_token):
    with set_temporary_config(
        {"cloud.agent.auth_token": "TEST_TOKEN", "cloud.agent.level": "DEBUG"}
    ):
        agent = Agent()
        assert agent.logger.level == 10


def test_agent_fails_no_auth_token():
    with pytest.raises(AuthorizationError):
        agent = Agent()
        agent.query_tenant_id()


def test_agent_fails_no_runner_token(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(data=dict(authInfo=MagicMock(apiTokenScope="USER")))
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with pytest.raises(AuthorizationError):
        agent = Agent()
        agent.query_tenant_id()


def test_query_tenant_id(monkeypatch, runner_token):
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


def test_query_tenant_id_not_found(monkeypatch, runner_token):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=dict(tenant=[]))))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    agent = Agent()
    tenant_id = agent.query_tenant_id()
    assert not tenant_id


def test_query_flow_runs(monkeypatch, runner_token):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                getRunsInQueue=MagicMock(flow_run_ids=["id"]), flow_run=[{"id": "id"}]
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    flow_runs = agent.query_flow_runs(tenant_id="id")
    assert flow_runs == [{"id": "id"}]


def test_update_states_passes_empty(monkeypatch, runner_token):
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


def test_update_states_passes_no_task_runs(monkeypatch, runner_token):
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


def test_update_states_passes_task_runs(monkeypatch, runner_token):
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


def test_deploy_flows_passes_base_agent(runner_token):
    agent = Agent()
    assert not agent.deploy_flows([])


def test_heartbeat_passes_base_agent(runner_token):
    agent = Agent()
    assert not agent.heartbeat()


def test_agent_connect(monkeypatch, runner_token):
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


def test_agent_connect_no_tenant_id(monkeypatch, runner_token):
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


def test_agent_process(monkeypatch, runner_token):
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
    assert agent.agent_process("id")


def test_agent_process_no_runs_found(monkeypatch, runner_token):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                set_flow_run_state=None,
                set_task_run_state=None,
                getRunsInQueue=MagicMock(flow_run_ids=["id"]),
                flow_run=[],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    # Assert it doesn't return everything but all functions are called properly
    agent = Agent()
    assert not agent.agent_process("id")


def test_agent_logs_flow_run_exceptions(monkeypatch, runner_token):
    gql_return = MagicMock(
        return_value=MagicMock(data=MagicMock(writeRunLog=MagicMock(success=True)))
    )
    client = MagicMock()
    client.return_value.write_run_log = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock(return_value=client))

    agent = Agent()
    agent._log_flow_run_exceptions(
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
        ],
        exc=ValueError("Error Here"),
    )

    assert client.write_run_log.called
    client.write_run_log.assert_called_with(
        flow_run_id="id", level="ERROR", message="Error Here", name="agent"
    )


def test_agent_logs_flow_run_exceptions_no_flow_runs(monkeypatch, runner_token):
    gql_return = MagicMock(
        return_value=MagicMock(data=MagicMock(writeRunLog=MagicMock(success=True)))
    )
    client = MagicMock()
    client.return_value.write_run_log = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock(return_value=client))

    agent = Agent()
    agent._log_flow_run_exceptions(flow_runs=[], exc=ValueError("Error Here"))

    assert not client.write_run_log.called


def test_agent_process_raises_exception_and_logs(monkeypatch, runner_token):
    client = MagicMock()
    client.return_value.graphql.side_effect = ValueError("Error")
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    with pytest.raises(Exception):
        agent.agent_process("id")
        assert client.write_run_log.called
