import os
import pytest
import requests
from unittest.mock import MagicMock, mock_open

import prefect
from prefect.client import Client, Secret
from prefect.utilities.tests import set_temporary_config


#################################
##### Client Tests
#################################


def test_client_initializes_from_config():
    with set_temporary_config("server.api_server", "api_server"):
        with set_temporary_config("server.graphql_server", "graphql_server"):
            with set_temporary_config("server.auth_token", "token"):
                client = Client()
    assert client.api_server == "api_server"
    assert client.graphql_server == "graphql_server"
    assert client.token == "token"


def test_client_token_initializes_from_kwarg():
    with set_temporary_config("server.api_server", "api_server"):
        with set_temporary_config("server.graphql_server", "graphql_server"):
            with set_temporary_config("server.auth_token", "token"):
                client = Client(token="init-token")
    assert client.api_server == "api_server"
    assert client.graphql_server == "graphql_server"
    assert client.token == "init-token"


def test_client_token_initializes_from_file(monkeypatch):
    monkeypatch.setattr("os.path.exists", MagicMock(return_value=True))
    monkeypatch.setattr("builtins.open", mock_open(read_data="TOKEN"))
    client = Client()
    assert client.token == "TOKEN"


def test_client_token_priotizes_config_over_file(monkeypatch):
    monkeypatch.setattr("os.path.exists", MagicMock(return_value=True))
    monkeypatch.setattr("builtins.open", mock_open(read_data="file-token"))
    with set_temporary_config("server.auth_token", "config-token"):
        client = Client()
    assert client.token == "config-token"


def test_client_logs_in_and_saves_token(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, json=MagicMock(return_value=dict(token="secrettoken"))
        )
    )
    monkeypatch.setattr("os.path.exists", MagicMock(return_value=True))
    mock_file = mock_open()
    monkeypatch.setattr("builtins.open", mock_file)
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.api_server", "http://my-server.foo"):
        client = Client()
    client.login("test@example.com", "1234")
    assert post.called
    assert post.call_args[0][0] == "http://my-server.foo/login"
    assert post.call_args[1]["auth"] == ("test@example.com", "1234")
    assert client.token == "secrettoken"
    assert mock_file.call_args[0] == ("~/.prefect/.credentials/auth_token", "w+")


def test_client_logs_out_and_deletes_auth_token(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, json=MagicMock(return_value=dict(token="secrettoken"))
        )
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.api_server", "http://my-server.foo"):
        client = Client()
    client.login("test@example.com", "1234")
    assert os.path.exists("~/.prefect/.credentials/auth_token")
    with open("~/.prefect/.credentials/auth_token", "r") as f:
        assert f.read() == "secrettoken"
    client.logout()
    assert not os.path.exists("~/.prefect/.credentials/auth_token")


def test_client_raises_if_login_fails(monkeypatch):
    post = MagicMock(return_value=MagicMock(ok=False))
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.api_server", "http://my-server.foo"):
        client = Client()
    with pytest.raises(ValueError):
        client.login("test@example.com", "1234")
    assert post.called
    assert post.call_args[0][0] == "http://my-server.foo/login"


def test_client_posts_raises_with_no_token(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.api_server", "http://my-server.foo"):
        client = Client()
    with pytest.raises(ValueError) as exc:
        result = client.post("/foo/bar")
    assert "Client.login" in str(exc.value)


def test_client_posts_to_api_server(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(success=True)))
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.api_server", "http://my-server.foo"):
        client = Client(token="secret_token")
    result = client.post("/foo/bar")
    assert result == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-server.foo/foo/bar"


def test_client_posts_retries_if_token_needs_refreshing(monkeypatch):
    error = requests.HTTPError()
    error.response = MagicMock(status_code=401)  # unauthorized
    post = MagicMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(side_effect=error),
            json=MagicMock(return_value=dict(token="new-token")),
        )
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.api_server", "http://my-server.foo"):
        client = Client(token="secret_token")
    with pytest.raises(requests.HTTPError) as exc:
        result = client.post("/foo/bar")
    assert exc.value is error
    assert post.call_count == 3  # first call -> refresh token -> last call
    assert post.call_args[0][0] == "http://my-server.foo/foo/bar"
    assert client.token == "new-token"


def test_client_posts_graphql_to_graphql_server(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(success=True)))
        )
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.graphql_server", "http://my-server.foo/graphql"):
        client = Client(token="secret_token")
    result = client.graphql("{projects{name}}")
    assert result == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-server.foo/graphql"


def test_client_graphql_retries_if_token_needs_refreshing(monkeypatch):
    error = requests.HTTPError()
    error.response = MagicMock(status_code=401)  # unauthorized
    post = MagicMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(side_effect=error),
            json=MagicMock(return_value=dict(token="new-token")),
        )
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config("server.graphql_server", "http://my-server.foo/graphql"):
        client = Client(token="secret_token")
    with pytest.raises(requests.HTTPError) as exc:
        result = client.graphql("{}")
    assert exc.value is error
    assert post.call_count == 3  # first call -> refresh token -> last call
    assert post.call_args[0][0] == "http://my-server.foo/graphql"
    assert client.token == "new-token"


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
        with pytest.raises(ValueError) as exc:
            secret.get()
        assert "Client.login" in str(exc.value)
