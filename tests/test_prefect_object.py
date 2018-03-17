import uuid
import prefect
from prefect import base
import pytest


def test_generate_id():
    id1 = base.generate_uuid()
    id2 = base.generate_uuid()
    assert id1 != id2
    assert uuid.UUID(id1)


def test_create_object():
    po1 = base.PrefectObject()
    po2 = base.PrefectObject()
    assert po1 == po2
    assert po1.id != po2.id
    assert po1.id in base.PREFECT_REGISTRY
    assert po2.id in base.PREFECT_REGISTRY
    assert po1 is base.get_object_by_id(po1.id)
    assert po2 is base.get_object_by_id(po2.id)


def test_get_nonexistant_id():
    with pytest.raises(ValueError):
        base.get_object_by_id('')


def test_assign_id():
    po = base.PrefectObject()
    id1 = po.id
    # assigning invalid UUIDs fails
    with pytest.raises(ValueError):
        po.id = '1'
    # valid UUIDs work
    po.id = uuid.uuid4()
    po.id = str(uuid.uuid4())

    assert po.id != id1

    assert id1 in base.PREFECT_REGISTRY
    assert po.id in base.PREFECT_REGISTRY


def test_serialize():
    po = base.PrefectObject()
    serialized = po.serialize()
    assert serialized['type'] == 'PrefectObject'
    assert serialized['qualified_type'] == 'prefect.base.PrefectObject'
    assert serialized['id'] == po.id
    assert serialized['prefect_version'] == prefect.__version__
