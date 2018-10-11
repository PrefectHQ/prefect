from prefect.client import Secret


#################################
##### Secret Tests
#################################


def test_create_secret():
    secret = Secret(name="test")
    assert secret


def test_secret_value_none():
    secret = Secret(name="test")
    assert not secret.value


def test_secret_value_set():
    secret = Secret(name="test")
    secret.value = "test_value"
    assert secret.value
