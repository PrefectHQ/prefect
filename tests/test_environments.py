import pytest

from prefect import Flow
from prefect.environments import Environment, Container, Secret

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


#################################
##### Environment Tests
#################################


def test_create_environment():
    environment = Environment()
    assert environment


def test_environment_secrets():
    secrets = [Secret(name="test")]
    environment = Environment(secrets=secrets)
    assert environment.secrets


def test_environment_secrets_none():
    environment = Environment()
    assert not environment.secrets


def test_environment_build_error():
    environment = Environment()
    with pytest.raises(NotImplementedError):
        environment.build()


#################################
##### Container Tests
#################################


def test_create_container():
    container = Container(image="test")
    assert container


def test_container_image():
    container = Container(image="test")
    assert container.image == "test"


def test_container_name():
    container = Container(image="test", name="test_name")
    assert container.name == "test_name"


def test_containet_name_none():
    container = Container(image="test")
    assert container.name == "test"
