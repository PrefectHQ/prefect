import prefect
from prefect.client import Secret


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
