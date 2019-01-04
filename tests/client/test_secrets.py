import json
import pytest
from unittest.mock import MagicMock

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


def test_secret_get_none():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        assert secret.get() is None


def test_secret_value_pulled_from_context():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(test=42)):
            assert secret.get() == 42
        assert secret.get() is None


def test_secret_value_depends_on_use_local_secrets():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": False}):
        with prefect.context(secrets=dict(test=42)):
            with pytest.raises(AuthorizationError) as exc:
                secret.get()
            assert "Client.login" in str(exc.value)


def test_secrets_use_client(monkeypatch):
    response = """
    {
        "secretValue": "1234"
    }
    """
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=json.loads(response)))
        )
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.use_local_secrets": False,
        }
    ):
        my_secret = Secret(name="the-key")
        val = my_secret.get()
    assert val == "1234"
