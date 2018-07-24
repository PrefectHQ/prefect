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


def test_container_tag():
    container = Container(image="test", tag="test_tag")
    assert container.tag == "test_tag"


def test_containet_tag_none():
    container = Container(image="test")
    assert container.tag == "test"


def test_build_image():
    container = Container(
        image="ubuntu:16.04", python_dependencies=["docker", "raven", "toml"]
    )
    image = container.build()
    assert image


# Will need a fixture
# def test_run_container():
#     container = Container(image="ubuntu:16.04")
#     container_running = container.run()
#     assert container_running
