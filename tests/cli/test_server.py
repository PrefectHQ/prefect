import os
from unittest.mock import MagicMock
from typing import List

from click.testing import CliRunner
import pytest
import yaml

import prefect
from prefect.cli.server import server, setup_compose_env, setup_compose_file
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture()
def mock_subprocess(monkeypatch):
    """
    Mock the various ways of creating a subprocess for `prefect server start` tests

    Interrupts the `time.sleep()` call after `docker-compose up` finishes so that the
    tests exit the loop.
    """
    mock = MagicMock()

    monkeypatch.setattr("subprocess.Popen", mock)
    # We will mock `check_call` and `check_output` as well so they don't depend on
    # proper objects being returned from `Popen`
    monkeypatch.setattr("subprocess.check_call", mock)
    monkeypatch.setattr("subprocess.check_output", mock)

    # Mock the sleep to raise an interrupt to prevent it from hanging after `up`
    monkeypatch.setattr("time.sleep", MagicMock(side_effect=KeyboardInterrupt()))

    return mock


def assert_command_not_called(mock: MagicMock, command: List[str]) -> None:
    """
    Assert a mocked `subprocess` was not called with the given command
    """
    for _, args, kwargs in mock.mock_calls:
        if args:
            assert args[0] != command


def get_command_call(mock: MagicMock, command: List[str]):
    """
    Get a mock `call` by command from the a mocked `subprocess` creation
    """
    for _, args, kwargs in mock.mock_calls:
        if args and args[0] == command:
            return args, kwargs

    call_commands = [args[0] for _, args, kwargs in mock.mock_calls if args]
    raise ValueError(f"{command} was not found in {call_commands}")


# Test utilities -----------------------------------------------------------------------


class TestSetupComposeEnv:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("0.10.3", "core-0.10.3"),
            ("0.13.3", "core-0.13.3"),
            ("0.10.3+114.g35bc7ba4", "master"),
            ("0.10.2+999.gr34343.dirty", "master"),
        ],
    )
    def test_server_start_image_versions(
        self, monkeypatch, version, expected, macos_platform
    ):
        monkeypatch.setattr(prefect, "__version__", version)
        assert setup_compose_env()["PREFECT_SERVER_TAG"] == expected

    def test_warns_on_version_conflict(self):
        os.environ["PREFECT_SERVER_TAG"] = "FOO"
        with pytest.warns(
            UserWarning,
            match="The version has been set in the environment .* and the CLI",
        ):
            env = setup_compose_env(version="BAR")

        assert env["PREFECT_SERVER_TAG"] == "BAR"

    def test_warns_on_ui_version_conflict(self):
        os.environ["PREFECT_UI_TAG"] = "FOO"
        with pytest.warns(
            UserWarning,
            match="The UI version has been set in the environment .* and the CLI",
        ):
            env = setup_compose_env(ui_version="BAR")

        assert env["PREFECT_UI_TAG"] == "BAR"

    def test_warns_on_db_command_conflict(self):
        os.environ["PREFECT_SERVER_DB_CMD"] = "FOO"
        with pytest.warns(
            UserWarning,
            match="The database startup command has been set in the environment .* CLI",
        ):
            env = setup_compose_env(no_upgrade=True)

        assert env["PREFECT_SERVER_DB_CMD"] == "echo 'DATABASE MIGRATIONS SKIPPED'"

    def test_allows_db_command_override(self, monkeypatch):
        monkeypatch.setenv("PREFECT_SERVER_DB_CMD", "FOO")
        env = setup_compose_env(no_upgrade=False)
        assert env["PREFECT_SERVER_DB_CMD"] == "FOO"

    def test_fills_env_with_values_from_config_and_args(self, monkeypatch):
        monkeypatch.delenv(
            "PREFECT_SERVER_DB_CMD", raising=False
        )  # Ensure this is not set
        with set_temporary_config(
            {
                "server.database.connection_url": "localhost/foo",
                "server.database.name": "D",
                "server.database.password": "E",
                "server.database.username": "F",
                "server.graphql.path": "/G",
                "server.telemetry.enabled": False,
            }
        ):
            env = setup_compose_env(
                version="A",
                ui_version="B",
                no_upgrade=False,
                postgres_port=1,
                hasura_port=2,
                graphql_port=3,
                ui_port=4,
                server_port=5,
                volume_path="C",
            )

        expected = {
            "APOLLO_HOST_PORT": "5",
            "APOLLO_URL": "http://localhost:4200/graphql",
            "DB_CONNECTION_URL": "postgres/foo",
            "GRAPHQL_HOST_PORT": "3",
            "HASURA_API_URL": "http://hasura:2/v1alpha1/graphql",
            "HASURA_HOST_PORT": "2",
            "HASURA_WS_URL": "ws://hasura:2/v1alpha1/graphql",
            "POSTGRES_DATA_PATH": "C",
            "POSTGRES_DB": "D",
            "POSTGRES_HOST_PORT": "1",
            "POSTGRES_PASSWORD": "E",
            "POSTGRES_USER": "F",
            "PREFECT_API_HEALTH_URL": "http://graphql:3/health",
            "PREFECT_API_URL": f"http://graphql:3/G",
            "PREFECT_CORE_VERSION": prefect.__version__,
            "PREFECT_SERVER_DB_CMD": "prefect-server database upgrade -y",
            "PREFECT_SERVER_TAG": "A",
            "PREFECT_UI_TAG": "B",
            "UI_HOST_PORT": "4",
            "PREFECT_SERVER__TELEMETRY__ENABLED": "false",
        }

        for key, expected_value in expected.items():
            assert env[key] == expected_value

    @pytest.mark.parametrize(
        "external_postgres, postgres_url, expected_postgres_url",
        [
            (True, None, "localhost/foo"),
            (False, "localhost/bar", "localhost/bar"),
            (True, "localhost/bar", "localhost/bar"),
        ],
    )
    def test_setup_env_for_external_postgres(
        self, monkeypatch, external_postgres, postgres_url, expected_postgres_url
    ):
        monkeypatch.delenv(
            "PREFECT_SERVER_DB_CMD", raising=False
        )  # Ensure this is not set
        with set_temporary_config(
            {
                "server.database.connection_url": "localhost/foo",
                "server.graphql.path": "/G",
                "server.telemetry.enabled": False,
            }
        ):
            env = setup_compose_env(
                version="A",
                ui_version="B",
                no_upgrade=False,
                external_postgres=external_postgres,
                postgres_url=postgres_url,
                hasura_port=2,
                graphql_port=3,
                ui_port=4,
                server_port=5,
                volume_path="C",
            )

        expected = {
            "APOLLO_HOST_PORT": "5",
            "APOLLO_URL": "http://localhost:4200/graphql",
            "DB_CONNECTION_URL": expected_postgres_url,
            "GRAPHQL_HOST_PORT": "3",
            "HASURA_API_URL": "http://hasura:2/v1alpha1/graphql",
            "HASURA_HOST_PORT": "2",
            "HASURA_WS_URL": "ws://hasura:2/v1alpha1/graphql",
            "PREFECT_API_HEALTH_URL": "http://graphql:3/health",
            "PREFECT_API_URL": f"http://graphql:3/G",
            "PREFECT_CORE_VERSION": prefect.__version__,
            "PREFECT_SERVER_DB_CMD": "prefect-server database upgrade -y",
            "PREFECT_SERVER_TAG": "A",
            "PREFECT_UI_TAG": "B",
            "UI_HOST_PORT": "4",
            "PREFECT_SERVER__TELEMETRY__ENABLED": "false",
        }

        for key, expected_value in expected.items():
            assert env[key] == expected_value

        # when using external postgres, we should not set these env vars
        not_expected = (
            "POSTGRES_DATA_PATH",
            "POSTGRES_DB",
            "POSTGRES_HOST_PORT",
            "POSTGRES_PASSWORD",
            "POSTGRES_USER",
        )
        assert all([key not in env for key in not_expected])


class TestSetupComposeFile:
    @pytest.mark.parametrize(
        "service", ["postgres", "hasura", "graphql", "ui", "server"]
    )
    def test_disable_port_mapping(self, service, tmpdir):
        compose_file = setup_compose_file(
            **{f"no_{service}_port": True}, temp_dir=str(tmpdir)
        )

        with open(compose_file) as file:
            compose_yml = yaml.safe_load(file)

        default_compose_file = setup_compose_file(temp_dir=str(tmpdir))
        with open(default_compose_file) as file:
            default_compose_yml = yaml.safe_load(file)

        if service == "server":
            service = "apollo"

        # Ensure ports is not set
        assert "ports" not in compose_yml["services"][service]

        # Ensure nothing else has changed
        default_compose_yml["services"][service].pop("ports")
        assert compose_yml == default_compose_yml

    def test_disable_ui_service(self, tmpdir):
        compose_file = setup_compose_file(no_ui=True, temp_dir=str(tmpdir))

        with open(compose_file) as file:
            compose_yml = yaml.safe_load(file)

        default_compose_file = setup_compose_file(temp_dir=str(tmpdir))
        with open(default_compose_file) as file:
            default_compose_yml = yaml.safe_load(file)

        # Ensure ui is not set
        assert "ui" not in compose_yml["services"]

        # Ensure nothing else has changed
        default_compose_yml["services"].pop("ui")
        assert compose_yml == default_compose_yml

    def test_external_postgres(self, tmpdir):
        compose_file = setup_compose_file(external_postgres=True, temp_dir=str(tmpdir))

        with open(compose_file) as file:
            compose_yml = yaml.safe_load(file)

        default_compose_file = setup_compose_file(temp_dir=str(tmpdir))
        with open(default_compose_file) as file:
            default_compose_yml = yaml.safe_load(file)

        # Ensure postgres is not set
        assert "postgres" not in compose_yml["services"]
        # Ensure hasura does not depend on postgres
        assert "postgres" not in compose_yml["services"]["hasura"].get("depends_on", [])

        # Ensure nothing else has changed
        default_compose_yml["services"].pop("postgres")
        default_compose_yml["services"]["hasura"]["depends_on"].remove("postgres")
        assert compose_yml == default_compose_yml

    def test_disable_postgres_volumes(self, tmpdir):
        compose_file = setup_compose_file(use_volume=False, temp_dir=str(tmpdir))

        with open(compose_file) as file:
            compose_yml = yaml.safe_load(file)

        default_compose_file = setup_compose_file(temp_dir=str(tmpdir))
        with open(default_compose_file) as file:
            default_compose_yml = yaml.safe_load(file)

        # Ensure volumes is not set
        assert "volumes" not in compose_yml["services"]["postgres"]

        # Ensure nothing else has changed
        default_compose_yml["services"]["postgres"].pop("volumes")
        assert compose_yml == default_compose_yml


# Test commands ------------------------------------------------------------------------


def test_server_init():
    runner = CliRunner()
    result = runner.invoke(server)
    assert result.exit_code == 0
    assert "Commands for interacting with the Prefect Core server" in result.output


def test_server_help():
    runner = CliRunner()
    result = runner.invoke(server, ["--help"])
    assert result.exit_code == 0
    assert "Commands for interacting with the Prefect Core server" in result.output


class TestPrefectServerStart:
    def test_server_start_setup_and_teardown(self, macos_platform, mock_subprocess):
        # Pull current version information to test default values
        base_version = prefect.__version__.split("+")
        if len(base_version) > 1:
            default_tag = "master"
        else:
            default_tag = f"core-{base_version[0]}"

        expected_env = setup_compose_env(
            version=default_tag,
            ui_version=default_tag,
            ui_port=prefect.config.server.ui.host_port,
            hasura_port=prefect.config.server.hasura.host_port,
            graphql_port=prefect.config.server.graphql.host_port,
            postgres_port=prefect.config.server.database.host_port,
            server_port=prefect.config.server.host_port,
            no_upgrade=False,
            volume_path=prefect.config.server.database.volume_path,
        )

        CliRunner().invoke(server, ["start"])

        pull_args, pull_kwargs = get_command_call(
            mock_subprocess, ["docker-compose", "pull"]
        )
        up_args, up_kwargs = get_command_call(mock_subprocess, ["docker-compose", "up"])
        down_args, down_kwargs = get_command_call(
            mock_subprocess, ["docker-compose", "down"]
        )

        # Ensure that cwd, env were passed and used consistently
        cwd = pull_kwargs.get("cwd")
        env = pull_kwargs.get("env")

        assert env is not None
        assert cwd is not None

        assert up_kwargs.get("cwd") == cwd
        assert up_kwargs.get("env") == env
        assert down_kwargs.get("cwd") == cwd
        assert down_kwargs.get("env") == env

        # Check the environment matches expected defaults
        assert env == expected_env

        # Ensure the docker-compose.yml exists at the tmpdir
        assert os.path.exists(os.path.join(cwd, "docker-compose.yml"))

    def test_server_start_skip_pull(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            ["start", "--skip-pull"],
        )
        assert_command_not_called(mock_subprocess, ["docker-compose", "pull"])
        assert get_command_call(mock_subprocess, ["docker-compose", "up"])

    def test_server_start_no_upgrade(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            ["start", "--no-upgrade"],
        )
        up_args, up_kwargs = get_command_call(mock_subprocess, ["docker-compose", "up"])
        env = up_kwargs.get("env")
        assert env["PREFECT_SERVER_DB_CMD"] == "echo 'DATABASE MIGRATIONS SKIPPED'"

    def test_server_start_port_options(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            [
                "start",
                "--postgres-port",
                "1",
                "--hasura-port",
                "2",
                "--graphql-port",
                "3",
                "--ui-port",
                "4",
                "--server-port",
                "5",
            ],
        )
        up_args, up_kwargs = get_command_call(mock_subprocess, ["docker-compose", "up"])
        env = up_kwargs.get("env")
        assert env["POSTGRES_HOST_PORT"] == "1"
        assert env["HASURA_HOST_PORT"] == "2"
        assert env["GRAPHQL_HOST_PORT"] == "3"
        assert env["UI_HOST_PORT"] == "4"
        assert env["APOLLO_HOST_PORT"] == "5"

    def test_server_start_detach(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            ["start", "--detach"],
        )
        assert get_command_call(mock_subprocess, ["docker-compose", "up", "--detach"])

    def test_server_start_disable_port_mapping(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            [
                "start",
                "--no-postgres-port",
                "--no-hasura-port",
                "--no-graphql-port",
                "--no-ui-port",
                "--no-server-port",
            ],
        )
        up_args, up_kwargs = get_command_call(mock_subprocess, ["docker-compose", "up"])
        tmpdir = up_kwargs["cwd"]

        with open(os.path.join(tmpdir, "docker-compose.yml"), "r") as file:
            compose_yml = yaml.safe_load(file)

        assert "ports" not in compose_yml["services"]["postgres"]
        assert "ports" not in compose_yml["services"]["hasura"]
        assert "ports" not in compose_yml["services"]["graphql"]
        assert "ports" not in compose_yml["services"]["ui"]
        assert "ports" not in compose_yml["services"]["apollo"]
        assert "volumes" not in compose_yml["services"]["postgres"]

    def test_server_start_no_ui_service(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            ["start", "--no-ui"],
        )
        up_args, up_kwargs = get_command_call(mock_subprocess, ["docker-compose", "up"])
        tmpdir = up_kwargs["cwd"]

        with open(os.path.join(tmpdir, "docker-compose.yml"), "r") as file:
            compose_yml = yaml.safe_load(file)

        assert "ui" not in compose_yml["services"]

    def test_server_start_with_volume(self, macos_platform, mock_subprocess):
        CliRunner().invoke(
            server,
            ["start", "--use-volume", "--volume-path", "/foo"],
        )
        up_args, up_kwargs = get_command_call(mock_subprocess, ["docker-compose", "up"])
        tmpdir = up_kwargs["cwd"]

        with open(os.path.join(tmpdir, "docker-compose.yml"), "r") as file:
            compose_yml = yaml.safe_load(file)

        assert "volumes" in compose_yml["services"]["postgres"]
        assert up_kwargs["env"]["POSTGRES_DATA_PATH"] == "/foo"


class TestPrefectServerConfig:
    def test_server_config_setup(self, mock_subprocess):
        # Pull current version information to test default values
        base_version = prefect.__version__.split("+")
        if len(base_version) > 1:
            default_tag = "master"
        else:
            default_tag = f"core-{base_version[0]}"

        expected_env = setup_compose_env(
            version=default_tag,
            ui_version=default_tag,
            ui_port=prefect.config.server.ui.host_port,
            hasura_port=prefect.config.server.hasura.host_port,
            graphql_port=prefect.config.server.graphql.host_port,
            postgres_port=prefect.config.server.database.host_port,
            server_port=prefect.config.server.host_port,
            no_upgrade=False,
            volume_path=prefect.config.server.database.volume_path,
        )

        CliRunner().invoke(server, ["config"])

        config_args, config_kwargs = get_command_call(
            mock_subprocess, ["docker-compose", "config"]
        )

        # Ensure the env is correct
        assert config_kwargs["env"] == expected_env

        # Ensure the docker-compose.yml exists at the tmpdir
        assert os.path.exists(os.path.join(config_kwargs["cwd"], "docker-compose.yml"))

    @pytest.mark.parametrize("with_flags", [True, False])
    def test_server_config_passes_cli_args_to_setup_compose_file(
        self, monkeypatch, mock_subprocess, with_flags
    ):
        mock = MagicMock()
        monkeypatch.setattr("prefect.cli.server.setup_compose_file", mock)

        cmd = ["config"]
        if with_flags:
            cmd += [
                "--external-postgres",
                "--no-postgres-port",
                "--no-hasura-port",
                "--no-graphql-port",
                "--no-ui-port",
                "--no-server-port",
                "--no-ui",
                "--use-volume",
            ]
        CliRunner().invoke(server, cmd)

        mock.assert_called_once_with(
            no_ui=with_flags,
            external_postgres=with_flags,
            no_postgres_port=with_flags,
            no_hasura_port=with_flags,
            no_graphql_port=with_flags,
            no_ui_port=with_flags,
            no_server_port=with_flags,
            use_volume=with_flags,
        )


def test_create_tenant(monkeypatch, cloud_api):
    create_tenant = MagicMock(return_value="my_id")
    monkeypatch.setattr("prefect.client.Client.create_tenant", create_tenant)

    result = CliRunner().invoke(
        server,
        ["create-tenant", "-n", "my-name", "-s", "my-slug"],
    )
    assert result.exit_code == 0
    assert "my_id" in result.output
    assert create_tenant.call_args[1] == {"name": "my-name", "slug": "my-slug"}

    result = CliRunner().invoke(
        server,
        ["create-tenant", "-n", "my-name"],
    )
    assert result.exit_code == 0
    assert "my_id" in result.output
    assert create_tenant.call_args[1] == {"name": "my-name", "slug": None}


def test_stop_server(monkeypatch):
    client = MagicMock()
    client.networks = MagicMock(return_value=["network_id"])
    client.inspect_network = MagicMock(
        return_value={"Containers": {"id": {"test": "val"}}}
    )
    monkeypatch.setattr("docker.APIClient", client)
    result = CliRunner().invoke(server, ["stop"])
    assert result.exit_code == 0
