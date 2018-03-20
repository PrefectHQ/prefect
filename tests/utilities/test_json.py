import datetime
import json
import prefect
import prefect.utilities.json as codecs


def default_load_json(obj):
    return json.JSONDecoder().decode(obj)


def test_json_codec_datetime():
    d = datetime.datetime(2020, 1, 2, 3, 4, 5, 6)

    j = json.dumps(d)
    assert j == json.dumps({'__datetime__': d.isoformat()})
    assert d == json.loads(j)


def test_json_codec_timedelta():
    t = datetime.timedelta(days=2, hours=5, microseconds=15)
    j = json.dumps(t)
    assert j == json.dumps({'__timedelta__': t.total_seconds()})
    assert t == json.loads(j)


def test_json_codec_date():
    d = datetime.datetime(2020, 1, 2, 3, 4, 5, 6).date()
    j = json.dumps(d)
    assert j == json.dumps({'__date__': d.isoformat()})
    assert d == json.loads(j)


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
    j = json.dumps(codecs.EncryptedCodec(x))
    assert len(default_load_json(j)['__encrypted__']) > 20
    assert x == json.loads(j)


def test_json_codec_set():
    x = set([3, 4, 5])
    j = json.dumps(x)
    assert default_load_json(j)['__set__'] == [3, 4, 5]
    assert x == json.loads(j)


@codecs.serializable
def serializable_fn():
    return 'hi'


def test_json_codec_imported_object():

    j = json.dumps(serializable_fn)
    assert default_load_json(j) == {
        '__imported_object__': 'tests.utilities.test_json.serializable_fn'
    }
    assert serializable_fn == json.loads(j)


class JsonMethodClass:

    def __json__(self):
        return dict(a=1, b=2, c=datetime.datetime(2000, 1, 1))


def test_json_method():

    x = JsonMethodClass()
    j = json.dumps(x)
    assert j == json.dumps(dict(a=1, b=2, c=datetime.datetime(2000, 1, 1)))


class ObjectDictClass:

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __eq__(self, o):
        return type(self) == type(o) and self.a == o.a and self.b == o.b


def test_json_object_attributes_codec():
    x = ObjectDictClass(1, 2)

    dict_codec = codecs.ObjectAttributesCodec(x)
    assert dict_codec.attributes_list == list(x.__dict__.keys())
    dict_j = default_load_json(json.dumps(dict_codec))
    assert dict_j['__object_attrs__']['attrs'] == x.__dict__
    assert json.loads(json.dumps(dict_codec)) == x

    attr_codec = codecs.ObjectAttributesCodec(x, attributes_list=['a'])
    assert attr_codec.attributes_list == ['a']
    attr_j = default_load_json(json.dumps(attr_codec))
    assert attr_j['__object_attrs__']['attrs'] == {'a': x.a}
    j = json.loads(json.dumps(attr_codec))
    assert isinstance(j, ObjectDictClass)
    assert j.a == x.a
    assert not hasattr(j, 'b')


def test_json_codec_object_attrs_dict():
    """Without arguments, the ObjectAttributesCodec will serialize the __dict__
    """

    x = ObjectDictClass(1, datetime.datetime(2000, 1, 1))
    j = json.dumps(codecs.ObjectAttributesCodec(x))

    assert default_load_json(j) == {
        "__object_attrs__": {
            "type": {
                "__imported_object__":
                "tests.utilities.test_json.ObjectDictClass"
            },
            "attrs": {
                "a": 1,
                "b": {
                    '__datetime__': '2000-01-01T00:00:00'
                }
            }
        }
    }
    assert x == json.loads(j)


class SerializableObj(codecs.Serializable):

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __eq__(self, o):
        return type(self) == type(o) and self.a == o.a and self.b == o.b


def test_serializable_class():
    """
    Tests that objects subclassing Serializable are automatically serialized.
    """

    x = SerializableObj(1, datetime.datetime(2000, 1, 1))
    j = json.dumps(x)

    assert x.json_codec is codecs.ObjectAttributesCodec

    assert j == json.dumps(
        {
            "__object_attrs__": {
                "type": {
                    "__imported_object__":
                    "tests.utilities.test_json.SerializableObj"
                },
                "attrs": {
                    "a": 1,
                    "b": {
                        '__datetime__': '2000-01-01T00:00:00'
                    }
                }
            }
        })
    assert x == json.loads(j)


def test_qualified_type():
    assert codecs.qualified_type(
        SerializableObj) == 'tests.utilities.test_json.SerializableObj'
