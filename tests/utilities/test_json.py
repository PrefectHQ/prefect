import pytest
import datetime
import json
import prefect.utilities.json as codecs


@codecs.serializable
def a_test_fn():
    pass


def default_load_json(obj):
    return json.JSONDecoder().decode(obj)


class EqMixin:

    def __eq__(self, other):
        return type(self) == type(other) and self.__dict__ == other.__dict__


class TestObjectFromString:

    class NestedClass:
        pass

    def test_local_obj(self):
        obj = codecs.object_from_string(codecs.qualified_name(a_test_fn))
        assert obj == a_test_fn

    def test_nested_obj(self):
        obj = codecs.object_from_string(codecs.qualified_name(self.NestedClass))
        assert obj == self.NestedClass

    def test_renamed_obj(self):
        from prefect.utilities.json import JSONCodec as jc
        assert codecs.object_from_string(codecs.qualified_name(jc)) == jc

    def test_bad_obj(self):
        with pytest.raises(ValueError):
            codecs.object_from_string('not.a.real.object')

    def test_unimported_obj(self):
        with pytest.raises(ValueError):
            # need a real module that hasn't been imported anywhere
            codecs.object_from_string('MODULE.path')


class TestTypeCodecs:

    def test_json_codec_datetime(self):
        d = datetime.datetime(2020, 1, 2, 3, 4, 5, 6)

        j = json.dumps(d)
        assert j == json.dumps({'//datetime': d.isoformat()})
        assert d == json.loads(j)

    def test_json_codec_timedelta(self):
        t = datetime.timedelta(days=2, hours=5, microseconds=15)
        j = json.dumps(t)
        assert j == json.dumps({'//timedelta': t.total_seconds()})
        assert t == json.loads(j)

    def test_json_codec_date(self):
        d = datetime.datetime(2020, 1, 2, 3, 4, 5, 6).date()
        j = json.dumps(d)
        assert j == json.dumps({'//date': d.isoformat()})
        assert d == json.loads(j)

    def test_json_codec_bytes(self):
        b = b'hello, world!'
        j = json.dumps(b)
        assert j == json.dumps({'//b': b.decode()})
        assert b == json.loads(j)

    def test_json_codec_multiple(self):
        x = dict(b=b'hello, world!', d=datetime.datetime(2020, 1, 1))
        j = json.dumps(x)
        assert x == json.loads(j)

    def test_json_codec_encrypted(self):
        x = 1
        j = json.dumps(codecs.EncryptedCodec(x))
        assert len(default_load_json(j)['//encrypted']) > 20
        assert x == json.loads(j)

    def test_json_codec_set(self):
        x = set([3, 4, 5])
        j = json.dumps(x)
        assert default_load_json(j)['//set'] == [3, 4, 5]
        assert x == json.loads(j)

    def test_json_codec_load(self):

        j = json.dumps(a_test_fn)
        assert default_load_json(j) == {
            '//obj': 'tests.utilities.test_json.a_test_fn'
        }
        assert a_test_fn == json.loads(j)


class TestObjectSerialization:

    class ClassWithJSONMethod(EqMixin):

        def __json__(self):
            return dict(a=1, b=2, c=datetime.datetime(2000, 1, 1))

    class ObjectWithAttrs(EqMixin):

        def __init__(self, a, b):
            self.a = a
            self.b = b

    def test_class_with_json_method(self):

        x = self.ClassWithJSONMethod()
        j = json.dumps(x)
        assert j == json.dumps(dict(a=1, b=2, c=datetime.datetime(2000, 1, 1)))

    def test_object_attrs_codec(self):
        x = self.ObjectWithAttrs(1, 2)

        dict_codec = codecs.ObjectAttributesCodec(x)
        assert dict_codec.attrs == list(x.__dict__.keys())
        dict_j = default_load_json(json.dumps(dict_codec))
        assert dict_j['//obj_attrs']['attrs'] == x.__dict__
        assert json.loads(json.dumps(dict_codec)) == x

        attr_codec = codecs.ObjectAttributesCodec(x, attributes_list=['a'])
        assert attr_codec.attrs == ['a']
        attr_j = default_load_json(json.dumps(attr_codec))
        assert attr_j['//obj_attrs']['attrs'] == {'a': x.a}
        j = json.loads(json.dumps(attr_codec))
        assert isinstance(j, self.ObjectWithAttrs)
        assert j.a == x.a
        assert not hasattr(j, 'b')

    def test_object_attrs_codec_no_args(self):
        """
        Without arguments, the ObjectAttributesCodec will serialize the __dict__
        """

        x = self.ObjectWithAttrs(1, datetime.datetime(2000, 1, 1))
        j = json.dumps(codecs.ObjectAttributesCodec(x))

        assert x == json.loads(j)
        assert isinstance(json.loads(j), self.ObjectWithAttrs)


class TestObjectInitArgsSerialization:

    class InitTwoArgs(EqMixin):

        def __init__(self, a, b):
            self.a = a
            self.b = b

    class InitTwoArgsUnderscore(EqMixin):

        def __init__(self, a, b):
            self._a = a
            self._b = b

    class InitTwoArgsNotStored(EqMixin):

        def __init__(self, a, b):
            self.a = a

    class InitTwoArgsPreferUnderscore(EqMixin):

        def __init__(self, a, b):
            self.a = a + 1
            self._a = a
            self.b = b

    class InitArgDict(EqMixin):

        def __init__(self, a, b):
            self.a = a + 1
            self._a = a + 1
            self._init_args = dict(a=a, b=b)

    class InitKwargs(EqMixin):

        def __init__(self, **test_kwargs):
            self.test_kwargs = test_kwargs

    class InitKwargsDict(EqMixin):

        def __init__(self, a, **test_kwargs):
            self.a = a
            self._init_args = dict(test_kwargs=test_kwargs)

    def test_two_args(self):
        x = self.InitTwoArgs(1, 2)
        assert json.loads(json.dumps(codecs.ObjectInitArgsCodec(x))) == x

    def test_two_args_underscore(self):
        x = self.InitTwoArgsUnderscore(1, 2)
        assert json.loads(json.dumps(codecs.ObjectInitArgsCodec(x))) == x

    def test_two_args_not_stored(self):
        x = self.InitTwoArgsNotStored(1, 2)
        with pytest.raises(ValueError):
            json.loads(json.dumps(codecs.ObjectInitArgsCodec(x)))

    def test_two_args_prefer_underscore(self):
        x = self.InitTwoArgsPreferUnderscore(1, 2)
        assert json.loads(json.dumps(codecs.ObjectInitArgsCodec(x))) == x

    def test_init_arg_dict(self):
        x = self.InitArgDict(1, 2)
        assert json.loads(json.dumps(codecs.ObjectInitArgsCodec(x))) == x

    def test_init_kwargs(self):
        x = self.InitKwargs(a=1, b=2)
        assert json.loads(json.dumps(codecs.ObjectInitArgsCodec(x))) == x

    def test_init_kwargs_dict(self):
        x = self.InitKwargsDict(a=1, b=2)
        assert json.loads(json.dumps(codecs.ObjectInitArgsCodec(x))) == x


class TestSerializableClass:

    class SerializableObj(codecs.Serializable, EqMixin):

        def __init__(self, a, b):
            self.a = a
            self.b = b

    def test_serializable_class(self):
        """
        Tests that objects subclassing Serializable are automatically serialized.
        """

        x = self.SerializableObj(1, datetime.datetime(2000, 1, 1))

        assert x._json_codec is codecs.ObjectInitArgsCodec
        assert x == json.loads(json.dumps(x))
