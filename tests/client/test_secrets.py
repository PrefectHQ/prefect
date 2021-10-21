from unittest.mock import MagicMock

import box
import pytest

import prefect
from prefect.client import Secret
from prefect.utilities.configuration import set_temporary_config
from prefect.exceptions import AuthorizationError, ClientError

#################################
##### Secret Tests
#################################


def test_create_secret():
    secret = Secret(name="test")
    assert secret


def test_secret_raises_if_doesnt_exist():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with pytest.raises(ValueError, match="not found"):
            secret.get()


def test_secret_raises_informative_error_for_server():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": False, "backend": "server"}):
        with pytest.raises(ValueError) as exc:
            secret.get()
    assert str(exc.value) == 'Local Secret "test" was not found.'


def test_secret_value_pulled_from_context():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42)):
            assert secret.get() == 42
        with pytest.raises(ValueError):
            secret.get()


def test_secret_value_depends_on_use_local_secrets(monkeypatch):
    response = {"errors": "Malformed Authorization header"}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    secret = Secret(name="test")
    with set_temporary_config(
        {"cloud.use_local_secrets": False, "cloud.auth_token": None}
    ):
        with prefect.context(secrets=dict()):
            with pytest.raises(ClientError):
                secret.get()


def test_secrets_use_client(monkeypatch, cloud_api):
    response = {"data": {"secret_value": '"1234"'}}
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


def test_cloud_secrets_use_context_first(monkeypatch):
    response = {"data": {"secret_value": '"1234"'}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.auth_token": "secret_token", "cloud.use_local_secrets": False}
    ):
        with prefect.context(secrets={"the-key": "foo"}):
            my_secret = Secret(name="the-key")
            val = my_secret.get()
    assert val == "foo"


def test_cloud_secrets_use_context_first_but_fallback_to_client(monkeypatch, cloud_api):
    response = {"data": {"secret_value": '"1234"'}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.auth_token": "secret_token", "cloud.use_local_secrets": False}
    ):
        with prefect.context(secrets={}):
            my_secret = Secret(name="the-key")
            val = my_secret.get()
    assert val == "1234"


def test_cloud_secrets_remain_plain_dictionaries(monkeypatch, cloud_api):
    response = {"data": {"secret_value": {"a": "1234", "b": [1, 2, {"c": 3}]}}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.auth_token": "secret_token", "cloud.use_local_secrets": False}
    ):
        my_secret = Secret(name="the-key")
        val = my_secret.get()
    assert val == {"a": "1234", "b": [1, 2, {"c": 3}]}
    assert isinstance(val, dict) and not isinstance(val, box.Box)
    val2 = val["b"]
    assert isinstance(val2, list) and not isinstance(val2, box.BoxList)
    val3 = val["b"][2]
    assert isinstance(val3, dict) and not isinstance(val3, box.Box)


def test_cloud_secrets_auto_load_json_strings(monkeypatch, cloud_api):
    response = {"data": {"secret_value": '{"x": 42}'}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.auth_token": "secret_token", "cloud.use_local_secrets": False}
    ):
        my_secret = Secret(name="the-key")
        val = my_secret.get()

    assert isinstance(val, dict)


def test_local_secrets_auto_load_json_strings():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test='{"x": 42}')):
            assert secret.get() == {"x": 42}
        with pytest.raises(ValueError):
            secret.get()


def test_local_secrets_remain_plain_dictionaries():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test={"x": 42})):
            assert isinstance(prefect.context.secrets["test"], dict)
            val = secret.get()
            assert val == {"x": 42}
            assert isinstance(val, dict) and not isinstance(val, box.Box)


def test_secrets_raise_if_in_flow_context():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42)):
            with prefect.Flow("test"):
                with pytest.raises(ValueError):
                    secret.get()


def test_secrets_dont_raise_just_because_flow_key_is_populated():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42), flow="not None"):
            assert secret.get() == 42
