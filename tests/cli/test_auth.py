import tempfile
from unittest.mock import MagicMock

import click
from click.testing import CliRunner
import requests
import toml

import prefect
from prefect.cli.auth import auth
from prefect.utilities.configuration import set_temporary_config


def test_auth_init():
    runner = CliRunner()
    result = runner.invoke(auth)
    assert result.exit_code == 0
    assert "Handle Prefect Cloud authorization." in result.output


def test_auth_help():
    runner = CliRunner()
    result = runner.invoke(auth, ["--help"])
    assert result.exit_code == 0
    assert "Handle Prefect Cloud authorization." in result.output


def test_auth_add_not_exist():
    runner = CliRunner()
    result = runner.invoke(
        auth, ["add", "--token", "test", "--config-path", "not_exist"]
    )
    assert result.exit_code == 0
    assert "not_exist does not exist" in result.output


def test_auth_add(monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:

        file = "{}/temp_config.toml".format(temp_dir)

        # Create file
        open(file, "w+")

        post = MagicMock(
            return_value=MagicMock(
                json=MagicMock(return_value=dict(data=dict(hello="hi")))
            )
        )
        monkeypatch.setattr("requests.post", post)

        with set_temporary_config(
            {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
        ):
            runner = CliRunner()
            result = runner.invoke(
                auth, ["add", "--token", "test", "--config-path", file]
            )
            assert result.exit_code == 0
            assert "Auth token added to Prefect config" in result.output


def test_auth_add_failes_query(monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:

        file = "{}/temp_config.toml".format(temp_dir)

        # Create file
        open(file, "w+")

        post = MagicMock(
            return_value=MagicMock(
                json=MagicMock(return_value=dict(data=dict(hello=None)))
            )
        )
        monkeypatch.setattr("requests.post", post)

        with set_temporary_config(
            {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
        ):
            runner = CliRunner()
            result = runner.invoke(
                auth, ["add", "--token", "test", "--config-path", file]
            )
            assert result.exit_code == 0
            assert "Error attempting to use Prefect auth token" in result.output
