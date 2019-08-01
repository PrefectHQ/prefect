import json
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.client import Secret
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.exceptions import AuthorizationError

#################################
##### Secret Tests
#################################


def test_create_secret():
    secret = Secret(name="test")
    assert secret


def test_secret_raises_if_doesnt_exist():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with pytest.raises(ValueError) as exc:
            secret.get()
    assert "not found" in str(exc.value)


def test_secret_value_pulled_from_context():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42)):
            assert secret.get() == 42
        with pytest.raises(ValueError):
            secret.get()


def test_secret_value_depends_on_use_local_secrets():
    secret = Secret(name="test")
    with set_temporary_config(
        {"cloud.use_local_secrets": False, "cloud.auth_token": None}
    ):
        with prefect.context(secrets=dict(test=42)):
            with pytest.raises(AuthorizationError) as exc:
                secret.get()
    assert "Client.login" in str(exc.value)


def test_secrets_use_client(monkeypatch):
    response = {"data": {"secretValue": "1234"}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.auth_token": "secret_token", "cloud.use_local_secrets": False}
    ):
        my_secret = Secret(name="the-key")
        val = my_secret.get()
    assert val == "1234"


def test_local_secrets_auto_load_json_strings():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test='{"x": 42}')):
            assert secret.get() == {"x": 42}
        with pytest.raises(ValueError):
            secret.get()


def test_secrets_raise_if_in_flow_context():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42)):
            with prefect.Flow("test"):
                with pytest.raises(ValueError) as exc:
                    secret.get()


def test_secrets_dont_raise_just_because_flow_key_is_populated():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42), flow="not None"):
            assert secret.get() == 42
