from unittest.mock import MagicMock

from click.testing import CliRunner

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
            "config.server.database.connection_url": "connect",
            "config.server.graphql.host_port": "1",
            "config.server.ui.host_port": "2",
            "config.server.hasura.port": "3",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
            "config.server.graphql.host_port": "1",
        }
    ):
        pass
