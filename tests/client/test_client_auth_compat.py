"""
This file tests Client auth handling with API tokens which have been deprecated in
favor of API keys. All of these tests are for backwards compatibility and can be removed
in 0.16.0 when API tokens are dropped.
"""
import json
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pendulum
import pytest
import requests
import toml

import prefect
from prefect.client.client import Client, FlowRunInfoResult, TaskRunInfoResult
from prefect.engine.result import Result
from prefect.engine.state import Pending
from prefect.utilities.configuration import set_temporary_config
from prefect.exceptions import AuthorizationError, ClientError
from prefect.utilities.graphql import GraphQLResult, decompress


class TestClientConfig:
    def test_client_initializes_from_config(self):
        with set_temporary_config(
            {
                "cloud.graphql": "api_server",
                "cloud.auth_token": "token",
                "backend": "cloud",
            }
        ):
            client = Client()
        assert client.api_server == "api_server"
        assert client._api_token == "token"

    def test_client_initializes_and_prioritizes_kwargs(self):
        with set_temporary_config(
            {
                "cloud.graphql": "api_server",
                "cloud.auth_token": "token",
                "backend": "cloud",
            }
        ):
            client = Client(api_server="my-graphql")
        assert client.api_server == "my-graphql"
        assert client._api_token == "token"

    def test_client_settings_path_is_path_object(self, cloud_api):
        assert isinstance(Client()._api_token_settings_path, Path)

    def test_client_settings_path_depends_on_api_server(
        self, prefect_home_dir, cloud_api
    ):
        path = Client(
            api_server="https://a-test-api.prefect.test/subdomain"
        )._api_token_settings_path
        expected = os.path.join(
            prefect_home_dir,
            "client",
            "https-a-test-api.prefect.test-subdomain",
            "settings.toml",
        )
        assert str(path) == expected

    def test_client_settings_path_depends_on_home_dir(self, cloud_api):
        with set_temporary_config(dict(home_dir="abc/def")):
            path = Client(api_server="xyz")._api_token_settings_path
            expected = os.path.join("abc", "def", "client", "xyz", "settings.toml")
            assert str(path) == os.path.expanduser(expected)

    def test_client_token_initializes_from_file(selfmonkeypatch, cloud_api):
        with tempfile.TemporaryDirectory() as tmp:
            with set_temporary_config({"home_dir": tmp, "cloud.graphql": "xyz"}):
                path = Path(tmp) / "client" / "xyz" / "settings.toml"
                path.parent.mkdir(parents=True)
                with path.open("w") as f:
                    toml.dump(dict(api_token="FILE_TOKEN"), f)

                client = Client()
                client._init_tenant()
        assert client._api_token == "FILE_TOKEN"

    def test_client_token_priotizes_config_over_file(selfmonkeypatch, cloud_api):
        with tempfile.TemporaryDirectory() as tmp:
            with set_temporary_config(
                {
                    "home_dir": tmp,
                    "cloud.graphql": "xyz",
                    "cloud.auth_token": "CONFIG_TOKEN",
                }
            ):
                path = Path(tmp) / "client" / "xyz" / "settings.toml"
                path.parent.mkdir(parents=True)
                with path.open("w") as f:
                    toml.dump(dict(api_token="FILE_TOKEN"), f)

                client = Client()
        assert client._api_token == "CONFIG_TOKEN"

    def test_client_token_priotizes_arg_over_config(self, cloud_api):
        with set_temporary_config({"cloud.auth_token": "CONFIG_TOKEN"}):
            client = Client(api_token="ARG_TOKEN")
        assert client._api_token == "ARG_TOKEN"

    def test_save_local_settings(self, cloud_api):
        with tempfile.TemporaryDirectory() as tmp:
            with set_temporary_config({"home_dir": tmp, "cloud.graphql": "xyz"}):
                path = Path(tmp) / "client" / "xyz" / "settings.toml"

                client = Client(api_token="a")
                client.save_api_token()
                with path.open("r") as f:
                    assert toml.load(f)["api_token"] == "a"

                client = Client(api_token="b")
                client.save_api_token()
                with path.open("r") as f:
                    assert toml.load(f)["api_token"] == "b"

    def test_load_local_api_token_is_called_when_the_client_is_initialized_without_token(
        self, cloud_api
    ):
        with tempfile.TemporaryDirectory() as tmp:
            with set_temporary_config({"home_dir": tmp}):
                client = Client(api_token="a")
                client._init_tenant()
                client.save_api_token()

                client = Client(api_token="b")
                assert client._api_token == "b"
                client_local_api = Client()
                client_local_api._init_tenant()
                assert client_local_api._api_token == "a"


class TestTenantAuth:
    def test_login_to_tenant_requires_argument(self, cloud_api):
        client = Client()
        with pytest.raises(ValueError, match="At least one"):
            client.login_to_tenant()

    def test_login_to_tenant_requires_valid_uuid(self, cloud_api):
        client = Client()
        with pytest.raises(ValueError, match="valid UUID"):
            client.login_to_tenant(tenant_id="a")

    def test_login_to_client_sets_access_token(self, patch_post, cloud_api):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )
        client = Client()
        assert client._access_token is None
        assert client._refresh_token is None
        client.login_to_tenant(tenant_id=tenant_id)
        assert client._access_token == "ACCESS_TOKEN"
        assert client._refresh_token == "REFRESH_TOKEN"

    def test_login_uses_api_token(self, patch_post, cloud_api):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )
        client = Client(api_token="api")
        client.login_to_tenant(tenant_id=tenant_id)
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer api",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_login_uses_api_token_when_access_token_is_set(self, patch_post, cloud_api):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )
        client = Client(api_token="api")
        client._access_token = "access"
        client.login_to_tenant(tenant_id=tenant_id)
        assert client.get_auth_token() == "ACCESS_TOKEN"
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer api",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_graphql_uses_access_token_after_login(self, patch_post, cloud_api):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )
        client = Client(api_token="api")
        client.graphql({})
        assert client.get_auth_token() == "api"
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer api",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

        client.login_to_tenant(tenant_id=tenant_id)
        client.graphql({})
        assert client.get_auth_token() == "ACCESS_TOKEN"
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer ACCESS_TOKEN",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_login_to_tenant_writes_tenant_and_reloads_it_when_token_is_reloaded(
        self, patch_post, cloud_api
    ):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )

        client = Client(api_token="abc")
        assert client.tenant_id is None
        client.login_to_tenant(tenant_id=tenant_id)
        client.save_api_token()
        assert client.active_tenant_id == tenant_id

        # new client loads the active tenant and token
        client_load_active_tenant = Client()
        # The tenant is initialized by calling the property active_tenant_id
        assert client_load_active_tenant.active_tenant_id == tenant_id
        assert client_load_active_tenant._api_token == "abc"

    def test_login_to_client_doesnt_reload_active_tenant_when_token_isnt_loaded(
        self, patch_post, cloud_api
    ):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )

        client = Client(api_token="abc")
        assert client.tenant_id is None
        client.login_to_tenant(tenant_id=tenant_id)
        assert client.tenant_id == tenant_id

        # new client doesn't load the active tenant because there's no api token loaded
        client = Client()
        client._init_tenant()
        assert client._tenant_id is None
        # Note: Using `.tenant_id` here would active api_key logic

    def test_logout_clears_access_token_and_tenant(self, patch_post, cloud_api):
        tenant_id = str(uuid.uuid4())
        post = patch_post(
            {
                "data": {
                    "tenant": [{"id": tenant_id}],
                    "switch_tenant": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    },
                }
            }
        )
        client = Client(api_token="TOKEN")
        client.login_to_tenant(tenant_id=tenant_id)

        assert client._access_token is not None
        assert client._refresh_token is not None
        assert client.tenant_id is not None

        client.logout_from_tenant()

        assert client._access_token is None
        assert client._refresh_token is None
        assert client.tenant_id is None

        # new client doesn't load the active tenant
        assert Client(api_token="TOKEN").tenant_id is None

    def test_refresh_token_sets_attributes(self, patch_post, cloud_api):
        patch_post(
            {
                "data": {
                    "refresh_token": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    }
                }
            }
        )
        client = Client()
        assert client._access_token is None
        assert client._refresh_token is None

        # add buffer because Windows doesn't compare milliseconds
        assert client._access_token_expires_at < pendulum.now().add(seconds=1)
        client._refresh_access_token()
        assert client._access_token == "ACCESS_TOKEN"
        assert client._refresh_token == "REFRESH_TOKEN"
        assert client._access_token_expires_at > pendulum.now().add(seconds=599)

    def test_refresh_token_passes_access_token_as_arg(self, patch_post, cloud_api):
        post = patch_post(
            {
                "data": {
                    "refresh_token": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    }
                }
            }
        )
        client = Client()
        client._access_token = "access"
        client._refresh_access_token()
        variables = json.loads(post.call_args[1]["json"]["variables"])
        assert variables["input"]["access_token"] == "access"

    def test_refresh_token_passes_refresh_token_as_header(self, patch_post, cloud_api):
        post = patch_post(
            {
                "data": {
                    "refresh_token": {
                        "access_token": "ACCESS_TOKEN",
                        "expires_at": "2100-01-01",
                        "refresh_token": "REFRESH_TOKEN",
                    }
                }
            }
        )
        client = Client()
        client._refresh_token = "refresh"
        client._refresh_access_token()
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer refresh",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_get_available_tenants(self, patch_post, cloud_api):
        tenants = [
            {"id": "a", "name": "a-name", "slug": "a-slug"},
            {"id": "b", "name": "b-name", "slug": "b-slug"},
            {"id": "c", "name": "c-name", "slug": "c-slug"},
        ]
        post = patch_post({"data": {"tenant": tenants}})
        client = Client()
        gql_tenants = client.get_available_tenants()
        assert gql_tenants == tenants

    def test_get_auth_token_returns_api_if_access_token_not_set(self, cloud_api):
        client = Client(api_token="api")
        assert client._access_token is None
        assert client.get_auth_token() == "api"

    def test_get_auth_token_returns_access_token_if_set(self, cloud_api):
        client = Client(api_token="api")
        client._access_token = "access"
        assert client.get_auth_token() == "access"

    def test_get_auth_token_refreshes_if_refresh_token_and_expiration_within_30_seconds(
        self, monkeypatch, cloud_api
    ):
        refresh_token = MagicMock()
        monkeypatch.setattr("prefect.Client._refresh_access_token", refresh_token)
        client = Client(api_token="api")
        client._access_token = "access"
        client._refresh_token = "refresh"
        client._access_token_expires_at = pendulum.now().add(seconds=29)
        client.get_auth_token()
        assert refresh_token.called

    def test_get_auth_token_refreshes_if_refresh_token_and_no_expiration(
        self, monkeypatch, cloud_api
    ):
        refresh_token = MagicMock()
        monkeypatch.setattr("prefect.Client._refresh_access_token", refresh_token)
        client = Client(api_token="api")
        client._access_token = "access"
        client._refresh_token = "refresh"
        client._access_token_expires_at = None
        client.get_auth_token()
        assert refresh_token.called

    def test_get_auth_token_doesnt_refresh_if_refresh_token_and_future_expiration(
        self, monkeypatch, cloud_api
    ):
        refresh_token = MagicMock()
        monkeypatch.setattr("prefect.Client._refresh_access_token", refresh_token)
        client = Client(api_token="api")
        client._access_token = "access"
        client._refresh_token = "refresh"
        client._access_token_expires_at = pendulum.now().add(minutes=10)
        assert client.get_auth_token() == "access"
        refresh_token.assert_not_called()

    def test_client_clears_active_tenant_if_login_fails_on_initialization(
        self, patch_post, cloud_api
    ):
        post = patch_post(
            {
                "errors": [
                    {
                        "message": "",
                        "locations": [],
                        "path": ["tenant"],
                        "extensions": {"code": "UNAUTHENTICATED"},
                    }
                ]
            }
        )

        # create a client just so we can use its settings methods to store settings
        client = Client()
        settings = client._load_local_settings()
        settings.update(api_token="API_TOKEN", active_tenant_id=str(uuid.uuid4()))
        client._save_local_settings(settings)

        # this initialization will fail with the patched error
        client = Client()
        client._init_tenant()
        settings = client._load_local_settings()
        assert "active_tenant_id" not in settings

    def test_client_infers_correct_tenant_if_a_token_is_not_user_scoped(
        self, patch_posts, cloud_api
    ):
        patch_posts(
            [
                # First, raise an UNAUTHENTICATED error
                {
                    "errors": [
                        {
                            "message": "",
                            "locations": [],
                            "path": ["tenant"],
                            "extensions": {"code": "UNAUTHENTICATED"},
                        }
                    ]
                },
                # Then, return a tenant id
                {"data": {"tenant": [{"id": "tenant-id"}]}},
            ]
        )

        # create a client just so we can use its settings methods to store settings
        disk_tenant = str(uuid.uuid4())
        client = Client()
        client._save_local_settings(
            dict(api_token="API_TOKEN", active_tenant_id=disk_tenant)
        )

        # this initialization will fail to login to the active tenant then load the
        # correct tenant from the API
        client = Client(api_token="API_TOKEN")
        client._init_tenant()
        assert client._tenant_id == "tenant-id"

        # Disk is unchanged
        settings = client._load_local_settings()
        assert settings["active_tenant_id"] == disk_tenant

    @pytest.mark.parametrize("tenants", ([], [{"id": "1"}, {"id": "2"}]))
    def test_client_throws_error_during_inference_if_non_single_tenant_is_returned(
        self, patch_posts, cloud_api, tenants
    ):
        patch_posts(
            [
                # First, raise an UNAUTHENTICATED error
                {
                    "errors": [
                        {
                            "message": "",
                            "locations": [],
                            "path": ["tenant"],
                            "extensions": {"code": "UNAUTHENTICATED"},
                        }
                    ]
                },
                # Then, return tenant ids
                {"data": {"tenant": tenants}},
            ]
        )

        # create a client just so we can use its settings methods to store settings
        client = Client()
        client._save_local_settings(
            dict(api_token="API_TOKEN", active_tenant_id=str(uuid.uuid4()))
        )

        # this initialization will fail to login to the active tenant then load the
        # correct tenant from the API
        client = Client(api_token="API_TOKEN")
        with pytest.raises(ValueError, match="Failed to authorize"):
            client._init_tenant()


class TestPassingHeadersAndTokens:
    def test_headers_are_passed_to_get(self, monkeypatch, cloud_api):
        get = MagicMock()
        session = MagicMock()
        session.return_value.get = get
        monkeypatch.setattr("requests.Session", session)
        with set_temporary_config(
            {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
        ):
            client = Client()
        client.get("/foo/bar", headers={"x": "y", "Authorization": "z"})
        assert get.called
        assert get.call_args[1]["headers"] == {
            "x": "y",
            "Authorization": "Bearer secret_token",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_headers_are_passed_to_post(self, monkeypatch, cloud_api):
        post = MagicMock()
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)
        with set_temporary_config(
            {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
        ):
            client = Client()
        client.post("/foo/bar", headers={"x": "y", "Authorization": "z"})
        assert post.called
        assert post.call_args[1]["headers"] == {
            "x": "y",
            "Authorization": "Bearer secret_token",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_headers_are_passed_to_graphql(self, monkeypatch, cloud_api):
        post = MagicMock()
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)
        with set_temporary_config(
            {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
        ):
            client = Client()
        client.graphql("query {}", headers={"x": "y", "Authorization": "z"})
        assert post.called
        assert post.call_args[1]["headers"] == {
            "x": "y",
            "Authorization": "Bearer secret_token",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_tokens_are_passed_to_get(self, monkeypatch, cloud_api):
        get = MagicMock()
        session = MagicMock()
        session.return_value.get = get
        monkeypatch.setattr("requests.Session", session)
        with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
            client = Client()
        client.get("/foo/bar", token="secret_token")
        assert get.called
        assert get.call_args[1]["headers"] == {
            "Authorization": "Bearer secret_token",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_tokens_are_passed_to_post(self, monkeypatch, cloud_api):
        post = MagicMock()
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)
        with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
            client = Client()
        client.post("/foo/bar", token="secret_token")
        assert post.called
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer secret_token",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }

    def test_tokens_are_passed_to_graphql(self, monkeypatch, cloud_api):
        post = MagicMock()
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)
        with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
            client = Client()
        client.graphql("query {}", token="secret_token")
        assert post.called
        assert post.call_args[1]["headers"] == {
            "Authorization": "Bearer secret_token",
            "X-PREFECT-CORE-VERSION": str(prefect.__version__),
        }
