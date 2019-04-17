import pytest

import prefect
from prefect.environments.storage import Storage


def test_create_base_storage():
    storage = Storage()
    assert storage


def test_build_base_storage_not_implemented():
    storage = Storage()
    with pytest.raises(NotImplementedError):
        storage.build(prefect.Flow("test"))


def test_serialize_base_storage():
    storage = Storage()
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Storage"
