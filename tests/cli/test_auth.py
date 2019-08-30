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

    with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"])
        assert result.exit_code == 0


def test_auth_login_client_error(patch_post):
    patch_post(dict(errors=dict(error="bad")))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"])
        assert result.exit_code == 0
        assert "Error attempting to communicate with Prefect Cloud" in result.output


def test_auth_login_confirm(patch_post):
    patch_post(dict(data=dict(hello="hi")))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"], input="Y")
        assert result.exit_code == 0


def test_auth_login_not_confirm(patch_post):
    patch_post(dict(data=dict(hello="hi")))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["login", "--token", "test"], input="N")
        assert result.exit_code == 1


def test_auth_logout_after_login(patch_post):
    patch_post(dict(data=dict(tenant="id")))

    with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
        runner = CliRunner()

        result = runner.invoke(auth, ["login", "--token", "test"])
        assert result.exit_code == 0

        c = prefect.Client()
        assert c._api_token == "test"

        result = runner.invoke(auth, ["logout"], input="Y")
        assert result.exit_code == 0

        c = prefect.Client()
        assert not c._active_tenant_id


def test_auth_logout_not_confirm(patch_post):
    patch_post(dict(data=dict(tenant="id")))

    with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
        runner = CliRunner()
        result = runner.invoke(auth, ["logout"], input="N")
        assert result.exit_code == 1


def test_auth_logout_no_active_tenant(patch_post):
    patch_post(dict(data=dict(tenant="id")))

    with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
        runner = CliRunner()
        result = runner.invoke(auth, ["logout"], input="Y")
        assert result.exit_code == 0
        assert "No tenant currently active" in result.output


def test_list_tenants(patch_post):
    patch_post(
        dict(
            data=dict(
                tenant=[{"id": "id", "slug": "slug", "name": "name"}],
                switchTenant={
                    "accessToken": "accessToken",
                    "expiresIn": "expiresIn",
                    "refreshToken": "refreshToken",
                },
            )
        )
    )

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["list-tenants"])
        assert result.exit_code == 0
        assert "id" in result.output
        assert "slug" in result.output
        assert "name" in result.output


def test_switch_tenants(monkeypatch):
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        monkeypatch.setattr("prefect.cli.auth.Client", MagicMock())

        runner = CliRunner()
        result = runner.invoke(auth, ["switch-tenants", "--slug", "slug"])
        assert result.exit_code == 0
        assert "Tenant switched" in result.output


def test_switch_tenants(monkeypatch):
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = MagicMock()
        client.return_value.login_to_tenant = MagicMock(return_value=False)
        monkeypatch.setattr("prefect.cli.auth.Client", client)

        runner = CliRunner()
        result = runner.invoke(auth, ["switch-tenants", "--slug", "slug"])
        assert result.exit_code == 0
        assert "Unable to switch tenant" in result.output


def test_create_token(patch_post):
    patch_post(dict(data=dict(createAPIToken={"token": "token"})))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["create-token", "-n", "name", "-r", "role"])
        assert result.exit_code == 0
        assert "token" in result.output


def test_create_token_fails(patch_post):
    patch_post(dict())

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(auth, ["create-token", "-n", "name", "-r", "role"])
        assert result.exit_code == 0
        assert "Issue creating API token" in result.output
