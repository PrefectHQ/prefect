import datetime
import json
import pytest

from prefect.utilities.serialize import JSONSerializable, json_serializable
from prefect.signals import SerializationError


def default_load_json(obj):
    return json.JSONDecoder().decode(obj)


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


def test_json_bytes():
    b = b'hello, world!'
    j = json.dumps(b)
    assert j == json.dumps({'__bytes__': b.decode()})
    assert b == json.loads(j)


class Serializeable(JSONSerializable):
    _serialize_encrypt = False
    _serialize_fields = ['z']

    def __init__(self, x=1, y=2, **kwargs):
        self.x = x
        self.y = y
        self.count_kwargs = len(kwargs)

    @property
    def z(self):
        return self.x + self.y


def test_serialize_objects():

    # test with args
    x = Serializeable(1, y=2, a=3, b=datetime.datetime(2020, 1, 1))
    assert 'z' in default_load_json(json.dumps(x))
    x2 = json.loads(json.dumps(x))
    assert type(x) == type(x2)
    assert x2.z == 3
    assert x2.count_kwargs == 2

    # test that serializing without args won't put them in the serialization
    y = Serializeable()
    y._serialize_fields = []
    assert len(default_load_json(json.dumps(y))) == 2


def test_encrypt_serialization():
    x = Serializeable(1, y=2)
    x._serialize_encrypt = True
    assert '__encrypted__' in default_load_json(json.dumps(x))
    obj = json.loads(json.dumps(x))
    assert isinstance(obj, Serializeable)


def test_unserializable_objects():

    class NotSerializeableVarArgs(JSONSerializable):

        def __init__(self, *args, **kwargs):
            pass

    with pytest.raises(SerializationError):
        NotSerializeableVarArgs(1, 2, 3)


@json_serializable
def serialize_fn():
    return 1


def test_serialize_functions():

    fn = json.loads(json.dumps(serialize_fn))
    assert fn() == 1

    with pytest.raises(SerializationError):

        @json_serializable
        def cant_serialize_fn():
            return 1

        json.loads(json.dumps(cant_serialize_fn))
