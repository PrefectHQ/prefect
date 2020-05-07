from unittest.mock import MagicMock

import pytest

from prefect import context
from prefect.agent.docker import DockerAgent
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_docker_agent_init(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    assert agent
    assert agent.labels == []
    assert agent.name == "agent"


def test_docker_agent_config_options(monkeypatch, runner_token):
    import docker  # DockerAgent imports docker within the constructor

    api = MagicMock()
    monkeypatch.setattr(
        "docker.APIClient", api,
    )
    monkeypatch.setattr("prefect.agent.docker.agent.platform", "osx")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = DockerAgent(name="test")
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert not agent.no_pull
        assert api.call_args[1]["base_url"] == "unix://var/run/docker.sock"


def test_docker_agent_daemon_url_responds_to_system(monkeypatch, runner_token):
    import docker  # DockerAgent imports docker within the constructor

    api = MagicMock()
    monkeypatch.setattr(
        "docker.APIClient", api,
    )
    monkeypatch.setattr("prefect.agent.docker.agent.platform", "win32")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = DockerAgent()
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert not agent.no_pull
        assert api.call_args[1]["base_url"] == "npipe:////./pipe/docker_engine"


def test_docker_agent_config_options_populated(monkeypatch, runner_token):
    import docker  # DockerAgent imports docker within the constructor

    api = MagicMock()
    monkeypatch.setattr(
        "docker.APIClient", api,
    )

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = DockerAgent(base_url="url", no_pull=True)
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.no_pull
        assert api.call_args[1]["base_url"] == "url"


def test_docker_agent_no_pull(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

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
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    assert api.ping.called


def test_docker_agent_ping_exception(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    api.ping.side_effect = Exception()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    with pytest.raises(Exception):
        agent = DockerAgent()


def test_populate_env_vars_uses_user_provided_env_vars(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": True,
        }
    ):
        agent = DockerAgent(env_vars=dict(AUTH_THING="foo"))

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

    assert env_vars["AUTH_THING"] == "foo"


def test_populate_env_vars(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": True,
        }
    ):
        agent = DockerAgent()

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CLOUD__AGENT__LABELS": "[]",
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CONTEXT__FLOW_ID": "foo",
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

        assert env_vars == expected_vars


def test_populate_env_vars_includes_agent_labels(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    with set_temporary_config(
        {
            "cloud.agent.auth_token": "token",
            "cloud.api": "api",
            "logging.log_to_cloud": True,
        }
    ):
        agent = DockerAgent(labels=["42", "marvin"])

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )

        expected_vars = {
            "PREFECT__CLOUD__API": "api",
            "PREFECT__CLOUD__AGENT__LABELS": "['42', 'marvin']",
            "PREFECT__CLOUD__AUTH_TOKEN": "token",
            "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
            "PREFECT__CONTEXT__FLOW_ID": "foo",
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
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    with set_temporary_config(
        {"cloud.agent.auth_token": "token", "cloud.api": "api",}
    ):
        agent = DockerAgent(labels=["42", "marvin"], no_cloud_logs=flag)

        env_vars = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}})
        )
    assert env_vars["PREFECT__LOGGING__LOG_TO_CLOUD"] == str(not flag).lower()


def test_docker_agent_deploy_flow(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    api.create_host_config.return_value = {"AutoRemove": True}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
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

    assert api.create_host_config.call_args[1]["auto_remove"] is True
    assert api.create_container.call_args[1]["command"] == "prefect execute cloud-flow"
    assert api.create_container.call_args[1]["host_config"]["AutoRemove"] is True
    assert api.start.call_args[1]["container"] == "container_id"


def test_docker_agent_deploy_flow_storage_raises(monkeypatch, runner_token):

    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock())
    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()

    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {"storage": Local().serialize(), "id": "foo"}
                    ),
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
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent(no_pull=True)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
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


def test_docker_agent_deploy_flow_show_flow_logs(monkeypatch, runner_token):

    process = MagicMock()
    monkeypatch.setattr("multiprocessing.Process", process)

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent(show_flow_logs=True)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    process.assert_called_with(
        target=agent.stream_container_logs, kwargs={"container_id": "container_id"}
    )
    assert len(agent.processes) == 1
    assert api.create_container.called
    assert api.start.called


def test_docker_agent_shutdown_terminates_child_processes(monkeypatch, runner_token):
    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock())
    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    proc = MagicMock(is_alive=MagicMock(return_value=True))
    agent = DockerAgent(show_flow_logs=True)
    agent.processes = [proc]
    agent.on_shutdown()

    assert proc.is_alive.called
    assert proc.terminate.called


def test_docker_agent_deploy_flow_no_registry_does_not_pull(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize(),
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


def test_docker_agent_heartbeat_gocase(monkeypatch, runner_token):
    api = MagicMock()
    api.ping.return_value = True
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    agent.heartbeat()
    assert api.ping.call_count == 2


def test_docker_agent_heartbeat_exits_on_failure(monkeypatch, runner_token, caplog):
    api = MagicMock()
    api.ping.return_value = True
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    api.ping.return_value = False
    agent.heartbeat()
    agent.heartbeat()
    agent.heartbeat()
    agent.heartbeat()
    agent.heartbeat()
    with pytest.raises(SystemExit):
        agent.heartbeat()
    assert "Cannot reconnect to Docker daemon. Agent is shutting down." in caplog.text
    assert api.ping.call_count == 7


def test_docker_agent_heartbeat_logs_reconnect(monkeypatch, runner_token, caplog):
    api = MagicMock()
    api.ping.return_value = True
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    api.ping.return_value = False
    agent.heartbeat()
    agent.heartbeat()
    api.ping.return_value = True
    agent.heartbeat()
    assert api.ping.call_count == 4
    assert "Reconnected to Docker daemon" in caplog.text


def test_docker_agent_heartbeat_resets_fail_count(monkeypatch, runner_token, caplog):
    api = MagicMock()
    api.ping.return_value = True
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    api.ping.return_value = False
    agent.heartbeat()
    agent.heartbeat()
    assert agent.failed_connections == 2
    api.ping.return_value = True
    agent.heartbeat()
    assert agent.failed_connections == 0
    assert api.ping.call_count == 4


def test_docker_agent_init_volume_empty_options(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()
    assert agent
    assert agent.named_volumes == []
    assert agent.container_mount_paths == []
    assert agent.host_spec == {}


@pytest.mark.parametrize(
    "path,result",
    [
        ("name", True),
        ("/some/path", False),
        ("./some/path", False),
        ("~/some/path", False),
        ("../some/path", False),
        (" ../some/path", True),  # it is up to the caller to strip the string
        ("\n../some/path", True),  # it is up to the caller to strip the string
    ],
)
def test_docker_agent_is_named_volume_unix(monkeypatch, runner_token, path, result):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )
    monkeypatch.setattr("prefect.agent.docker.agent.platform", "osx")

    agent = DockerAgent()

    assert agent._is_named_volume_unix(path) == result


@pytest.mark.parametrize(
    "path,result",
    [
        ("name", True),
        ("C:\\\\some\\path", False),
        ("c:\\\\some\\path", False),
        ("\\\\some\\path", False),
        ("\\\\\\some\\path", False),
    ],
)
def test_docker_agent_is_named_volume_win32(monkeypatch, runner_token, path, result):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )
    monkeypatch.setattr("prefect.agent.docker.agent.platform", "win32")

    agent = DockerAgent()

    assert agent._is_named_volume_win32(path) == result


@pytest.mark.parametrize(
    "candidate,named_volumes,container_mount_paths,host_spec",
    [
        (
            # handle no volume spec
            [],
            [],
            [],
            {},
        ),
        (
            # no external path given (assume same as host path)
            ["/some/path"],
            [],
            ["/some/path"],
            {"/some/path": {"bind": "/some/path", "mode": "rw",}},
        ),
        (
            # internal & external paths
            ["/some/path:/ctr/path"],
            [],
            ["/ctr/path"],
            {"/some/path": {"bind": "/ctr/path", "mode": "rw",}},
        ),
        (
            # internal & external paths with mode
            ["/some/path:/ctr/path:ro"],
            [],
            ["/ctr/path"],
            {"/some/path": {"bind": "/ctr/path", "mode": "ro",}},
        ),
        (
            # named volume
            ["some-name:/ctr/path"],
            ["some-name"],
            ["/ctr/path"],
            {},
        ),
        (
            # multiple volumes
            [
                "some-name:/ctr/path3",
                "/some/path:/ctr/path1",
                "/another/path:/ctr/path2:ro",
            ],
            ["some-name"],
            ["/ctr/path3", "/ctr/path1", "/ctr/path2"],
            {
                "/another/path": {"bind": "/ctr/path2", "mode": "ro"},
                "/some/path": {"bind": "/ctr/path1", "mode": "rw",},
            },
        ),
    ],
)
def test_docker_agent_parse_volume_spec_unix(
    monkeypatch,
    runner_token,
    candidate,
    named_volumes,
    container_mount_paths,
    host_spec,
):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()

    (
        actual_named_volumes,
        actual_container_mount_paths,
        actual_host_spec,
    ) = agent._parse_volume_spec_unix(candidate)

    assert actual_named_volumes == named_volumes
    assert actual_container_mount_paths == container_mount_paths
    assert actual_host_spec == host_spec


@pytest.mark.parametrize(
    "candidate,named_volumes,container_mount_paths,host_spec",
    [
        (
            # windows host --> linux container
            ["C:\\some\\path"],
            [],
            ["/c/some/path"],
            {"C:\\some\\path": {"bind": "/c/some/path", "mode": "rw",}},
        ),
        (
            # internal & external paths
            ["C:\\some\\path:/ctr/path"],
            [],
            ["/ctr/path"],
            {"C:\\some\\path": {"bind": "/ctr/path", "mode": "rw",}},
        ),
        (
            # internal & external paths with mode
            ["C:\\some\\path:/ctr/path:ro"],
            [],
            ["/ctr/path"],
            {"C:\\some\\path": {"bind": "/ctr/path", "mode": "ro",}},
        ),
        (
            # named volume
            ["some-name:/ctr/path"],
            ["some-name"],
            ["/ctr/path"],
            {},
        ),
        (
            # multiple volumes
            [
                "some-name:/ctr/path3",
                "C:\\some\\path:/ctr/path1",
                "D:\\another\\path:/ctr/path2:ro",
            ],
            ["some-name"],
            ["/ctr/path3", "/ctr/path1", "/ctr/path2"],
            {
                "D:\\another\\path": {"bind": "/ctr/path2", "mode": "ro"},
                "C:\\some\\path": {"bind": "/ctr/path1", "mode": "rw",},
            },
        ),
    ],
)
def test_docker_agent_parse_volume_spec_win(
    monkeypatch,
    runner_token,
    candidate,
    named_volumes,
    container_mount_paths,
    host_spec,
):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()

    (
        actual_named_volumes,
        actual_container_mount_paths,
        actual_host_spec,
    ) = agent._parse_volume_spec_win32(candidate)

    assert actual_named_volumes == named_volumes
    assert actual_container_mount_paths == container_mount_paths
    assert actual_host_spec == host_spec


@pytest.mark.parametrize(
    "candidate,exception_type",
    [
        # named volumes cannot be read only
        ("some-name:/ctr/path:ro", ValueError),
        # dont attempt to parse too many fields
        ("/some/path:/ctr/path:rw:something-else", ValueError),
    ],
)
def test_docker_agent_parse_volume_spec_raises_on_invalid_spec(
    monkeypatch, runner_token, candidate, exception_type,
):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent()

    with pytest.raises(exception_type):
        agent._parse_volume_spec([candidate])


def test_docker_agent_start_max_polls(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.DockerAgent.heartbeat", heartbeat)

    agent = DockerAgent(max_polls=1)
    agent.start()

    assert agent_process.called
    assert heartbeat.called


def test_docker_agent_start_max_polls_count(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.DockerAgent.heartbeat", heartbeat)

    agent = DockerAgent(max_polls=2)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 2
    assert heartbeat.call_count == 2


def test_docker_agent_start_max_polls_zero(monkeypatch, runner_token):
    api = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.DockerAgent.heartbeat", heartbeat)

    agent = DockerAgent(max_polls=0)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 0
    assert heartbeat.call_count == 0


def test_docker_agent_network(monkeypatch, runner_token):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    api.create_networking_config.return_value = {"test-network": "config"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    agent = DockerAgent(network="test-network")
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert agent.network == "test-network"
    args, kwargs = api.create_container.call_args
    assert kwargs["networking_config"] == {"test-network": "config"}


def test_docker_agent_deploy_with_interface_check_linux(
    monkeypatch, runner_token, linux_platform
):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    get_ip = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.get_docker_ip", get_ip)

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize(),
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert get_ip.called


def test_docker_agent_deploy_with_no_interface_check_linux(
    monkeypatch, runner_token, linux_platform
):

    api = MagicMock()
    api.ping.return_value = True
    api.create_container.return_value = {"Id": "container_id"}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=api),
    )

    get_ip = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.get_docker_ip", get_ip)

    agent = DockerAgent(docker_interface=False)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize(),
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert not get_ip.called
