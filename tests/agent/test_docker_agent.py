import pickle
from unittest.mock import MagicMock

import pytest
import uuid

import prefect
from prefect import context
from prefect.agent.docker.agent import DockerAgent, _stream_container_logs
from prefect.storage import Docker, Local
from prefect.run_configs import DockerRun, LocalRun, UniversalRun
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult

docker = pytest.importorskip("docker")


@pytest.fixture
def api(monkeypatch):
    client = MagicMock()
    client.ping.return_value = True
    client.create_container.return_value = {"Id": "container_id"}
    client.create_host_config.return_value = {"AutoRemove": True}
    client.version.return_value = {"Version": "20.10.0"}  # Our recommend min version
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
def test_docker_agent_config_options(platform, url, monkeypatch, config_with_api_key):
    api = MagicMock()
    monkeypatch.setattr("docker.APIClient", api)
    monkeypatch.setattr("prefect.agent.docker.agent.platform", platform)

    agent = DockerAgent(name="test")
    assert agent.name == "test"
    assert agent.client.api_key == config_with_api_key.cloud.api_key
    assert agent.logger
    assert not agent.no_pull
    assert api.call_args[1]["base_url"] == url


def test_docker_agent_config_options_populated(monkeypatch, config_with_api_key):
    api = MagicMock()
    monkeypatch.setattr("docker.APIClient", api)

    agent = DockerAgent(base_url="url", no_pull=True, docker_client_timeout=123)
    assert agent.client.api_key == config_with_api_key.cloud.api_key
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
        "PREFECT__CLOUD__AUTH_TOKEN": "",
        "PREFECT__CLOUD__API_KEY": "",
        "PREFECT__CLOUD__TENANT_ID": "",
        "PREFECT__CLOUD__AGENT__LABELS": "[]",
        "PREFECT__CONTEXT__FLOW_RUN_ID": "id",
        "PREFECT__CONTEXT__FLOW_ID": "foo",
        "PREFECT__CONTEXT__IMAGE": "test-image",
        "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
        "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": "true",
        "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
        "PREFECT__LOGGING__LEVEL": "INFO",
        "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
        "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
    }

    assert env_vars == expected_vars


def test_environment_has_api_key_from_config(api, config_with_api_key):
    agent = DockerAgent()

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}),
        "test-image",
    )

    assert env_vars["PREFECT__CLOUD__API_KEY"] == config_with_api_key.cloud.api_key
    assert env_vars["PREFECT__CLOUD__AUTH_TOKEN"] == config_with_api_key.cloud.api_key
    assert env_vars["PREFECT__CLOUD__TENANT_ID"] == config_with_api_key.cloud.tenant_id


def test_environment_has_tenant_id_from_server(api, config_with_api_key):
    tenant_id = uuid.uuid4()

    with set_temporary_config({"cloud.tenant_id": None}):
        agent = DockerAgent()
        agent.client._get_auth_tenant = MagicMock(return_value=tenant_id)

        env = agent.populate_env_vars(
            GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}),
            "test-image",
        )

    assert env["PREFECT__CLOUD__API_KEY"] == config_with_api_key.cloud.api_key
    assert env["PREFECT__CLOUD__AUTH_TOKEN"] == config_with_api_key.cloud.api_key
    assert env["PREFECT__CLOUD__TENANT_ID"] == tenant_id


def test_environment_has_api_key_from_disk(api, monkeypatch):
    """Check that the API key is passed through from the on disk cache"""

    tenant_id = str(uuid.uuid4())

    monkeypatch.setattr(
        "prefect.Client.load_auth_from_disk",
        MagicMock(
            return_value={
                "api_key": "TEST_KEY",
                "tenant_id": tenant_id,
            }
        ),
    )

    agent = DockerAgent()

    env = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}),
        "test-image",
    )

    assert env["PREFECT__CLOUD__API_KEY"] == "TEST_KEY"
    assert env["PREFECT__CLOUD__AUTH_TOKEN"] == "TEST_KEY"
    assert env["PREFECT__CLOUD__TENANT_ID"] == tenant_id


def test_populate_env_vars_includes_agent_labels(api):
    agent = DockerAgent(labels=["42", "marvin"])

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}), "test-image"
    )
    assert env_vars["PREFECT__CLOUD__AGENT__LABELS"] == "['42', 'marvin']"


@pytest.mark.parametrize("flag", [True, False])
def test_populate_env_vars_sets_log_to_cloud(flag, api, config_with_api_key):
    agent = DockerAgent(labels=["42", "marvin"], no_cloud_logs=flag)

    env_vars = agent.populate_env_vars(
        GraphQLResult({"id": "id", "name": "name", "flow": {"id": "foo"}}), "test-image"
    )
    assert env_vars["PREFECT__CLOUD__SEND_FLOW_RUN_LOGS"] == str(not flag).lower()

    # Backwards compatibility variable for containers on Prefect <0.15.0
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


def test_api_url_can_be_overridden_at_agent_level(api):
    agent = DockerAgent(env_vars={"PREFECT__CLOUD__API": "FOO"})

    env_vars = agent.populate_env_vars(
        GraphQLResult(
            {
                "id": "id",
                "name": "name",
                "flow": {"id": "foo"},
            }
        ),
        "test-image",
    )
    assert env_vars["PREFECT__CLOUD__API"] == "FOO"


def test_api_url_can_be_overridden_with_run_config(api):
    agent = DockerAgent(env_vars={"PREFECT__CLOUD__API": "FOO"})

    run = DockerRun(
        env={"PREFECT__CLOUD__API": "BAR"},
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
    assert env_vars["PREFECT__CLOUD__API"] == "BAR"


def test_api_url_uses_server_network(api, backend):
    """
    If the `prefect-server` network is provided and the backend is 'server' then we
    will replace the API url with 'apollo' instead of 'host.docker.internal' to make
    use of the network for connections to the API
    """
    agent = DockerAgent(networks=["prefect-server"])

    env_vars = agent.populate_env_vars(
        GraphQLResult(
            {
                "id": "id",
                "name": "name",
                "flow": {"id": "foo"},
                "run_config": {},
            }
        ),
        "test-image",
    )

    if backend == "server":
        assert env_vars["PREFECT__CLOUD__API"] == "http://apollo:4200"
    else:
        assert env_vars["PREFECT__CLOUD__API"] == "https://api.prefect.io"


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


@pytest.mark.parametrize("collision_count", (0, 1, 5))
def test_docker_agent_deploy_flow_sets_container_name_with_index(api, collision_count):
    """
    Asserts that the container name is set to the flow run name and that collisions with
    existing containers with the same name is handled by adding an index
    """

    if collision_count:
        # Add the basic name first
        existing_names = ["flow-run-name"]
        for i in range(1, collision_count):
            existing_names.append(f"flow-run-name-{i}")
    else:
        existing_names = []

    def fail_if_name_exists(*args, **kwargs):
        if kwargs.get("name") in existing_names:
            raise docker.errors.APIError(
                "Conflict. The container name 'foobar' is already in use"
            )
        return {}

    api.create_container = MagicMock(side_effect=fail_if_name_exists)

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Local().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": "flow-run-name",
            }
        )
    )

    expected_name = (
        "flow-run-name" if not collision_count else f"flow-run-name-{collision_count}"
    )
    assert api.create_container.call_args[1]["name"] == expected_name


@pytest.mark.parametrize(
    "run_name,container_name",
    [
        ("_flow_run", "flow_run"),
        ("...flow_run", "flow_run"),
        ("._-flow_run", "flow_run"),
        ("9flow-run", "9flow-run"),
        ("-flow.run", "flow.run"),
        ("flow*run", "flow-run"),
        ("flow9.-foo_bar^x", "flow9.-foo_bar-x"),
        ("", "id"),  # Falls back to ID on empty name
        ("_._-_", "id"),  # Falls back to ID on empty name after trim
    ],
)
def test_docker_agent_deploy_flow_sets_container_name_with_slugify(
    api, run_name, container_name
):
    """
    Asserts that the container name is set to the flow run name and that collisions with
    existing containers with the same name is handled by adding an index
    """

    agent = DockerAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "id": "foo",
                        "name": "flow-name",
                        "storage": Local().serialize(),
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
                "name": run_name,
            }
        )
    )

    assert api.create_container.call_args[1]["name"] == container_name


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
        ports = [12001]
        host_config = {"auto_remove": False, "shm_size": "128m"}
        exp_host_config = {
            "auto_remove": False,
            "shm_size": "128m",
        }
        run = DockerRun(image=image, env=env, ports=ports, host_config=host_config)
    else:
        env = {}
        ports = []
        host_config = {}
        exp_host_config = {
            "auto_remove": True,
        }
        run = None if run_kind == "missing" else UniversalRun()

    exp_host_config["extra_hosts"] = {"host.docker.internal": "host-gateway"}

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
    res_ports = api.create_container.call_args[1]["ports"]
    for i, v in enumerate(ports):
        assert res_ports[i] == v
    res_host_config = api.create_host_config.call_args[1]
    for k, v in exp_host_config.items():
        assert res_host_config[k] == v


@pytest.mark.parametrize("docker_engine_version", ["0.25.10", "19.1.1"])
def test_docker_agent_deploy_flow_does_not_include_host_gateway_for_old_engine_versions(
    api, docker_engine_version
):
    api.version.return_value = {"Version": docker_engine_version}

    run = UniversalRun()
    storage = Local()

    agent = DockerAgent()
    with pytest.warns(
        UserWarning,
        match=(
            "`host.docker.internal` could not be automatically resolved.*"
            f"feature is not supported on Docker Engine v{docker_engine_version}"
        ),
    ):
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

    assert "extra_hosts" not in api.create_host_config.call_args[1]


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
            {"some-name": {"bind": "/ctr/path", "mode": "rw"}},
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
                "some-name": {"bind": "/ctr/path3", "mode": "rw"},
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
            # windows docker socket
            ["//var/run/docker.sock"],
            [],
            ["/var/run/docker.sock"],
            {"//var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
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
            {"some-name": {"bind": "/ctr/path", "mode": "rw"}},
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
                "some-name": {"bind": "/ctr/path3", "mode": "rw"},
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
    args, kwargs = api.create_container.call_args
    assert kwargs["networking_config"] == {
        "test-network-1": "config1",
        "test-network-2": "config2",
    }
