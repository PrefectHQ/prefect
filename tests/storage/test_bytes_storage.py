import pytest

import prefect
from prefect.environments.storage import Bytes


def test_create_bytes_storage():
    storage = Bytes()
    assert storage


def test_build_bytes_storage_not_implemented():
    storage = Bytes()
    with pytest.raises(NotImplementedError):
        storage.build(prefect.Flow("test"))


def test_serialize_bytes_storage():
    storage = Bytes()
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Bytes"
