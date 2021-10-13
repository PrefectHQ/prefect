import datetime
import json
from pathlib import Path
import uuid
from unittest.mock import MagicMock

import marshmallow
import pendulum
import pytest
import requests
import toml

import prefect
from prefect.client.client import Client, FlowRunInfoResult, TaskRunInfoResult
from prefect.utilities.graphql import GraphQLResult
from prefect.engine.result import Result
from prefect.engine.state import Pending, Running, State
from prefect.environments.execution import LocalEnvironment
from prefect.storage import Local
from prefect.run_configs import LocalRun
from prefect.utilities.configuration import set_temporary_config
from prefect.exceptions import ClientError, AuthorizationError
from prefect.utilities.graphql import decompress


class TestClientAuthentication:
    """
    These tests cover Client handling of API key based authentication
    """

    def test_client_determines_api_key_in_expected_order(self):
        # 1. Directly passed
        # 2. From the config
        # 3. From the disk

        # No key should be present yet
        client = Client()
        assert client.api_key is None

        # Save to disk
        client = Client(api_key="DISK_KEY")
        client.save_auth_to_disk()

        # Set in config
        with set_temporary_config({"cloud.api_key": "CONFIG_KEY"}):

            # Should ignore config/disk
            client = Client(api_key="DIRECT_KEY")
            assert client.api_key == "DIRECT_KEY"

            # Should load from config
            client = Client()
            assert client.api_key == "CONFIG_KEY"

        # Should load from disk
        client = Client()
        assert client.api_key == "DISK_KEY"

    def test_client_determines_tenant_id_in_expected_order(self):
        # 1. Directly passed
        # 2. From the config
        # 3. From the disk

        # No key should be present yet
        client = Client()
        assert client._tenant_id is None

        # Save to disk (and set an API key so we don't enter API token logic)
        client = Client(api_key="KEY", tenant_id="DISK_TENANT")
        client.save_auth_to_disk()

        # Set in config
        with set_temporary_config({"cloud.tenant_id": "CONFIG_TENANT"}):

            # Should ignore config/disk
            client = Client(tenant_id="DIRECT_TENANT")
            assert client._tenant_id == "DIRECT_TENANT"

            # Should load from config
            client = Client()
            assert client._tenant_id == "CONFIG_TENANT"

        # Should load from disk
        client = Client()
        assert client._tenant_id == "DISK_TENANT"

    def test_client_save_auth_to_disk(self):

        # Ensure saving is robust to a missing directory
        Path(prefect.context.config.home_dir).rmdir()

        client = Client(api_key="KEY", tenant_id="ID")
        client.save_auth_to_disk()

        data = toml.loads(client._auth_file.read_text())
        assert set(data.keys()) == {client._api_server_slug}
        assert data[client._api_server_slug] == dict(api_key="KEY", tenant_id="ID")

        old_key = client._api_server_slug
        client.api_server = "foo"
        client.api_key = "NEW_KEY"
        client.tenant_id = "NEW_ID"
        client.save_auth_to_disk()

        data = toml.loads(client._auth_file.read_text())
        assert set(data.keys()) == {client._api_server_slug, old_key}
        assert data[client._api_server_slug] == dict(
            api_key="NEW_KEY", tenant_id="NEW_ID"
        )

        # Old data is unchanged
        assert data[old_key] == dict(api_key="KEY", tenant_id="ID")

    def test_client_load_auth_from_disk(self):
        client = Client(api_key="KEY", tenant_id="ID")
        client.save_auth_to_disk()

        client = Client()

        assert client.api_key == "KEY"
        assert client.tenant_id == "ID"

        client._auth_file.write_text(
            toml.dumps(
                {
                    client._api_server_slug: {
                        "api_key": "NEW_KEY",
                        "tenant_id": "NEW_ID",
                    }
                }
            )
        )
        data = client.load_auth_from_disk()

        # Does not mutate the client!
        assert client.api_key == "KEY"
        assert client.tenant_id == "ID"

        assert data["api_key"] == "NEW_KEY"
        assert data["tenant_id"] == "NEW_ID"

    def test_client_sets_api_key_in_header(self, monkeypatch):
        Session = MagicMock()
        monkeypatch.setattr("requests.Session", Session)
        client = Client(api_key="foo")

        client.get("path")

        headers = Session().get.call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer foo"

        # Tenant id is _not_ included by default
        assert "X-PREFECT-TENANT-ID" not in headers

    def test_client_sets_tenant_id_in_header(self, monkeypatch):
        Session = MagicMock()
        monkeypatch.setattr("requests.Session", Session)

        client = Client(api_key="foo", tenant_id="bar")
        client.get("path")

        headers = Session().get.call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer foo"
        assert "X-PREFECT-TENANT-ID" in headers
        assert headers["X-PREFECT-TENANT-ID"] == "bar"

    def test_client_does_not_set_tenant_id_in_header_when_using_api_token(
        self, monkeypatch
    ):
        Session = MagicMock()
        monkeypatch.setattr("requests.Session", Session)

        client = Client(api_token="foo", tenant_id="bar")
        client.get("path")

        headers = Session().get.call_args[1]["headers"]
        assert "X-PREFECT-TENANT-ID" not in headers

    @pytest.mark.parametrize("tenant_id", [None, "id"])
    def test_client_tenant_id_returns_set_tenant_or_queries(self, tenant_id):

        client = Client(api_key="foo", tenant_id=tenant_id)
        client._get_auth_tenant = MagicMock(return_value="id")

        assert client.tenant_id == "id"

        if not tenant_id:
            client._get_auth_tenant.assert_called_once()
        else:
            client._get_auth_tenant.assert_not_called()

    def test_client_tenant_id_backwards_compat_for_api_tokens(self, monkeypatch):
        client = Client(api_token="foo")
        client._init_tenant = MagicMock()
        client.tenant_id
        client._init_tenant.assert_called_once()

    def test_client_tenant_id_gets_default_tenant_for_server(self):
        with set_temporary_config({"backend": "server"}):
            client = Client()
            client._get_default_server_tenant = MagicMock(return_value="foo")
            assert client.tenant_id == "foo"
            client._get_default_server_tenant.assert_called_once()

    def test_get_auth_tenant_queries_for_auth_info(self):
        client = Client(api_key="foo")
        client.graphql = MagicMock(
            return_value=GraphQLResult({"data": {"auth_info": {"tenant_id": "id"}}})
        )

        assert client._get_auth_tenant() == "id"
        client.graphql.assert_called_once_with({"query": {"auth_info": "tenant_id"}})

    def test_get_auth_tenant_errors_with_api_token_as_keye(self):
        client = Client(api_key="pretend-this-is-a-token")
        client.graphql = MagicMock(
            return_value=GraphQLResult({"data": {"auth_info": {"tenant_id": None}}})
        )

        with pytest.raises(
            AuthorizationError, match="API token was used as an API key"
        ):
            client._get_auth_tenant()

    def test_get_auth_tenant_errors_without_auth_set(self):
        client = Client()

        with pytest.raises(ValueError, match="have not set an API key"):
            assert client._get_auth_tenant() == "id"

    def test_get_default_server_tenant_gets_first_tenant(self):
        with set_temporary_config({"backend": "server"}):
            client = Client()
            client.graphql = MagicMock(
                return_value=GraphQLResult(
                    {"data": {"tenant": [{"id": "id1"}, {"id": "id2"}]}}
                )
            )

            assert client._get_default_server_tenant() == "id1"
            client.graphql.assert_called_once_with({"query": {"tenant": {"id"}}})

    def test_get_default_server_tenant_raises_on_no_tenants(self):
        with set_temporary_config({"backend": "server"}):
            client = Client()
            client.graphql = MagicMock(
                return_value=GraphQLResult({"data": {"tenant": []}})
            )

            with pytest.raises(ClientError, match="no tenant"):
                client._get_default_server_tenant()


def test_client_posts_to_api_server(patch_post):
    post = patch_post(dict(success=True))

    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.post("/foo/bar")
    assert result == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo/foo/bar"


def test_version_header(monkeypatch):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    client.get("/foo/bar")
    assert get.call_args[1]["headers"]["X-PREFECT-CORE-VERSION"] == str(
        prefect.__version__
    )


def test_version_header_cant_be_overridden(monkeypatch):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    client.get("/foo/bar", headers={"X-PREFECT-CORE-VERSION": "-1"})
    assert get.call_args[1]["headers"]["X-PREFECT-CORE-VERSION"] == str(
        prefect.__version__
    )


def test_client_attached_headers(monkeypatch, cloud_api):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()
        assert client._attached_headers == {}

        client.attach_headers({"1": "1"})
        assert client._attached_headers == {"1": "1"}

        client.attach_headers({"2": "2"})
        assert client._attached_headers == {"1": "1", "2": "2"}


def test_client_posts_graphql_to_api_server(patch_post):
    post = patch_post(dict(data=dict(success=True)))

    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.graphql("{projects{name}}")
    assert result.data == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo"


# test actual mutation and query handling
def test_graphql_errors_get_raised(patch_post):
    patch_post(dict(data="42", errors=[{"GraphQL issue!": {}}]))

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    with pytest.raises(ClientError, match="GraphQL issue!"):
        client.graphql("query: {}")


class TestClientGraphQLErrorHandling:
    @pytest.fixture()
    def patch_post_response(self, monkeypatch):
        response = requests.Response()
        response.status_code = 400
        session = MagicMock()
        session.return_value.post = MagicMock(return_value=response)
        monkeypatch.setattr("requests.Session", session)

    def get_client(self):
        with set_temporary_config(
            {
                "cloud.api": "http://my-cloud.foo",
                "cloud.auth_token": "secret_token",
                "backend": "cloud",
            }
        ):
            return Client()

    def test_graphql_errors_calls_formatter_and_displays(
        self, patch_post_response, monkeypatch
    ):
        formatter = MagicMock(return_value="Formatted graphql message")
        monkeypatch.setattr(
            "prefect.client.client.format_graphql_request_error", formatter
        )

        with pytest.raises(ClientError, match="Formatted graphql message"):
            self.get_client().graphql({"query": "foo"})

        formatter.assert_called_once()

    def test_graphql_errors_allow_formatter_to_fail(
        self, patch_post_response, monkeypatch
    ):
        def erroring_formatter():
            raise Exception("Bad formatter")

        monkeypatch.setattr(
            "prefect.client.client.format_graphql_request_error", erroring_formatter
        )

        with pytest.raises(
            ClientError,
            match=(
                "This is likely caused by a poorly formatted GraphQL query or "
                "mutation but the response could not be parsed for more details"
            ),
        ):
            self.get_client().graphql({"query": "foo"})


def test_client_register_raises_if_required_param_isnt_scheduled(
    patch_post, monkeypatch, tmpdir
):
    response = {
        "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
    }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    a = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.1)], parameter_defaults=dict(x=1)
    )
    b = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.25)], parameter_defaults=dict(y=2)
    )

    x = prefect.Parameter("x", required=True)

    flow = prefect.Flow(
        "test", schedule=prefect.schedules.Schedule(clocks=[a, b]), tasks=[x]
    )
    flow.storage = prefect.storage.Local(tmpdir)
    flow.result = flow.storage.result

    with pytest.raises(
        ClientError,
        match="Flows with required parameters can not be scheduled automatically",
    ):
        client.register(
            flow,
            project_name="my-default-project",
            compressed=False,
            version_group_id=str(uuid.uuid4()),
            no_url=True,
        )


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_doesnt_raise_for_scheduled_params(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    a = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.1)], parameter_defaults=dict(x=1)
    )
    b = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.25)], parameter_defaults=dict(x=2, y=5)
    )

    x = prefect.Parameter("x", required=True)
    y = prefect.Parameter("y", default=1)

    flow = prefect.Flow(
        "test", schedule=prefect.schedules.Schedule(clocks=[a, b]), tasks=[x, y]
    )
    flow.storage = prefect.storage.Local(tmpdir)
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
        no_url=True,
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register(patch_post, compressed, monkeypatch, tmpdir):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.storage.Local(tmpdir))
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
        no_url=True,
        idempotency_key="foo",
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_raises_for_keyed_flows_with_no_result(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    @prefect.task
    def a(x):
        pass

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    with prefect.Flow(name="test", storage=prefect.storage.Local(tmpdir)) as flow:
        a(prefect.Task())

    flow.result = None

    with pytest.warns(UserWarning, match="result handler"):
        client.register(
            flow,
            project_name="my-default-project",
            compressed=compressed,
            version_group_id=str(uuid.uuid4()),
            no_url=True,
        )


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_doesnt_raise_if_no_keyed_edges(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.storage.Local(tmpdir))
    flow.result = None

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
        no_url=True,
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_builds_flow(patch_post, compressed, monkeypatch, tmpdir):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    post = patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.storage.Local(tmpdir))
    flow.result = flow.storage.result

    client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        no_url=True,
        set_schedule_active=False,
    )

    # extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args_list[1][1]["json"]["variables"])["input"][
                "serialized_flow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args_list[1][1]["json"]["variables"])[
            "input"
        ]["serialized_flow"]
    assert serialized_flow["storage"] is not None


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_docker_image_name(patch_post, compressed, monkeypatch, tmpdir):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    post = patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )
    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(
        name="test",
        storage=prefect.storage.Docker(image_name="test_image"),
        environment=LocalEnvironment(),
    )
    flow.result = flow.storage.result

    client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        build=True,
        no_url=True,
        set_schedule_active=False,
    )

    # extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args_list[1][1]["json"]["variables"])["input"][
                "serialized_flow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args_list[1][1]["json"]["variables"])[
            "input"
        ]["serialized_flow"]
    assert serialized_flow["storage"] is not None
    assert "test_image" in serialized_flow["environment"]["metadata"]["image"]


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_default_prefect_image(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    post = patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )
    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(
        name="test",
        storage=prefect.storage.Local(tmpdir),
        environment=LocalEnvironment(),
    )
    flow.result = flow.storage.result

    client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        build=True,
        no_url=True,
        set_schedule_active=False,
    )

    # extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args_list[1][1]["json"]["variables"])["input"][
                "serialized_flow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args_list[1][1]["json"]["variables"])[
            "input"
        ]["serialized_flow"]
    assert serialized_flow["storage"] is not None
    assert "prefecthq/prefect" in serialized_flow["environment"]["metadata"]["image"]


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_optionally_avoids_building_flow(
    patch_post, compressed, monkeypatch
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    post = patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(name="test")
    flow.result = Result()

    client.register(
        flow,
        project_name="my-default-project",
        build=False,
        compressed=compressed,
        no_url=True,
        set_schedule_active=False,
    )

    # extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args_list[1][1]["json"]["variables"])["input"][
                "serialized_flow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args_list[1][1]["json"]["variables"])[
            "input"
        ]["serialized_flow"]
    assert serialized_flow["storage"] is None


def test_client_register_with_bad_proj_name(patch_post, monkeypatch, cloud_api):
    patch_post({"data": {"project": []}})

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()
    flow = prefect.Flow(name="test")
    flow.result = Result()

    with pytest.raises(ValueError) as exc:
        client.register(flow, project_name="my-default-project", no_url=True)
    assert "not found" in str(exc.value)
    assert "prefect create project 'my-default-project'" in str(exc.value)


def test_client_create_project_that_already_exists(patch_posts, monkeypatch):
    patch_posts(
        [
            {
                "errors": [
                    {"message": "Uniqueness violation.", "path": ["create_project"]}
                ],
                "data": {"create_project": None},
            },
            {"data": {"project": [{"id": "proj-id"}]}},
        ]
    )

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()
    project_id = client.create_project(project_name="my-default-project")
    assert project_id == "proj-id"


def test_client_delete_project(patch_post, monkeypatch):
    patch_post(
        {"data": {"project": [{"id": "test"}], "delete_project": {"success": True}}}
    )

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()
    result = client.delete_project(project_name="my-default-project")
    assert result is True


def test_client_delete_project_error(patch_post, monkeypatch):
    patch_post(
        {
            "data": {
                "project": {},
            }
        }
    )

    project_name = "my-default-project"

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()

    with pytest.raises(ValueError, match="Project {} not found".format(project_name)):
        client.delete_project(project_name=project_name)


def test_client_register_with_flow_that_cant_be_deserialized(patch_post, monkeypatch):
    patch_post({"data": {"project": [{"id": "proj-id"}]}})

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    task = prefect.Task()
    # we add a max_retries value to the task without a corresponding retry_delay;
    # this will fail at deserialization
    task.max_retries = 3
    flow = prefect.Flow(name="test", tasks=[task])
    flow.result = Result()

    with pytest.raises(
        ValueError,
        match=(
            "(Flow could not be deserialized).*"
            "(`retry_delay` must be provided if max_retries > 0)"
        ),
    ):
        client.register(
            flow, project_name="my-default-project", build=False, no_url=True
        )


@pytest.mark.parametrize("use_run_config", [True, False])
@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_flow_id_output(
    patch_post, use_run_config, compressed, monkeypatch, capsys, cloud_api, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
                "flow_by_pk": {"flow_group_id": "fg-id"},
            }
        }
    else:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow": {"id": "long-id"},
                "flow_by_pk": {"flow_group_id": "fg-id"},
            }
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    labels = ["test1", "test2"]
    storage = Local(tmpdir)
    if use_run_config:
        flow = prefect.Flow(
            name="test", storage=storage, run_config=LocalRun(labels=labels)
        )
        flow.environment = None
    else:
        flow = prefect.Flow(
            name="test", storage=storage, environment=LocalEnvironment(labels=labels)
        )
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
    )
    assert flow_id == "long-id"

    captured = capsys.readouterr()
    assert "Flow URL: https://cloud.prefect.io/tslug/flow/fg-id\n" in captured.out
    assert f"Labels: {labels}" in captured.out


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_flow_id_no_output(
    patch_post, compressed, monkeypatch, capsys, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.storage.Local(tmpdir))
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
        no_url=True,
    )
    assert flow_id == "long-id"

    captured = capsys.readouterr()
    assert not captured.out


def test_set_flow_run_name(patch_posts, cloud_api):
    mutation_resp = {"data": {"set_flow_run_name": {"success": True}}}

    patch_posts(mutation_resp)

    client = Client()
    result = client.set_flow_run_name(flow_run_id="74-salt", name="name")

    assert result is True


def test_cancel_flow_run(patch_posts, cloud_api):
    mutation_resp = {"data": {"cancel_flow_run": {"state": True}}}

    patch_posts(mutation_resp)

    client = Client()
    result = client.cancel_flow_run(flow_run_id="74-salt")

    assert result is True


def test_get_flow_run_info(patch_post):
    response = {
        "flow_run_by_pk": {
            "id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "flow_id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "name": "flow-run-name",
            "flow": {"project": {"id": "my-project-id", "name": "my-project-name"}},
            "version": 0,
            "parameters": {"a": 1},
            "context": None,
            "scheduled_start_time": "2019-01-25T19:15:58.632412+00:00",
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "PrefectResult",
                    "location": "42",
                },
                "message": None,
                "__version__": "0.3.3+309.gf1db024",
                "cached_inputs": None,
            },
            "task_runs": [
                {
                    "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                    "task": {
                        "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                        "slug": "da344768-5f5d-4eaf-9bca-83815617f713",
                    },
                    "version": 0,
                    "serialized_state": {
                        "type": "Pending",
                        "result": None,
                        "message": None,
                        "__version__": "0.3.3+309.gf1db024",
                        "cached_inputs": None,
                    },
                }
            ],
        }
    }
    patch_post(dict(data=response))

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.get_flow_run_info(flow_run_id="74-salt")
    assert isinstance(result, FlowRunInfoResult)
    assert isinstance(result.scheduled_start_time, datetime.datetime)
    assert result.scheduled_start_time.minute == 15
    assert result.scheduled_start_time.year == 2019
    assert isinstance(result.state, Pending)
    assert result.state._result.location == "42"
    assert result.state.message is None
    assert result.version == 0
    assert result.project.name == "my-project-name"
    assert result.project.id == "my-project-id"
    assert result.parameters == {"a": 1}
    assert result.context == {}


def test_get_flow_run_info_with_nontrivial_payloads(patch_post):
    response = {
        "flow_run_by_pk": {
            "id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "flow_id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "name": "flow-run-name",
            "flow": {"project": {"id": "my-project-id", "name": "my-project-name"}},
            "version": 0,
            "parameters": {"x": {"deep": {"nested": 5}}},
            "context": {"my_val": "test"},
            "scheduled_start_time": "2019-01-25T19:15:58.632412+00:00",
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "PrefectResult",
                    "location": "42",
                },
                "message": None,
                "__version__": "0.3.3+309.gf1db024",
                "cached_inputs": None,
            },
            "task_runs": [
                {
                    "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                    "task": {
                        "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                        "slug": "da344768-5f5d-4eaf-9bca-83815617f713",
                    },
                    "version": 0,
                    "serialized_state": {
                        "type": "Pending",
                        "result": None,
                        "message": None,
                        "__version__": "0.3.3+309.gf1db024",
                        "cached_inputs": None,
                    },
                }
            ],
        }
    }
    patch_post(dict(data=response))

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.get_flow_run_info(flow_run_id="74-salt")
    assert isinstance(result, FlowRunInfoResult)
    assert isinstance(result.scheduled_start_time, datetime.datetime)
    assert result.scheduled_start_time.minute == 15
    assert result.scheduled_start_time.year == 2019
    assert isinstance(result.state, Pending)
    assert result.state._result.location == "42"
    assert result.state.message is None
    assert result.version == 0
    assert result.project.name == "my-project-name"
    assert result.project.id == "my-project-id"
    assert isinstance(result.parameters, dict)
    assert result.parameters["x"]["deep"]["nested"] == 5
    # ensures all sub-dictionaries are actually dictionaries
    assert json.loads(json.dumps(result.parameters)) == result.parameters
    assert isinstance(result.context, dict)
    assert result.context["my_val"] == "test"


def test_get_flow_run_info_raises_informative_error(patch_post):
    patch_post(dict(data={"flow_run_by_pk": None}))
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    with pytest.raises(ClientError, match="not found"):
        client.get_flow_run_info(flow_run_id="74-salt")


def test_get_flow_run_state(patch_posts, cloud_api, runner_token):
    query_resp = {
        "flow_run_by_pk": {
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "PrefectResult",
                    "location": "42",
                },
                "message": None,
                "__version__": "0.3.3+310.gd19b9b7.dirty",
                "cached_inputs": None,
            },
        }
    }

    patch_posts([dict(data=query_resp)])

    client = Client()
    state = client.get_flow_run_state(flow_run_id="72-salt")
    assert isinstance(state, Pending)
    assert state._result.location == "42"
    assert state.message is None


def test_set_flow_run_state(patch_post):
    response = {
        "data": {
            "set_flow_run_states": {
                "states": [{"id": 1, "status": "SUCCESS", "message": None}]
            }
        }
    }
    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    state = Pending()
    result = client.set_flow_run_state(flow_run_id="74-salt", version=0, state=state)
    assert isinstance(result, State)
    assert isinstance(result, Pending)


def test_set_flow_run_state_gets_queued(patch_post):
    response = {
        "data": {
            "set_flow_run_states": {
                "states": [{"id": "74-salt", "status": "QUEUED", "message": None}]
            }
        }
    }
    patch_post(response)
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    state = Running()
    result = client.set_flow_run_state(flow_run_id="74-salt", version=0, state=state)
    assert isinstance(result, State)
    assert state != result
    assert result.is_queued()


@pytest.mark.parametrize("interval_seconds", [10, 20, 30, 40])
def test_set_flow_run_state_uses_config_queue_interval(
    patch_post, interval_seconds, monkeypatch
):
    response = {
        "data": {
            "set_flow_run_states": {
                "states": [{"id": "74-salt", "status": "QUEUED", "message": None}]
            }
        }
    }
    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
            "cloud.queue_interval": interval_seconds,
        }
    ):
        client = Client()

        # Mocking the concept of "now" so we can have consistent assertions
        now = pendulum.now("UTC")
        mock_now = MagicMock(return_value=now)
        monkeypatch.setattr("prefect.client.client.pendulum.now", mock_now)

        result = client.set_flow_run_state(
            flow_run_id="74-salt", version=0, state=Running()
        )
    mock_now.assert_called_once()

    assert now.add(seconds=interval_seconds) == result.start_time


def test_set_flow_run_state_with_error(patch_post):
    response = {
        "data": {"set_flow_run_state": None},
        "errors": [{"message": "something went wrong"}],
    }
    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    with pytest.raises(ClientError, match="something went wrong"):
        client.set_flow_run_state(flow_run_id="74-salt", version=0, state=Pending())


def test_get_task_run_info(patch_posts):
    mutation_resp = {
        "get_or_create_task_run_info": {
            "id": "772bd9ee-40d7-479c-9839-4ab3a793cabd",
            "version": 0,
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "PrefectResult",
                    "location": "42",
                },
                "message": None,
                "__version__": "0.3.3+310.gd19b9b7.dirty",
                "cached_inputs": None,
            },
        }
    }

    patch_posts([dict(data=mutation_resp)])
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.get_task_run_info(
        flow_run_id="74-salt", task_id="72-salt", map_index=None
    )
    assert isinstance(result, TaskRunInfoResult)
    assert isinstance(result.state, Pending)
    assert result.state._result.location == "42"
    assert result.state.message is None
    assert result.id == "772bd9ee-40d7-479c-9839-4ab3a793cabd"
    assert result.version == 0


def test_get_task_run_info_with_error(patch_post):
    response = {
        "data": {"get_or_create_task_run": None},
        "errors": [{"message": "something went wrong"}],
    }
    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    with pytest.raises(ClientError, match="something went wrong"):
        client.get_task_run_info(
            flow_run_id="74-salt", task_id="72-salt", map_index=None
        )


def test_set_task_run_name(patch_posts, cloud_api):
    mutation_resp = {"data": {"set_task_run_name": {"success": True}}}

    patch_posts(mutation_resp)

    client = Client()
    result = client.set_task_run_name(task_run_id="76-salt", name="name")

    assert result is True


def test_get_task_run_state(patch_posts, cloud_api, runner_token):
    query_resp = {
        "get_task_run_info": {
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "PrefectResult",
                    "location": "42",
                },
                "message": None,
                "__version__": "0.3.3+310.gd19b9b7.dirty",
                "cached_inputs": None,
            },
        }
    }

    patch_posts([dict(data=query_resp)])

    client = Client()
    state = client.get_task_run_state(task_run_id="72-salt")
    assert isinstance(state, Pending)
    assert state._result.location == "42"
    assert state.message is None


def test_set_task_run_state(patch_post):
    response = {"data": {"set_task_run_states": {"states": [{"status": "SUCCESS"}]}}}
    patch_post(response)
    state = Pending()

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.set_task_run_state(task_run_id="76-salt", version=0, state=state)

    assert result is state


def test_set_task_run_state_responds_to_status(patch_post):
    response = {"data": {"set_task_run_states": {"states": [{"status": "QUEUED"}]}}}
    patch_post(response)
    state = Pending()

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
    result = client.set_task_run_state(task_run_id="76-salt", version=0, state=state)

    assert result.is_queued()
    assert result.state is None  # caller should set this


def test_set_task_run_state_responds_to_config_when_queued(patch_post):
    response = {
        "data": {
            "set_task_run_states": {
                "states": [{"status": "QUEUED", "message": "hol up"}]
            }
        }
    }
    patch_post(response)
    state = Pending()

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
            "cloud.queue_interval": 750,
        }
    ):
        client = Client()
        result = client.set_task_run_state(
            task_run_id="76-salt", version=0, state=state
        )

    assert result.is_queued()
    assert result.state is None  # caller should set this
    assert result.message == "hol up"
    assert result.start_time >= pendulum.now("UTC").add(seconds=749)


def test_set_task_run_state_with_error(patch_post):
    response = {
        "data": {"set_task_run_states": None},
        "errors": [{"message": "something went wrong"}],
    }
    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    with pytest.raises(ClientError, match="something went wrong"):
        client.set_task_run_state(task_run_id="76-salt", version=0, state=Pending())


def test_create_flow_run_requires_flow_id_or_version_group_id():
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    with pytest.raises(
        ValueError, match="flow_id or version_group_id must be provided"
    ):
        client.create_flow_run()


@pytest.mark.parametrize("use_flow_id", [False, True])
@pytest.mark.parametrize("use_extra_args", [False, True])
def test_create_flow_run_with_input(patch_post, use_flow_id, use_extra_args):
    response = {
        "data": {"create_flow_run": {"id": "FOO"}},
    }
    post = patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

    kwargs = (
        {"flow_id": "my-flow-id"}
        if use_flow_id
        else {"version_group_id": "my-version-group-id"}
    )
    if use_extra_args:
        extra_kwargs = {
            "parameters": {"x": 1},
            "run_config": LocalRun(),
            "labels": ["b"],
            "context": {"key": "val"},
            "idempotency_key": "my-idem-key",
            "scheduled_start_time": datetime.datetime.now(),
            "run_name": "my-run-name",
        }
        expected = extra_kwargs.copy()
        expected.update(
            flow_run_name=expected.pop("run_name"),
            run_config=expected["run_config"].serialize(),
            scheduled_start_time=expected["scheduled_start_time"].isoformat(),
            **kwargs,
        )
        kwargs.update(extra_kwargs)
    else:
        expected = kwargs

    assert client.create_flow_run(**kwargs) == "FOO"
    variables = json.loads(post.call_args[1]["json"]["variables"])
    input = variables["input"]
    assert variables["input"] == expected


def test_get_default_tenant_slug_as_user(patch_post):
    response = {
        "data": {"user": [{"default_membership": {"tenant": {"slug": "tslug"}}}]}
    }

    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
        slug = client.get_default_tenant_slug(as_user=True)

        assert slug == "tslug"


def test_get_default_tenant_slug_not_as_user(patch_post):
    response = {
        "data": {
            "tenant": [
                {"slug": "tslug", "id": "tenant-id"},
                {"slug": "wrongslug", "id": "foo"},
            ]
        }
    }

    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.tenant_id": "tenant-id",
            "backend": "cloud",
        }
    ):
        client = Client()
        slug = client.get_default_tenant_slug(as_user=False)

        assert slug == "tslug"


def test_get_default_tenant_slug_not_as_user_with_no_tenant_id(patch_post):
    # Generally, this would occur when using a RUNNER API token
    response = {
        "data": {
            "tenant": [
                {"slug": "firstslug", "id": "tenant-id"},
                {"slug": "wrongslug", "id": "foo"},
            ]
        }
    }

    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()
        client._tenant_id = None  # Ensure tenant id is not set
        slug = client.get_default_tenant_slug(as_user=False)

        assert slug == "firstslug"


def test_get_cloud_url_as_user(patch_post, cloud_api):
    response = {
        "data": {"user": [{"default_membership": {"tenant": {"slug": "tslug"}}}]}
    }

    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://api.prefect.io",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

        url = client.get_cloud_url(subdirectory="flow", id="id", as_user=True)
        assert url == "http://cloud.prefect.io/tslug/flow/id"

        url = client.get_cloud_url(subdirectory="flow-run", id="id2", as_user=True)
        assert url == "http://cloud.prefect.io/tslug/flow-run/id2"


def test_get_cloud_url_not_as_user(patch_post, cloud_api):
    response = {
        "data": {
            "tenant": [
                {"slug": "tslug", "id": "tenant-id"},
                {"slug": "wrongslug", "id": "foo"},
            ]
        }
    }

    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://api.prefect.io",
            "backend": "cloud",
        }
    ):
        client = Client()
        client._tenant_id = "tenant-id"

        url = client.get_cloud_url(subdirectory="flow", id="id", as_user=False)
        assert url == "http://cloud.prefect.io/tslug/flow/id"

        url = client.get_cloud_url(subdirectory="flow-run", id="id2", as_user=False)
        assert url == "http://cloud.prefect.io/tslug/flow-run/id2"


def test_get_cloud_url_different_regex(patch_post, cloud_api):
    response = {
        "data": {"user": [{"default_membership": {"tenant": {"slug": "tslug"}}}]}
    }

    patch_post(response)

    with set_temporary_config(
        {
            "cloud.api": "http://api-hello.prefect.io",
            "cloud.auth_token": "secret_token",
            "backend": "cloud",
        }
    ):
        client = Client()

        url = client.get_cloud_url(subdirectory="flow", id="id")
        assert url == "http://hello.prefect.io/tslug/flow/id"

        url = client.get_cloud_url(subdirectory="flow-run", id="id2")
        assert url == "http://hello.prefect.io/tslug/flow-run/id2"


def test_register_agent(cloud_api):
    with set_temporary_config({"backend": "cloud"}):
        client = Client(api_key="foo")
        client.graphql = MagicMock(
            return_value=GraphQLResult(
                {
                    "data": {
                        "register_agent": {"id": "AGENT-ID"},
                        "auth_info": {"tenant_id": "TENANT-ID"},
                    }
                }
            )
        )

        agent_id = client.register_agent(
            agent_type="type", name="name", labels=["1", "2"], agent_config_id="asdf"
        )

    client.graphql.assert_called_with(
        {
            "mutation($input: register_agent_input!)": {
                "register_agent(input: $input)": {"id"}
            }
        },
        variables={
            "input": {
                "type": "type",
                "name": "name",
                "labels": ["1", "2"],
                "tenant_id": "TENANT-ID",
                "agent_config_id": "asdf",
            }
        },
    )
    assert agent_id == "AGENT-ID"


def test_register_agent_raises_error(patch_post, cloud_api):
    response = {"data": {"register_agent": {"id": None}}}

    patch_post(response)

    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()

        with pytest.raises(ValueError):
            client.register_agent(agent_type="type", name="name", labels=["1", "2"])


def test_get_agent_config(patch_post, cloud_api):
    response = {"data": {"agent_config": [{"settings": {"yes": "no"}}]}}

    patch_post(response)

    with set_temporary_config({"cloud.auth_token": "secret_token", "backend": "cloud"}):
        client = Client()

        agent_config = client.get_agent_config(agent_config_id="id")
        assert agent_config == {"yes": "no"}


def test_artifacts_client_functions(patch_post, cloud_api):
    response = {
        "data": {
            "create_task_run_artifact": {"id": "artifact_id"},
            "update_task_run_artifact": {"success": True},
            "delete_task_run_artifact": {"success": True},
        }
    }

    patch_post(response)

    client = Client()

    artifact_id = client.create_task_run_artifact(
        task_run_id="tr_id", kind="kind", data={"test": "data"}, tenant_id="t_id"
    )
    assert artifact_id == "artifact_id"

    client.update_task_run_artifact(task_run_artifact_id="tra_id", data={"new": "data"})
    client.delete_task_run_artifact(task_run_artifact_id="tra_id")

    response = {
        "data": {
            "create_task_run_artifact": {"id": None},
        }
    }

    patch_post(response)

    with pytest.raises(ValueError):
        client.create_task_run_artifact(
            task_run_id="tr_id", kind="kind", data={"test": "data"}, tenant_id="t_id"
        )

    with pytest.raises(ValueError):
        client.update_task_run_artifact(task_run_artifact_id=None, data={"new": "data"})

    with pytest.raises(ValueError):
        client.delete_task_run_artifact(task_run_artifact_id=None)


def test_client_posts_graphql_to_api_server_backend_server(patch_post):
    post = patch_post(dict(data=dict(success=True)))

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "backend": "server",
        }
    ):
        client = Client()
    result = client.graphql("{projects{name}}")
    assert result.data == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo"
