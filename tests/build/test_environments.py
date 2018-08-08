import os

import pytest

from prefect import Flow
from prefect.build.environments import (
    Environment,
    ContainerEnvironment,
    PickleEnvironment,
    Secret,
)

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
    container = ContainerEnvironment(image="test")
    assert container


def test_container_image():
    container = ContainerEnvironment(image="test")
    assert container.image == "test"


def test_container_tag():
    container = ContainerEnvironment(image="test", tag="test_tag")
    assert container.tag == "test_tag"


def test_container_tag_none():
    container = ContainerEnvironment(image="test")
    assert container.tag == "test"


@pytest.mark.skipif(os.getenv("SKIP_DOCKER_ENVIRONMENT_TESTS"))
def test_build_image():
    container = ContainerEnvironment(
        image="python:3.6-alpine", python_dependencies=["docker", "raven", "toml"]
    )
    image = container.build()
    assert image


@pytest.mark.skipif(os.getenv("SKIP_DOCKER_ENVIRONMENT_TESTS"))
def test_run_container():
    container = ContainerEnvironment(image="python:3.6-alpine")
    container_running = container.run()
    assert container_running


@pytest.mark.skipif(os.getenv("SKIP_DOCKER_ENVIRONMENT_TESTS"))
def test_check_pip_installs():
    container = ContainerEnvironment(
        image="python:3.6-alpine", python_dependencies=["docker"]
    )
    container_running = container.run(tty=True)

    pip_output = container_running.exec_run("pip freeze")
    assert b"docker" in pip_output[1]

    container_running.kill()


@pytest.mark.skipif(os.getenv("SKIP_DOCKER_ENVIRONMENT_TESTS"))
def test_environment_variables():
    secret = Secret("TEST")
    secret.value = "test_value"

    container = ContainerEnvironment(image="python:3.6-alpine", secrets=[secret])
    container.build()
    container_running = container.run(tty=True)

    echo_output = container_running.exec_run(
        "python -c 'import os; print(os.getenv(\"TEST\"))'"
    )
    assert b"test_value\n" == echo_output[1]

    container_running.kill()


#################################
##### Pickle Tests
#################################


def test_create_pickle():
    pickle_env = PickleEnvironment()
    assert pickle_env


def test_pickle_flow():
    pickle_env = PickleEnvironment()
    flow = Flow(name="test", environment=pickle_env)

    pickled_flow = flow.environment.build(flow=flow)
    assert pickled_flow


def test_unpickle_flow():
    pickle_env = PickleEnvironment()
    flow = Flow(name="test", environment=pickle_env)

    pickled_flow = flow.environment.build(flow=flow)

    serialized_flow = flow.environment.info(pickled_flow)
    assert serialized_flow["name"] == "test"
