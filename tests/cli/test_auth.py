import uuid
from unittest.mock import MagicMock

import click
import pytest
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


def test_auth_login(patch_post, monkeypatch, cloud_api):
    patch_post(
        dict(
            data=dict(
                tenant="id",
                user=[dict(default_membership=dict(tenant_id=str(uuid.uuid4())))],
            )
        )
    )

    client = MagicMock()
    client.return_value.login_to_tenant = MagicMock(return_value=True)
    monkeypatch.setattr("prefect.cli.auth.Client", client)

    runner = CliRunner()
    result = runner.invoke(auth, ["login", "--token", "test"])
    assert result.exit_code == 0


def test_auth_login_client_error(patch_post, cloud_api):
    patch_post(dict(errors=[dict(error={})]))

    runner = CliRunner()
    result = runner.invoke(auth, ["login", "--token", "test"])
    assert result.exit_code == 0
    assert "Error attempting to communicate with Prefect Cloud" in result.output


def test_auth_logout_after_login(patch_post, monkeypatch, cloud_api):
    patch_post(
        dict(
            data=dict(
                tenant="id",
                user=[dict(default_membership=dict(tenant_id=str(uuid.uuid4())))],
            )
        )
    )

    client = MagicMock()
    client.return_value.login_to_tenant = MagicMock(return_value=True)
    monkeypatch.setattr("prefect.cli.auth.Client", client)

    runner = CliRunner()

    result = runner.invoke(auth, ["login", "--token", "test"])
    assert result.exit_code == 0

    result = runner.invoke(auth, ["logout"], input="Y")
    assert result.exit_code == 0


def test_auth_logout_not_confirm(patch_post, cloud_api):
    patch_post(dict(data=dict(auth_info=dict(tenant_id="id"))))

    client = prefect.Client(api_key="foo")
    client._write_auth_to_disk()

    runner = CliRunner()
    result = runner.invoke(auth, ["logout"], input="N")
    assert result.exit_code == 1


def test_auth_logout_not_logged_in(patch_post, cloud_api):
    patch_post(dict(data=dict(tenant="id")))

    runner = CliRunner()
    result = runner.invoke(auth, ["logout"], input="Y")
    assert result.exit_code == 1
    assert "not logged in to Prefect Cloud" in result.output


def test_auth_logout_api_token_removes_api_token(patch_post, cloud_api):
    patch_post(dict(data=dict(tenant="id")))

    client = prefect.Client(api_token="foo")
    client._save_local_settings({"api_token": client._api_token})

    runner = CliRunner()
    result = runner.invoke(auth, ["logout"], input="Y")
    assert result.exit_code == 0
    assert "This will remove your API token" in result.output

    client = prefect.Client()
    assert "api_token" not in client._load_local_settings()

    patch_post(dict(data=dict(tenant="id")))

    runner = CliRunner()
    result = runner.invoke(auth, ["logout"], input="Y")
    assert result.exit_code == 0
    assert "No tenant currently active" in result.output


def test_list_tenants(patch_post, cloud_api):
    patch_post(
        dict(
            data=dict(
                tenant=[{"id": "id", "slug": "slug", "name": "name"}],
                switch_tenant={
                    "access_token": "access_token",
                    "expires_in": "expires_in",
                    "refresh_token": "refresh_token",
                },
            )
        )
    )

    runner = CliRunner()
    result = runner.invoke(auth, ["list-tenants"])
    assert result.exit_code == 0
    assert "id" in result.output
    assert "slug" in result.output
    assert "name" in result.output


def test_switch_tenants_success(monkeypatch, cloud_api):
    monkeypatch.setattr("prefect.cli.auth.Client", MagicMock())

    runner = CliRunner()
    result = runner.invoke(auth, ["switch-tenants", "--slug", "slug"])
    assert result.exit_code == 0
    assert "Tenant switched" in result.output


def test_switch_tenants_failed(monkeypatch, cloud_api):
    client = MagicMock()
    client.return_value.login_to_tenant = MagicMock(return_value=False)
    monkeypatch.setattr("prefect.cli.auth.Client", client)

    runner = CliRunner()
    result = runner.invoke(auth, ["switch-tenants", "--slug", "slug"])
    assert result.exit_code == 0
    assert "Unable to switch tenant" in result.output


def test_create_token(patch_post, cloud_api):
    patch_post(dict(data=dict(create_api_token={"token": "token"})))

    runner = CliRunner()
    result = runner.invoke(auth, ["create-token", "-n", "name", "-s", "scope"])
    assert result.exit_code == 0
    assert "token" in result.output


def test_create_token_fails(patch_post, cloud_api):
    patch_post(dict())

    runner = CliRunner()
    result = runner.invoke(auth, ["create-token", "-n", "name", "-s", "scope"])
    assert result.exit_code == 0
    assert "Issue creating API token" in result.output


def test_list_tokens(patch_post, cloud_api):
    patch_post(dict(data=dict(api_token=[{"id": "id", "name": "name"}])))

    runner = CliRunner()
    result = runner.invoke(auth, ["list-tokens"])
    assert result.exit_code == 0
    assert "id" in result.output
    assert "name" in result.output


def test_list_tokens_fails(patch_post, cloud_api):
    patch_post(dict())

    runner = CliRunner()
    result = runner.invoke(auth, ["list-tokens"])
    assert result.exit_code == 0
    assert "Unable to list API tokens" in result.output


def test_revoke_token(patch_post, cloud_api):
    patch_post(dict(data=dict(delete_api_token={"success": True})))

    runner = CliRunner()
    result = runner.invoke(auth, ["revoke-token", "--id", "id"])
    assert result.exit_code == 0
    assert "Token successfully revoked" in result.output


def test_revoke_token_fails(patch_post, cloud_api):
    patch_post(dict())

    runner = CliRunner()
    result = runner.invoke(auth, ["revoke-token", "--id", "id"])
    assert result.exit_code == 0
    assert "Unable to revoke token with ID id" in result.output


def test_check_override_function():
    with set_temporary_config({"cloud.auth_token": "TOKEN"}):
        with pytest.raises(click.exceptions.Abort):
            prefect.cli.auth.check_override_auth_token()


def test_override_functions_on_commands(cloud_api):
    with set_temporary_config({"cloud.auth_token": "TOKEN"}):
        runner = CliRunner()
        result = runner.invoke(auth, ["revoke-token", "--id", "id"])
        assert result.exit_code == 1
