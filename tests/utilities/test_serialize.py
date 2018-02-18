import datetime
import json
import pytest

from prefect.utilities.serialize import JSONSerializable, json_serializable


@pytest.fixture(autouse=True, scope='module')
def monkey_patch_json():
    from prefect.utilities.serialize import patch_json
    patch_json()


def test_json_datetime():
    d = datetime.datetime(2020, 1, 1)
    j = json.dumps(d)
    assert j == json.dumps({'__datetime__': d.isoformat()})
    assert d == json.loads(j)


def test_json_timedelta():
    t = datetime.timedelta(days=2, hours=5, microseconds=15)
    j = json.dumps(t)
    assert j == json.dumps({'__timedelta__': t.total_seconds()})
    assert t == json.loads(j)


def test_serialize_objects():

    class Serializeable(JSONSerializable):

        def __init__(self, x=1, y=2, **kwargs):
            self.z = x + y
            self.count_kwargs = len(kwargs)

    # test with args
    x = Serializeable(1, y=2, a=3, b=datetime.datetime(2020, 1, 1))
    x2 = json.loads(json.dumps(x))
    assert type(x) == type(x2)
    assert x2.z == 3
    assert x2.count_kwargs == 2

    # test that serializing without args won't put them in the serialization
    y = Serializeable()
    assert '__prefect_args__' not in json.dumps(y)

    class NotSerializeable(JSONSerializable):

        def __init__(self, *args, **kwargs):
            pass

    with pytest.raises(TypeError):
        NotSerializeable(1, 2, 3)


@json_serializable
def serialize_fn():
    return 42


def test_serialize_functions():
    fn = json.loads(json.dumps(serialize_fn))
    assert fn() == 42
