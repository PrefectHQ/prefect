import uuid
import pendulum
from unittest.mock import MagicMock

import click
import pytest
import json
from click.testing import CliRunner

import prefect
import prefect.backend
from prefect.cli.auth import auth
from prefect.utilities.configuration import set_temporary_config
from prefect.exceptions import AuthorizationError


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


def test_auth_login_client_error(patch_post, cloud_api):
    patch_post(dict(errors=[dict(error={})]))

    runner = CliRunner()
    result = runner.invoke(auth, ["login", "--key", "test"])
    assert result.exit_code == 1
    assert "Error attempting to communicate with Prefect Cloud" in result.output


def test_auth_login_with_api_key(patch_post, monkeypatch, cloud_api):
    Client = MagicMock()
    Client()._get_auth_tenant = MagicMock(return_value="tenant-id")
    TenantView = MagicMock()
    TenantView.from_tenant_id.return_value = prefect.backend.TenantView(
        tenant_id="id", name="Name", slug="tenant-slug"
    )
    monkeypatch.setattr("prefect.cli.auth.TenantView", TenantView)
    monkeypatch.setattr("prefect.cli.auth.Client", Client)

    runner = CliRunner()
    result = runner.invoke(auth, ["login", "--key", "test"])

    assert result.exit_code == 0
    assert "Logged in to Prefect Cloud tenant 'Name' (tenant-slug)" in result.output

    # Client is instantiated with the correct key and null tenant
    Client.assert_called_with(api_key="test", tenant_id=None)
    # Auth tenant is retrieved to verify key
    Client()._get_auth_tenant.assert_called_once()
    # Auth tenant is set on Client and saved to disk
    assert Client().tenant_id == "tenant-id"
    Client().save_auth_to_disk.assert_called_once()


def test_auth_login_with_api_key_client_error(patch_post, cloud_api):
    patch_post(dict(errors=[dict(error={})]))

    runner = CliRunner()
    result = runner.invoke(auth, ["login", "--key", "test"])
    assert result.exit_code == 1
    assert "Error attempting to communicate with Prefect Cloud" in result.output


def test_auth_login_with_api_key_unauthorized(patch_post, cloud_api):
    patch_post(dict(errors=[dict(error={"UNAUTHENTICATED"})]))

    runner = CliRunner()
    result = runner.invoke(auth, ["login", "--key", "test"])
    assert result.exit_code == 1
    assert "Unauthorized. Invalid Prefect Cloud API key." in result.output


def test_auth_logout_after_login(patch_post, monkeypatch, cloud_api):
    patch_post(
        dict(
            data=dict(
                tenant="id",
                user=[dict(default_membership=dict(tenant_id=str(uuid.uuid4())))],
            )
        )
    )

    Client = MagicMock()
    Client()._get_auth_tenant = MagicMock(return_value="tenant-id")
    TenantView = MagicMock()
    TenantView.from_tenant_id.return_value = prefect.backend.TenantView(
        tenant_id="id", name="Name", slug="tenant-slug"
    )
    monkeypatch.setattr("prefect.cli.auth.TenantView", TenantView)
    monkeypatch.setattr("prefect.cli.auth.Client", Client)

    runner = CliRunner()

    result = runner.invoke(auth, ["login", "--key", "test"])
    assert result.exit_code == 0

    result = runner.invoke(auth, ["logout"], input="Y")
    assert result.exit_code == 0


def test_auth_logout_not_confirm(patch_post, cloud_api):
    patch_post(dict(data=dict(auth_info=dict(tenant_id="id"))))

    client = prefect.Client(api_key="foo")
    client.save_auth_to_disk()

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


def test_auth_logout_api_token_with_tenant_removes_tenant_id(patch_posts, cloud_api):
    patch_posts(
        [
            # Login to tenant call during setup
            dict(data=dict(tenant=[dict(id=str(uuid.uuid4()))])),
            # Access token retrieval call during setup
            dict(
                data=dict(
                    switch_tenant=dict(
                        access_token="access-token",
                        expires_at=pendulum.now().isoformat(),
                        refresh_token="refresh-token",
                    )
                )
            ),
            # Login to tenant call during logout
            dict(data=dict(tenant=[dict(id=str(uuid.uuid4()))])),
            # Access token retrieval call during logout
            dict(
                data=dict(
                    switch_tenant=dict(
                        access_token="access-token",
                        expires_at=pendulum.now().isoformat(),
                        refresh_token="refresh-token",
                    )
                )
            ),
        ]
    )

    client = prefect.Client()
    client._save_local_settings(
        {"api_token": "token", "active_tenant_id": str(uuid.uuid4())}
    )

    runner = CliRunner()
    result = runner.invoke(auth, ["logout"], input="Y")

    assert result.exit_code == 0

    settings = client._load_local_settings()

    # Does not remove the API token
    assert "This will remove your API token" not in result.output
    assert "api_token" in settings

    # Removes the tenant id
    assert "Logged out from tenant" in result.output
    assert "active_tenant_id" not in settings


def test_list_tenants(patch_post, cloud_api):
    patch_post(
        dict(
            data=dict(
                auth_info={"tenant_id": "id"},
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
    with set_temporary_config({"cloud.api_key": "foo"}):
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
    assert result.exit_code == 1
    assert "Unable to switch tenant" in result.output


@pytest.mark.parametrize(
    "expires",
    [None, "2025-06-14T12:04:56.044422-05:00", "2025-12-05"],
)
@pytest.mark.parametrize("quiet", [True, False])
def test_create_key(patch_post, cloud_api, quiet, expires):
    post = patch_post(
        dict(
            data=dict(
                create_api_key={"key": "this-key"}, auth_info={"user_id": "this-id"}
            )
        )
    )

    runner = CliRunner()
    args = []
    if quiet:
        args.append("--quiet")
    if expires:
        args += ["--expire", expires]

    result = runner.invoke(auth, ["create-key", "-n", "this-name"] + args)
    assert result.exit_code == 0
    assert "this-key" in result.output if not quiet else "this-key\n" == result.output

    # Check for the correct API call
    inputs = json.loads(post.call_args[1]["json"]["variables"])["input"]
    assert inputs["name"] == "this-name"
    assert inputs["user_id"] == "this-id"
    assert inputs["expires_at"] == (
        pendulum.parse(expires, strict=False).in_tz("utc").isoformat()
        if expires
        else None
    )


def test_create_key_unparsable_expiration(patch_post, cloud_api):
    runner = CliRunner()

    result = runner.invoke(auth, ["create-key", "-n", "this-name", "-e", "foo"])
    assert result.exit_code == 1
    assert "Failed to parse expiration time. Invalid date string: foo" in result.output


def test_create_key_expiration_in_the_past(patch_post, cloud_api):
    runner = CliRunner()

    result = runner.invoke(
        auth,
        [
            "create-key",
            "-n",
            "this-name",
            "-e",
            "1900-1-1",
        ],
    )
    assert result.exit_code == 1
    assert "Given expiration time '1900-1-1' is a time in the past" in result.output


def test_create_key_fails_on_user_retrieval(patch_post, cloud_api):
    patch_post(dict())

    runner = CliRunner()
    result = runner.invoke(auth, ["create-key", "-n", "name"])
    assert result.exit_code == 1
    assert "Failed to retrieve the current user id from Prefect Cloud" in result.output


def test_create_key_fails_on_key_creation(patch_posts, cloud_api):
    patch_posts([dict(data=dict(auth_info={"user_id": "this-id"})), dict()])

    runner = CliRunner()
    result = runner.invoke(auth, ["create-key", "-n", "name"])
    assert result.exit_code == 1
    assert "Unexpected response from Prefect Cloud" in result.output


def test_list_keys(patch_post, cloud_api):
    patch_post(
        dict(data=dict(auth_api_key=[{"id": "id", "name": "name", "expires_at": None}]))
    )

    runner = CliRunner()
    result = runner.invoke(auth, ["list-keys"])
    assert result.exit_code == 0
    assert "id" in result.output
    assert "name" in result.output
    assert "NEVER" in result.output


def test_list_keys_fails_with_unexpected_response(patch_post, cloud_api):
    patch_post(dict(data={}))

    runner = CliRunner()
    result = runner.invoke(auth, ["list-keys"])
    assert result.exit_code == 1
    assert "Unexpected response from Prefect Cloud" in result.output


def test_list_keys_fails_with_no_keys(patch_post, cloud_api):
    patch_post(dict(data=dict(auth_api_key=[])))

    runner = CliRunner()
    result = runner.invoke(auth, ["list-keys"])
    assert result.exit_code == 0
    assert "You have not created any API keys" in result.output


def test_revoke_key(patch_post, cloud_api):
    patch_post(dict(data=dict(delete_api_key={"success": True})))

    runner = CliRunner()
    result = runner.invoke(auth, ["revoke-key", "--id", "id"])
    assert result.exit_code == 0
    assert "Key successfully revoked" in result.output


def test_revoke_key_fails(patch_post, cloud_api):
    patch_post(dict())

    runner = CliRunner()
    result = runner.invoke(auth, ["revoke-key", "--id", "id"])
    assert result.exit_code == 1
    assert "Unable to revoke key 'id'" in result.output
