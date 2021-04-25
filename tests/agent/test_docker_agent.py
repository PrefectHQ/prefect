import pickle
from unittest.mock import MagicMock

import pytest

import prefect
from prefect import context
from prefect.agent.docker.agent import DockerAgent, _stream_container_logs
from prefect.environments import LocalEnvironment
from prefect.storage import Docker, Local
from prefect.run_configs import DockerRun, LocalRun, UniversalRun
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult

docker = pytest.importorskip("docker")


@pytest.fixture(autouse=True)
def mock_cloud_config(cloud_api):
    with set_temporary_config(
        {"cloud.agent.auth_token": "TEST_TOKEN", "logging.log_to_cloud": True}
    ):
        yield


@pytest.fixture
def api(monkeypatch):
    client = MagicMock()
    client.ping.return_value = True
    client.create_container.return_value = {"Id": "container_id"}
    client.create_host_config.return_value = {"AutoRemove": True}
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=client),
    )
    return client


def test_docker_agent_init(api):
    agent = DockerAgent()
    assert agent
    assert agent.agent_config_id is None
    assert agent.labels == []
    assert agent.name == "agent"


@pytest.mark.parametrize(
    "platform, url",
    [
        ("osx", "unix://var/run/docker.sock"),
        ("win32", "npipe:////./pipe/docker_engine"),
    ],
)
def test_docker_agent_config_options(platform, url, monkeypatch):
    api = MagicMock()
    monkeypatch.setattr("docker.APIClient", api)
    monkeypatch.setattr("prefect.agent.docker.agent.platform", platform)

    agent = DockerAgent(name="test")
    assert agent.name == "test"
    assert agent.client.get_auth_token() == "TEST_TOKEN"
    assert agent.logger
    assert not agent.no_pull
    assert api.call_args[1]["base_url"] == url


def test_docker_agent_config_options_populated(monkeypatch):
    api = MagicMock()
    monkeypatch.setattr("docker.APIClient", api)

    agent = DockerAgent(base_url="url", no_pull=True, docker_client_timeout=123)
    assert agent.client.get_auth_token() == "TEST_TOKEN"
    assert agent.logger
    assert agent.no_pull
    assert api.call_args[1]["base_url"] == "url"
    assert api.call_args[1]["timeout"] == 123


def test_docker_agent_no_pull(api):
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


def test_docker_agent_ping(api):
    DockerAgent()
    assert api.ping.called


def test_docker_agent_ping_exception(api):
    api.ping.side_effect = Exception()

    with pytest.raises(Exception):
        DockerAgent()


def test_populate_env_vars_from_agent_config(api):
    agent = DockerAgent(env_vars=dict(AUTH_THING="foo"))

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}), "test-image"
    )

    assert env_vars["AUTH_THING"] == "foo"


def test_populate_env_vars(api, backend):
    agent = DockerAgent()

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}), "test-image"
    )

    if backend == "server":
        cloud_api = "http://host.docker.internal:4200"
    else:
        cloud_api = prefect.config.cloud.api

    expected_vars = {
        "PREFECT__BACKEND": backend,
        "PREFECT__CLOUD__API": cloud_api,
        "PREFECT__CLOUD__AUTH_TOKEN": "TEST_TOKEN",
        "PREFECT__CLOUD__AGENT__LABELS": "[]",
        "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
        "PREFECT__CONTEXT__FLOW_ID": "foo",
        "PREFECT__CONTEXT__IMAGE": "test-image",
        "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
        "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
        "PREFECT__LOGGING__LEVEL": "INFO",
        "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
        "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
    }

    assert env_vars == expected_vars


def test_populate_env_vars_includes_agent_labels(api):
    agent = DockerAgent(labels=["42", "marvin"])

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}), "test-image"
    )
    assert env_vars["PREFECT__CLOUD__AGENT__LABELS"] == "['42', 'marvin']"


@pytest.mark.parametrize("flag", [True, False])
def test_populate_env_vars_sets_log_to_cloud(flag, api):
    agent = DockerAgent(labels=["42", "marvin"], no_cloud_logs=flag)

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}), "test-image"
    )
    assert env_vars["PREFECT__LOGGING__LOG_TO_CLOUD"] == str(not flag).lower()


def test_populate_env_vars_from_run_config(api):
    agent = DockerAgent(env_vars={"KEY1": "VAL1", "KEY2": "VAL2"})

    run = DockerRun(
        env={"KEY2": "OVERRIDE", "PREFECT__LOGGING__LEVEL": "TEST"},
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
        "test-image",
        run_config=run,
    )
    assert env_vars["KEY1"] == "VAL1"
    assert env_vars["KEY2"] == "OVERRIDE"
    assert env_vars["PREFECT__LOGGING__LEVEL"] == "TEST"


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
    config, agent_env_vars, run_config_env_vars, expected_logging_level, api
):
    with set_temporary_config(config):
        agent = DockerAgent(env_vars=agent_env_vars)

        run = DockerRun(env=run_config_env_vars)

        env_vars = agent.populate_env_vars(
            GraphQLResult(
                {
                    "id": "id",
                    "name": "name",
                    "flow": {"id": "foo"},
                    "run_config": run.serialize(),
                }
            ),
            "test-image",
            run_config=run,
        )
        assert env_vars["PREFECT__LOGGING__LEVEL"] == expected_logging_level


@pytest.mark.parametrize(
    "core_version,command",
    [
        ("0.10.0", "prefect execute cloud-flow"),
        ("0.6.0+134", "prefect execute cloud-flow"),
        ("0.13.0", "prefect execute flow-run"),
        ("0.13.1+134", "prefect execute flow-run"),
    ],
)
def test_docker_agent_deploy_flow(core_version, command, api):

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": core_version,
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
    assert api.create_container.call_args[1]["command"] == command
    assert api.create_container.call_args[1]["host_config"]["AutoRemove"] is True
    assert api.create_container.call_args[1]["labels"] == {
        "io.prefect.flow-id": "foo",
        "io.prefect.flow-name": "flow-name",
        "io.prefect.flow-run-id": "id",
    }
    assert api.start.call_args[1]["container"] == "container_id"


def test_docker_agent_deploy_flow_uses_environment_metadata(api):
    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Local().serialize(),
                        "environment": LocalEnvironment(
                            metadata={"image": "repo/name:tag"}
                        ).serialize(),
                        "core_version": "0.13.0",
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
    assert api.create_container.call_args[1]["command"] == "prefect execute flow-run"
    assert api.create_container.call_args[1]["host_config"]["AutoRemove"] is True
    assert api.start.call_args[1]["container"] == "container_id"


@pytest.mark.parametrize("run_kind", ["docker", "missing", "universal"])
@pytest.mark.parametrize("has_docker_storage", [True, False])
def test_docker_agent_deploy_flow_run_config(api, run_kind, has_docker_storage):
    if has_docker_storage:
        storage = Docker(
            registry_url="testing", image_name="on-storage", image_tag="tag"
        )
        image = "testing/on-storage:tag"
    else:
        storage = Local()
        image = "on-run-config" if run_kind == "docker" else "prefecthq/prefect:0.13.11"

    if run_kind == "docker":
        env = {"TESTING": "VALUE"}
        run = DockerRun(image=image, env=env)
    else:
        env = {}
        run = None if run_kind == "missing" else UniversalRun()

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": storage.serialize(),
                        "core_version": "0.13.11",
                    }
                ),
                "run_config": run.serialize() if run else None,
                "id": "id",
                "name": "name",
            }
        )
    )

    assert api.create_container.called
    assert api.create_container.call_args[0][0] == image
    res_env = api.create_container.call_args[1]["environment"]
    for k, v in env.items():
        assert res_env[k] == v


def test_docker_agent_deploy_flow_unsupported_run_config(api):
    agent = DockerAgent()

    with pytest.raises(
        TypeError,
        match="`run_config` of type `LocalRun`, only `DockerRun` is supported",
    ):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Local().serialize(),
                            "id": "foo",
                            "name": "flow-name",
                            "core_version": "0.13.0",
                        }
                    ),
                    "run_config": LocalRun().serialize(),
                    "id": "id",
                    "name": "name",
                    "version": "version",
                }
            )
        )

    assert not api.pull.called


def test_docker_agent_deploy_flow_storage_raises(monkeypatch, api):
    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock())

    agent = DockerAgent()

    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Local().serialize(),
                            "id": "foo",
                            "name": "flow-name",
                            "environment": LocalEnvironment().serialize(),
                            "core_version": "0.13.0",
                        }
                    ),
                    "id": "id",
                    "name": "name",
                    "version": "version",
                }
            )
        )

    assert not api.pull.called


def test_docker_agent_deploy_flow_no_pull(api):
    agent = DockerAgent(no_pull=True)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
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


def test_docker_agent_deploy_flow_no_pull_using_environment_metadata(api):
    agent = DockerAgent(no_pull=True)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Local().serialize(),
                        "environment": LocalEnvironment(
                            metadata={"image": "name:tag"}
                        ).serialize(),
                        "core_version": "0.13.0",
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


def test_docker_agent_deploy_flow_reg_allow_list_allowed(api):
    agent = DockerAgent(reg_allow_list=["test1"])

    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="test1", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
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


def test_docker_agent_deploy_flow_reg_allow_list_not_allowed(api):
    agent = DockerAgent(reg_allow_list=["test1"])

    with pytest.raises(ValueError) as error:
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "id": "foo",
                            "name": "flow-name",
                            "storage": Docker(
                                registry_url="test2", image_name="name", image_tag="tag"
                            ).serialize(),
                            "environment": LocalEnvironment().serialize(),
                            "core_version": "0.13.0",
                        }
                    ),
                    "id": "id",
                    "name": "name",
                }
            )
        )

    expected_error = (
        "Trying to pull image from a Docker registry 'test2'"
        " which is not in the reg_allow_list"
    )

    assert not api.pull.called
    assert not api.create_container.called
    assert not api.start.called
    assert str(error.value) == expected_error


def test_docker_agent_deploy_flow_show_flow_logs(api, monkeypatch):
    process = MagicMock()
    monkeypatch.setattr("multiprocessing.Process", process)

    agent = DockerAgent(show_flow_logs=True)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    process_kwargs = dict(
        target=_stream_container_logs,
        kwargs={
            "base_url": agent.base_url,
            "container_id": "container_id",
            "timeout": 60,
        },
    )
    process.assert_called_with(**process_kwargs)
    # Check all arguments to `multiprocessing.Process` are pickleable
    assert pickle.loads(pickle.dumps(process_kwargs)) == process_kwargs

    assert len(agent.processes) == 1
    assert api.create_container.called
    assert api.start.called


def test_docker_agent_shutdown_terminates_child_processes(monkeypatch, api):
    monkeypatch.setattr("prefect.agent.agent.Client", MagicMock())

    proc = MagicMock(is_alive=MagicMock(return_value=True))
    agent = DockerAgent(show_flow_logs=True)
    agent.processes = [proc]
    agent.on_shutdown()

    assert proc.is_alive.called
    assert proc.terminate.called


def test_docker_agent_deploy_flow_no_registry_does_not_pull(api):
    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
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


def test_docker_agent_heartbeat_gocase(api):
    agent = DockerAgent()
    agent.heartbeat()
    assert api.ping.call_count == 2


def test_docker_agent_heartbeat_exits_on_failure(api, caplog):
    agent = DockerAgent()
    api.ping.return_value = False
    for _ in range(5):
        agent.heartbeat()
    with pytest.raises(SystemExit):
        agent.heartbeat()
    assert "Cannot reconnect to Docker daemon. Agent is shutting down." in caplog.text
    assert api.ping.call_count == 7


def test_docker_agent_heartbeat_logs_reconnect(api, caplog):
    agent = DockerAgent()
    api.ping.return_value = False
    agent.heartbeat()
    agent.heartbeat()
    api.ping.return_value = True
    agent.heartbeat()
    assert api.ping.call_count == 4
    assert "Reconnected to Docker daemon" in caplog.text


def test_docker_agent_heartbeat_resets_fail_count(api, caplog):
    agent = DockerAgent()
    api.ping.return_value = False
    agent.heartbeat()
    agent.heartbeat()
    assert agent.failed_connections == 2
    api.ping.return_value = True
    agent.heartbeat()
    assert agent.failed_connections == 0
    assert api.ping.call_count == 4


def test_docker_agent_init_volume_empty_options(api):
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
def test_docker_agent_is_named_volume_unix(monkeypatch, api, path, result):
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
def test_docker_agent_is_named_volume_win32(monkeypatch, api, path, result):
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
            {"/some/path": {"bind": "/some/path", "mode": "rw"}},
        ),
        (
            # internal & external paths
            ["/some/path:/ctr/path"],
            [],
            ["/ctr/path"],
            {"/some/path": {"bind": "/ctr/path", "mode": "rw"}},
        ),
        (
            # internal & external paths with mode
            ["/some/path:/ctr/path:ro"],
            [],
            ["/ctr/path"],
            {"/some/path": {"bind": "/ctr/path", "mode": "ro"}},
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
                "/some/path": {"bind": "/ctr/path1", "mode": "rw"},
            },
        ),
    ],
)
def test_docker_agent_parse_volume_spec_unix(
    api, candidate, named_volumes, container_mount_paths, host_spec
):
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
            {"C:\\some\\path": {"bind": "/c/some/path", "mode": "rw"}},
        ),
        (
            # internal & external paths
            ["C:\\some\\path:/ctr/path"],
            [],
            ["/ctr/path"],
            {"C:\\some\\path": {"bind": "/ctr/path", "mode": "rw"}},
        ),
        (
            # internal & external paths with mode
            ["C:\\some\\path:/ctr/path:ro"],
            [],
            ["/ctr/path"],
            {"C:\\some\\path": {"bind": "/ctr/path", "mode": "ro"}},
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
                "C:\\some\\path": {"bind": "/ctr/path1", "mode": "rw"},
            },
        ),
    ],
)
def test_docker_agent_parse_volume_spec_win(
    api, candidate, named_volumes, container_mount_paths, host_spec
):
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
    api, candidate, exception_type
):
    agent = DockerAgent()

    with pytest.raises(exception_type):
        agent._parse_volume_spec([candidate])


@pytest.mark.parametrize("max_polls", [0, 1, 2])
def test_docker_agent_start_max_polls(max_polls, api, monkeypatch, runner_token):
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

    agent = DockerAgent(max_polls=max_polls)
    agent.start()

    assert agent_connect.call_count == 1
    assert agent_process.call_count == max_polls
    assert heartbeat.call_count == 1
    assert on_shutdown.call_count == 1


def test_docker_agent_network(api):
    api.create_networking_config.return_value = {"test-network": "config"}

    with pytest.warns(UserWarning):
        agent = DockerAgent(network="test-network")
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert agent.network == "test-network"
    assert agent.networks is None
    args, kwargs = api.create_container.call_args
    assert kwargs["networking_config"] == {"test-network": "config"}


def test_docker_agent_network_network_and_networks(api):
    with pytest.raises(ValueError):
        DockerAgent(
            network="test-network", networks=["test-network-1", "test-network-2"]
        )


def test_docker_agent_networks(api):
    api.create_networking_config.return_value = {
        "test-network-1": "config1",
        "test-network-2": "config2",
    }

    agent = DockerAgent(networks=["test-network-1", "test-network-2"])
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert "test-network-1" in agent.networks
    assert "test-network-2" in agent.networks
    assert agent.network is None
    args, kwargs = api.create_container.call_args
    assert kwargs["networking_config"] == {
        "test-network-1": "config1",
        "test-network-2": "config2",
    }


def test_docker_agent_deploy_with_interface_check_linux(
    api, monkeypatch, linux_platform
):
    get_ip = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.get_docker_ip", get_ip)

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert get_ip.called


def test_docker_agent_deploy_with_no_interface_check_linux(
    api, monkeypatch, linux_platform
):
    get_ip = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.get_docker_ip", get_ip)

    agent = DockerAgent(docker_interface=False)
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Docker(
                            registry_url="", image_name="name", image_tag="tag"
                        ).serialize(),
                        "environment": LocalEnvironment().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )

    assert not get_ip.called
