import logging
import socket
import time
from unittest.mock import MagicMock

import pytest

from prefect.agent import Agent
from prefect.engine.state import Scheduled
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.exceptions import AuthorizationError
from prefect.utilities.graphql import GraphQLResult


def test_agent_init(cloud_api):
    agent = Agent()
    assert agent


def test_multiple_agent_init_doesnt_duplicate_logs(cloud_api):
    a, b, c = Agent(), Agent(), Agent()
    assert len(c.logger.handlers) == 1


def test_agent_config_options(cloud_api):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent()
        assert agent.agent_config_id == None
        assert agent.labels == []
        assert agent.env_vars == dict()
        assert agent.max_polls is None
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.name == "agent"
        assert agent.logger
        assert agent.logger.name == "agent"


def test_agent_name_set_options(monkeypatch, cloud_api):
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


def test_agent_log_level(cloud_api):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent()
        assert agent.logger.level == 20


def test_agent_log_level_responds_to_config(cloud_api):
    with set_temporary_config(
        {
            "cloud.agent.auth_token": "TEST_TOKEN",
            "cloud.agent.level": "DEBUG",
            "cloud.agent.agent_address": "http://localhost:8000",
        }
    ):
        agent = Agent()
        assert agent.logger.level == 10
        assert agent.agent_address == "http://localhost:8000"


def test_agent_env_vars(cloud_api):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent(env_vars=dict(AUTH_THING="foo"))
        assert agent.env_vars == dict(AUTH_THING="foo")


def test_agent_env_vars_from_config(cloud_api):
    with set_temporary_config(
        {
            "cloud.agent.auth_token": "TEST_TOKEN",
            "cloud.agent.env_vars": {"test1": "test2", "test3": "test4"},
        }
    ):
        agent = Agent()
        assert agent.env_vars == {"test1": "test2", "test3": "test4"}


def test_agent_max_polls(cloud_api):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent(max_polls=10)
        assert agent.max_polls == 10


def test_agent_labels(cloud_api):
    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = Agent(labels=["test", "2"])
        assert agent.labels == ["test", "2"]


def test_agent_labels_from_config_var(cloud_api):
    with set_temporary_config({"cloud.agent.labels": ["test", "2"]}):
        agent = Agent()
        assert agent.labels == ["test", "2"]


def test_agent_log_level_debug(cloud_api):
    with set_temporary_config(
        {"cloud.agent.auth_token": "TEST_TOKEN", "cloud.agent.level": "DEBUG"}
    ):
        agent = Agent()
        assert agent.logger.level == 10


def test_agent_fails_no_auth_token(cloud_api):
    with pytest.raises(AuthorizationError):
        agent = Agent().start()


def test_agent_fails_no_runner_token(monkeypatch, cloud_api):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value=dict(
                    data=dict(auth_info=MagicMock(api_token_scope="USER"))
                )
            )
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with pytest.raises(AuthorizationError):
        agent = Agent().start()


def test_query_flow_runs(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                get_runs_in_queue=MagicMock(flow_run_ids=["id"]),
                flow_run=[GraphQLResult({"id": "id", "scheduled_start_time": 1})],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    flow_runs = agent.query_flow_runs()
    assert flow_runs == [GraphQLResult({"id": "id", "scheduled_start_time": 1})]


def test_query_flow_runs_ignores_currently_submitting_runs(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                get_runs_in_queue=MagicMock(flow_run_ids=["id1", "id2"]),
                flow_run=[GraphQLResult({"id": "id", "scheduled_start_time": 1})],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    agent.submitting_flow_runs.add("id2")
    agent.query_flow_runs()

    assert len(gql_return.call_args_list) == 2
    assert (
        'id: { _in: ["id1"] }'
        in list(gql_return.call_args_list[1][0][0]["query"].keys())[0]
    )


def test_query_flow_runs_ordered_by_start_time(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                get_runs_in_queue=MagicMock(flow_run_ids=["id"]),
                flow_run=[
                    GraphQLResult({"id": "id2", "scheduled_start_time": 200}),
                    GraphQLResult({"id": "id", "scheduled_start_time": 1}),
                ],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    flow_runs = agent.query_flow_runs()
    assert flow_runs == [
        GraphQLResult({"id": "id", "scheduled_start_time": 1}),
        GraphQLResult({"id": "id2", "scheduled_start_time": 200}),
    ]


def test_query_flow_runs_does_not_use_submitting_flow_runs_directly(
    monkeypatch, caplog, cloud_api
):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                get_runs_in_queue=MagicMock(flow_run_ids=["already-submitted-id"]),
                flow_run=[{"id": "id"}],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    agent.logger.setLevel(logging.DEBUG)
    copy_mock = MagicMock(return_value=set(["already-submitted-id"]))
    agent.submitting_flow_runs = MagicMock(copy=copy_mock)

    flow_runs = agent.query_flow_runs()

    assert flow_runs == []
    assert "1 already submitting: ['already-submitted-id']" in caplog.text
    copy_mock.assert_called_once_with()


def test_update_states_passes_no_task_runs(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(set_flow_run_state=None, set_task_run_state=None)
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    assert not agent.update_state(
        flow_run=GraphQLResult(
            {
                "id": "id",
                "serialized_state": Scheduled().serialize(),
                "version": 1,
                "task_runs": [],
            }
        )
    )


def test_update_states_passes_task_runs(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(set_flow_run_state=None, set_task_run_state=None)
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    assert not agent.update_state(
        flow_run=GraphQLResult(
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
    )


def test_mark_failed(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(set_flow_run_state=None, set_task_run_state=None)
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    agent = Agent()
    assert not agent.mark_failed(
        flow_run=GraphQLResult(
            {
                "id": "id",
                "serialized_state": Scheduled().serialize(),
                "version": 1,
                "task_runs": [],
            }
        ),
        exc=Exception(),
    )


def test_deploy_flows_passes_base_agent(cloud_api):
    agent = Agent()
    with pytest.raises(NotImplementedError):
        agent.deploy_flow(None)


def test_heartbeat_passes_base_agent(cloud_api):
    agent = Agent()
    assert not agent.heartbeat()


def test_agent_connect(monkeypatch, cloud_api):
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value="hello")))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    agent = Agent()
    assert agent.agent_connect() is None


def test_agent_connect_handled_error(monkeypatch, cloud_api):
    post = MagicMock(side_effect=Exception)
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    agent = Agent()
    assert agent.agent_connect() is None


def test_on_flow_run_deploy_attempt_removes_id(monkeypatch, cloud_api):
    agent = Agent()
    agent.submitting_flow_runs.add("id")
    agent.on_flow_run_deploy_attempt(None, "id")
    assert len(agent.submitting_flow_runs) == 0


def test_agent_process(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                set_flow_run_state=None,
                set_task_run_state=None,
                get_runs_in_queue=MagicMock(flow_run_ids=["id"]),
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
                            "scheduled_start_time": 1,
                        }
                    )
                ],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    executor = MagicMock()
    future_mock = MagicMock()
    executor.submit = MagicMock(return_value=future_mock)

    agent = Agent()
    assert agent.agent_process(executor)
    assert executor.submit.called
    assert future_mock.add_done_callback.called


def test_agent_process_no_runs_found(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                set_flow_run_state=None,
                set_task_run_state=None,
                get_runs_in_queue=MagicMock(flow_run_ids=["id"]),
                flow_run=[],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    executor = MagicMock()

    agent = Agent()
    assert not agent.agent_process(executor)
    assert not executor.submit.called


def test_agent_logs_flow_run_exceptions(monkeypatch, caplog, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(data=MagicMock(write_run_logs=MagicMock(success=True)))
    )
    client = MagicMock()
    client.return_value.write_run_logs = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock(return_value=client))

    agent = Agent()
    agent.deploy_flow = MagicMock(side_effect=Exception("Error Here"))
    agent.deploy_and_update_flow_run(
        flow_run=GraphQLResult(
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
    )

    assert client.write_run_logs.called
    client.write_run_logs.assert_called_with(
        [dict(flow_run_id="id", level="ERROR", message="Error Here", name="agent")]
    )
    assert "Logging platform error for flow run" in caplog.text


def test_agent_process_raises_exception_and_logs(monkeypatch, cloud_api):
    client = MagicMock()
    client.return_value.graphql.side_effect = ValueError("Error")
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    executor = MagicMock()

    agent = Agent()
    with pytest.raises(Exception):
        agent.agent_process(executor, "id")
        assert client.write_run_log.called


def test_agent_start_max_polls(monkeypatch, runner_token, cloud_api):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.heartbeat", heartbeat)

    agent = Agent(max_polls=1)
    agent.start()

    assert on_shutdown.called
    assert agent_process.called
    assert heartbeat.called


def test_agent_start_max_polls_count(monkeypatch, runner_token, cloud_api):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.heartbeat", heartbeat)

    agent = Agent(max_polls=2)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 2
    assert heartbeat.call_count == 1


def test_agent_start_max_polls_zero(monkeypatch, runner_token, cloud_api):
    on_shutdown = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.on_shutdown", on_shutdown)

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.heartbeat", heartbeat)

    agent = Agent(max_polls=0)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 0
    assert heartbeat.call_count == 1


def test_agent_registration_and_id(monkeypatch, cloud_api):
    monkeypatch.setattr("prefect.agent.agent.Agent._verify_token", MagicMock())
    monkeypatch.setattr(
        "prefect.agent.agent.Client.register_agent", MagicMock(return_value="ID")
    )

    agent = Agent(max_polls=1)
    agent.start()
    assert agent._register_agent() == "ID"
    assert agent.client._attached_headers == {"X-PREFECT-AGENT-ID": "ID"}


def test_agent_rerieve_config(monkeypatch, cloud_api):
    monkeypatch.setattr("prefect.agent.agent.Agent._verify_token", MagicMock())
    monkeypatch.setattr(
        "prefect.agent.agent.Client.register_agent", MagicMock(return_value="ID")
    )
    monkeypatch.setattr(
        "prefect.agent.agent.Client.get_agent_config",
        MagicMock(return_value={"settings": "yes"}),
    )

    agent = Agent(max_polls=1)
    agent.start()
    assert agent._retrieve_agent_config() == {"settings": "yes"}


def test_agent_health_check(cloud_api):
    requests = pytest.importorskip("requests")

    class TestAgent(Agent):
        def agent_connect(self):
            pass

    with socket.socket() as sock:
        sock.bind(("", 0))
        port = sock.getsockname()[1]

    agent = TestAgent(agent_address=f"http://127.0.0.1:{port}", max_polls=1)

    agent.setup()

    # May take a sec for the api server to startup
    for attempt in range(5):
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/api/health")
            break
        except Exception:
            time.sleep(0.1)
    else:
        agent.cleanup()
        assert False, "Failed to connect to health check"

    assert resp.status_code == 200

    agent.cleanup()
    assert not agent._api_server_thread.is_alive()


def test_agent_poke_api(monkeypatch, runner_token, cloud_api):
    import threading

    requests = pytest.importorskip("requests")

    def _poke_agent(agent_address):
        # May take a sec for the api server to startup
        for attempt in range(5):
            try:
                resp = requests.get(f"{agent_address}/api/health")
                break
            except Exception:
                time.sleep(0.1)
        else:
            assert False, "Failed to connect to health check"

        assert resp.status_code == 200
        # Agent API is now available. Poke agent to start processing.
        requests.get(f"{agent_address}/api/poke")

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.heartbeat", heartbeat)

    with socket.socket() as sock:
        sock.bind(("", 0))
        port = sock.getsockname()[1]

    agent_address = f"http://127.0.0.1:{port}"

    # Poke agent in separate thread as main thread is blocked by main agent
    # process waiting for loop interval to complete.
    poke_agent_thread = threading.Thread(target=_poke_agent, args=(agent_address,))
    poke_agent_thread.start()

    agent_start_time = time.time()
    agent = Agent(agent_address=agent_address, max_polls=1)
    # Override loop interval to 5 seconds.
    agent.start(_loop_intervals={0: 5.0})
    agent_stop_time = time.time()

    agent.cleanup()

    assert agent_stop_time - agent_start_time < 5.0

    assert not agent._api_server_thread.is_alive()
    assert heartbeat.call_count == 1
    assert agent_process.call_count == 1
    assert agent_connect.call_count == 1


def test_catch_errors_in_heartbeat_thread(monkeypatch, runner_token, cloud_api, caplog):
    """Check that errors in the heartbeat thread are caught, logged, and the thread keeps going"""
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", MagicMock())
    monkeypatch.setattr(
        "prefect.agent.agent.Agent.agent_connect", MagicMock(return_value="id")
    )
    heartbeat = MagicMock(side_effect=ValueError)
    monkeypatch.setattr("prefect.agent.agent.Agent.heartbeat", heartbeat)
    agent = Agent(max_polls=2)
    agent.heartbeat_period = 0.1
    agent.start()

    assert heartbeat.call_count > 1
    assert any("Error in agent heartbeat" in m for m in caplog.messages)
