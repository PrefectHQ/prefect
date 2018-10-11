import prefect
from prefect.client import Secret


#################################
##### Secret Tests
#################################


def test_create_secret():
    secret = Secret(name="test")
    assert secret
    assert secret._use_local_secrets is prefect.config.server.use_local_secrets


def test_secret_get_none():
    secret = Secret(name="test")
    assert secret.get() is None


def test_secret_value_pulled_from_context():
    secret = Secret(name="test")
    with prefect.context(_secrets=dict(test=42)):
        assert secret.get() == 42
    assert secret.get() is None


def test_secret_value_depends_on_prefect_config():
    secret = Secret(name="test")
    secret._use_local_secrets = False
    with prefect.context(_secrets=dict(test=42)):
        assert secret.get() is None
