import pytest
from unittest.mock import MagicMock

import prefect
from prefect.client import Client, Secret
from prefect.utilities.tests import set_temporary_config


#################################
##### Client Tests
#################################
def test_client_initializes_from_kwargs():
    client = Client(
        api_server="api_server", graphql_server="graphql_server", token="token"
    )
    assert client._api_server == "api_server"
    assert client._graphql_server == "graphql_server"
    assert client._token == "token"


def test_client_initializes_from_config():
    with set_temporary_config("server.api_server", "api_server"):
        with set_temporary_config("server.graphql_server", "graphql_server"):
            with set_temporary_config("server.token", "token"):
                client = Client()
    assert client._api_server == "api_server"
    assert client._graphql_server == "graphql_server"
    assert client._token is None


def test_client_initializes_from_context():
    with set_temporary_config("server.api_server", None):
        with set_temporary_config("server.graphql_server", None):
            with set_temporary_config("server.token", None):
                with prefect.context(
                    api_server="api_server",
                    graphql_server="graphql_server",
                    token="token",
                ):
                    client = Client()

    assert client._api_server == "api_server"
    assert client._graphql_server == "graphql_server"
    assert client._token == "token"


def test_client_logs_in_and_saves_token(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, json=MagicMock(return_value=dict(token="secret_token"))
        )
    )
    monkeypatch.setattr("requests.post", post)
    client = Client(api_server="http://my-server.foo")
    client.login("test@example.com", "1234")
    assert post.called
    assert post.call_args[0][0] == "http://my-server.foo/login"
    assert post.call_args[1]["auth"] == ("test@example.com", "1234")
    assert client._token == "secret_token"


def test_client_raises_if_login_fails(monkeypatch):
    post = MagicMock(return_value=MagicMock(ok=False))
    monkeypatch.setattr("requests.post", post)
    client = Client(api_server="http://my-server.foo")
    with pytest.raises(ValueError):
        client.login("test@example.com", "1234")
    assert post.called
    assert post.call_args[0][0] == "http://my-server.foo/login"


#################################
##### Secret Tests
#################################


def test_create_secret():
    secret = Secret(name="test")
    assert secret


def test_secret_get_none():
    secret = Secret(name="test")
    assert secret.get() is None


def test_secret_value_pulled_from_context():
    secret = Secret(name="test")
    with prefect.context(_secrets=dict(test=42)):
        assert secret.get() == 42
    assert secret.get() is None


def test_secret_value_depends_on_use_local_secrets(monkeypatch):
    secret = Secret(name="test")
    monkeypatch.setattr(prefect.config.server, "use_local_secrets", False)
    with prefect.context(_secrets=dict(test=42)):
        assert secret.get() is None
