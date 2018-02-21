import datetime
import json

import pytest

from prefect.signals import SerializationError
from prefect.utilities.serialize import (Encrypted, Serializable, serializable)


def default_load_json(obj):
    return json.JSONDecoder().decode(obj)


def test_json_codec_datetime():
    d = datetime.datetime(2020, 1, 1)
    j = json.dumps(d)
    assert j == json.dumps({'__datetime__': d.isoformat()})
    assert d == json.loads(j)


def test_json_codec_timedelta():
    t = datetime.timedelta(days=2, hours=5, microseconds=15)
    j = json.dumps(t)
    assert j == json.dumps({'__timedelta__': t.total_seconds()})
    assert t == json.loads(j)


def test_json_codec_bytes():
    b = b'hello, world!'
    j = json.dumps(b)
    assert j == json.dumps({'__bytes__': b.decode()})
    assert b == json.loads(j)


def test_json_codec_multiple():
    x = dict(b=b'hello, world!', d=datetime.datetime(2020, 1, 1))
    j = json.dumps(x)
    assert x == json.loads(j)


def test_json_codec_encrypted():
    x = 1
    j = json.dumps(Encrypted(x))
    assert len(default_load_json(j)['__encrypted__']) > 20
    assert x == json.loads(j)


def test_json_codec_set():
    x = set([3, 4, 5])
    j = json.dumps(x)
    assert default_load_json(j)['__set__'] == [3, 4, 5]
    assert x == json.loads(j)


class Serializable(Serializable):

    def __init__(self, x=1, y=2, **kwargs):
        self.count_kwargs = len(kwargs)


def test_serialize_objects():

    # test with args
    x = Serializable(1, y=2, a=3, b=datetime.datetime(2020, 1, 1))
    x2 = json.loads(json.dumps(x))
    assert type(x) == type(x2)
    assert x2.count_kwargs == 2


def test_encrypted():
    x = Encrypted(Serializable(1, y=2))
    assert '__encrypted__' in default_load_json(json.dumps(x))
    obj = json.loads(json.dumps(x))
    assert isinstance(obj, Serializable)


def test_unserializable_objects():

    class NotSerializeableVarArgs(Serializable):

        def __init__(self, *args, **kwargs):
            pass

    with pytest.raises(SerializationError):
        NotSerializeableVarArgs(1, 2, 3)


@serializable
def serialize_fn():
    return 1


def test_serialize_functions():

    fn = json.loads(json.dumps(serialize_fn))
    assert fn() == 1

    with pytest.raises(SerializationError):

        @serializable
        def cant_serialize_fn():
            return 1

        json.loads(json.dumps(cant_serialize_fn))
