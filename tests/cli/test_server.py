from unittest.mock import MagicMock

from click.testing import CliRunner
import pytest

import prefect
from prefect.cli.server import server, make_env
from prefect.utilities.configuration import set_temporary_config


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


def test_make_env():
    env = make_env()
    assert env


def test_make_env_config_vars():
    with set_temporary_config(
        {
            "server.database.connection_url": "localhost",
            "server.graphql.host_port": "1",
            "server.ui.host_port": "2",
            "server.hasura.port": "3",
            "server.graphql.port": "4",
            "server.graphql.path": "/path",
            "server.host_port": "5",
            "server.database.host_port": "6",
            "server.database.username": "username",
            "server.database.password": "password",
            "server.database.name": "db",
            "server.hasura.host_port": "7",
        }
    ):
        env = make_env()

        assert env["DB_CONNECTION_URL"] == "postgres"
        assert env["GRAPHQL_HOST_PORT"] == "1"
        assert env["UI_HOST_PORT"] == "2"
        assert env["HASURA_API_URL"] == "http://hasura:3/v1alpha1/graphql"
        assert env["HASURA_WS_URL"] == "ws://hasura:3/v1alpha1/graphql"
        assert env["PREFECT_API_URL"] == "http://graphql:4/path"
        assert env["PREFECT_API_HEALTH_URL"] == "http://graphql:4/health"
        assert env["APOLLO_HOST_PORT"] == "5"
        assert env["POSTGRES_HOST_PORT"] == "6"
        assert env["POSTGRES_USER"] == "username"
        assert env["POSTGRES_PASSWORD"] == "password"
        assert env["POSTGRES_DB"] == "db"
        assert env["HASURA_HOST_PORT"] == "7"


def test_server_start(monkeypatch, macos_platform):
    check_call = MagicMock()
    popen = MagicMock(side_effect=KeyboardInterrupt())
    check_output = MagicMock()
    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.setattr("subprocess.check_call", check_call)
    monkeypatch.setattr("subprocess.check_output", check_output)

    runner = CliRunner()
    result = runner.invoke(server, ["start"])
    assert result.exit_code == 1

    assert check_call.called
    assert popen.called
    assert check_output.called

    assert check_call.call_args[0][0] == ["docker-compose", "pull"]
    assert check_call.call_args[1].get("cwd")
    assert check_call.call_args[1].get("env")

    assert popen.call_args[0][0] == ["docker-compose", "up"]
    assert popen.call_args[1].get("cwd")
    assert popen.call_args[1].get("env")

    assert check_output.call_args[0][0] == ["docker-compose", "down"]
    assert check_output.call_args[1].get("cwd")
    assert check_output.call_args[1].get("env")


@pytest.mark.parametrize(
    "version",
    [
        ("0.10.3", "0.10.3"),
        ("0.10.3+114.g35bc7ba4", "master"),
        ("0.10.2+999.gr34343.dirty", "master"),
    ],
)
def test_server_start_image_versions(monkeypatch, version, macos_platform):
    check_call = MagicMock()
    popen = MagicMock(side_effect=KeyboardInterrupt())
    check_output = MagicMock()
    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.setattr("subprocess.check_call", check_call)
    monkeypatch.setattr("subprocess.check_output", check_output)
    monkeypatch.setattr(prefect, "__version__", version[0])

    runner = CliRunner()
    result = runner.invoke(server, ["start"])
    assert result.exit_code == 1

    assert check_call.called
    assert popen.called
    assert check_output.called

    assert popen.call_args[0][0] == ["docker-compose", "up"]
    assert popen.call_args[1].get("cwd")
    assert popen.call_args[1].get("env")
    assert popen.call_args[1]["env"].get("PREFECT_SERVER_TAG") == version[1]


def test_server_start_options_and_flags(monkeypatch, macos_platform):
    check_call = MagicMock()
    popen = MagicMock(side_effect=KeyboardInterrupt())
    check_output = MagicMock()
    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.setattr("subprocess.check_call", check_call)
    monkeypatch.setattr("subprocess.check_output", check_output)

    runner = CliRunner()
    result = runner.invoke(
        server,
        ["start", "--version", "version", "--skip-pull", "--no-upgrade", "--no-ui"],
    )
    assert result.exit_code == 1

    assert not check_call.called
    assert popen.called
    assert check_output.called

    assert popen.call_args[0][0] == ["docker-compose", "up", "--scale", "ui=0"]
    assert popen.call_args[1].get("cwd")
    assert popen.call_args[1].get("env")
    assert popen.call_args[1]["env"].get("PREFECT_SERVER_TAG") == "version"
    assert (
        popen.call_args[1]["env"].get("PREFECT_SERVER_DB_CMD")
        == "echo 'DATABASE MIGRATIONS SKIPPED'"
    )

    assert check_output.call_args[0][0] == ["docker-compose", "down"]
    assert check_output.call_args[1].get("cwd")
    assert check_output.call_args[1].get("env")


def test_server_start_port_options(monkeypatch, macos_platform):
    check_call = MagicMock()
    popen = MagicMock(side_effect=KeyboardInterrupt())
    check_output = MagicMock()
    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.setattr("subprocess.check_call", check_call)
    monkeypatch.setattr("subprocess.check_output", check_output)

    runner = CliRunner()
    result = runner.invoke(
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
    assert result.exit_code == 1

    assert check_call.called
    assert popen.called
    assert check_output.called

    assert popen.call_args[0][0] == ["docker-compose", "up"]
    assert popen.call_args[1].get("cwd")
    assert popen.call_args[1].get("env")
    assert popen.call_args[1]["env"].get("POSTGRES_HOST_PORT") == "1"
    assert popen.call_args[1]["env"].get("HASURA_HOST_PORT") == "2"
    assert popen.call_args[1]["env"].get("GRAPHQL_HOST_PORT") == "3"
    assert popen.call_args[1]["env"].get("UI_HOST_PORT") == "4"
    assert popen.call_args[1]["env"].get("APOLLO_HOST_PORT") == "5"


def test_server_start_disable_port_mapping(monkeypatch, macos_platform):
    check_call = MagicMock()
    popen = MagicMock(side_effect=KeyboardInterrupt())
    check_output = MagicMock()
    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.setattr("subprocess.check_call", check_call)
    monkeypatch.setattr("subprocess.check_output", check_output)

    runner = CliRunner()
    result = runner.invoke(
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
    assert result.exit_code == 1

    assert check_call.called
    assert popen.called
    assert check_output.called

    assert check_call.call_args[0][0] == ["docker-compose", "pull"]
    assert check_call.call_args[1].get("cwd")
    assert check_call.call_args[1].get("env")

    assert popen.call_args[0][0] == ["docker-compose", "up"]
    assert popen.call_args[1].get("cwd")
    assert popen.call_args[1].get("env")

    assert check_output.call_args[0][0] == ["docker-compose", "down"]
    assert check_output.call_args[1].get("cwd")
    assert check_output.call_args[1].get("env")


def test_server_start_linux_host(monkeypatch, linux_platform):
    popen = MagicMock(side_effect=KeyboardInterrupt())
    check_output = MagicMock()
    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.setattr("subprocess.check_output", check_output)

    sys_platform = MagicMock()
    sys_platform.return_value = "linux"
    monkeypatch.setattr("sys.platform", sys_platform)

    get_docker_ip = MagicMock()
    get_docker_ip.return_value = "172.17.0.1"
    monkeypatch.setattr("prefect.cli.server.get_docker_ip", get_docker_ip)

    yaml_dump = MagicMock()
    monkeypatch.setattr("yaml.safe_dump", yaml_dump)

    runner = CliRunner()
    result = runner.invoke(server, ["start", "--skip-pull",],)
    assert result.exit_code == 1

    assert popen.called
    assert check_output.called

    call_arg = yaml_dump.call_args[0][0]
    for svc in ("postgres", "hasura", "graphql", "apollo", "scheduler", "ui"):
        assert call_arg["services"][svc]["extra_hosts"] == [
            "host.docker.internal:172.17.0.1"
        ]
