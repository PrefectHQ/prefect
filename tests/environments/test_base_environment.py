import pytest

from prefect.environments import Environment
from prefect.environments.storage import Docker


def test_create_environment():
    environment = Environment()
    assert environment


def test_setup_environment_passes():
    environment = Environment()
    environment.setup(storage=Docker())
    assert environment


def test_execute_environment_passes():
    environment = Environment()
    environment.execute(storage=Docker())
    assert environment


def test_serialize_environment():
    environment = Environment()
    env = environment.serialize()
    assert env["type"] == "Environment"
