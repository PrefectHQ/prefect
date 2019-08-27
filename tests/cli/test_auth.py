import tempfile
from unittest.mock import MagicMock

import click
import requests
import toml
from click.testing import CliRunner

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


def test_auth_login(patch_post):
    patch_post(dict(data=dict(tenant="id")))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.api_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"])
        assert result.exit_code == 0
        assert "Login successful" in result.output


def test_auth_login_client_error(patch_post):
    patch_post(dict(errors=dict(error="bad")))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.api_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"])
        assert result.exit_code == 0
        assert "Error attempting to communicate with Prefect Cloud" in result.output


def test_auth_login_confirm(patch_post):
    patch_post(dict(data=dict(hello="hi")))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.api_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"], input="Y")
        assert result.exit_code == 0
        assert "Login successful" in result.output


def test_auth_login_not_confirm(patch_post):
    patch_post(dict(data=dict(hello="hi")))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.api_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"], input="N")
        assert result.exit_code == 1
