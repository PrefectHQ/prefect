import pytest

import prefect
from prefect.environments.storage import Docker


def test_create_docker_storage():
    storage = Docker()
    assert storage


def test_serialize_docker_storage():
    storage = Docker()
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Docker"
