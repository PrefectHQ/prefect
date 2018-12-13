import pytest
from unittest.mock import MagicMock

import prefect
from prefect.client import Secret
from prefect.utilities.tests import set_temporary_config


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
    with prefect.context(secrets=dict(test=42)):
        assert secret.get() == 42
    assert secret.get() is None


def test_secret_value_depends_on_use_local_secrets():
    secret = Secret(name="test")
    with set_temporary_config({"cloud.use_local_secrets": False}):
        with prefect.context(secrets=dict(test=42)):
            with pytest.raises(ValueError) as exc:
                secret.get()
            assert "Client.login" in str(exc.value)
