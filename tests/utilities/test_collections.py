import pytest

from prefect.utilities import collections
from prefect.utilities.collections import DotDict


@pytest.fixture
def nested_dict():
    return {1: 2, 2: {1: 2, 3: 4}, 3: {1: 2, 3: {4: 5, 6: {7: 8}}}}


def test_flatten_dict(nested_dict):
    flat = collections.dict_to_flatdict(nested_dict)
    assert flat == {
        collections.CompoundKey([1]): 2,
        collections.CompoundKey([2, 1]): 2,
        collections.CompoundKey([2, 3]): 4,
        collections.CompoundKey([3, 1]): 2,
        collections.CompoundKey([3, 3, 4]): 5,
        collections.CompoundKey([3, 3, 6, 7]): 8,
    }


def test_nest_flattened_dict(nested_dict):
    flat = collections.dict_to_flatdict(nested_dict)
    nested = collections.flatdict_to_dict(flat)
    assert nested == nested_dict


@pytest.fixture(params=[dict(another=500),
                        DotDict(another=500)])
def mutable_mapping(request):
    "MutableMapping objects to test with"
    return request.param


class TestDotDict:
    def test_initialization_with_kwargs(self):
        d = DotDict(chris=10, attr='string', other=lambda x: {})
        assert 'another' not in d
        assert 'chris' in d
        assert 'attr' in d
        assert 'other' in d

    def test_initialization_with_mutable_mapping(self, mutable_mapping):
        d = DotDict(mutable_mapping)
        assert 'chris' not in d
        assert 'another' in d

    def test_update_with_kwargs(self):
        d = DotDict(chris=10, attr='string', other=lambda x: {})
        assert 'another' not in d
        d.update(another=500)
        assert 'another' in d
        assert d['another'] == 500

    def test_update_with_mutable_mapping(self, mutable_mapping):
        d = DotDict({'chris': 10, 'attr': 'string', 'other': lambda x: {}})
        assert 'another' not in d
        d.update(mutable_mapping)
        assert 'another' in d

    def test_len(self):
        d = DotDict({'chris': 10, 'attr': 'string', 'other': lambda x: {}})
        assert len(d) == 3
        a = DotDict()
        assert len(a) == 0
        a.update(new=4)
        assert len(a) == 1
        del d['chris']
        assert len(d) == 2

    @pytest.mark.parametrize("key", ["keys", "update", "get", "items"])
    def test_reserved_attrs_raise_error_on_init(self, key):
        with pytest.raises(ValueError):
            d = DotDict({key: 5})

    @pytest.mark.parametrize("key", ["keys", "update", "get", "items"])
    def test_reserved_attrs_raise_error_on_set(self, key):
        with pytest.raises(ValueError):
            d = DotDict(data=5)
            d.__setattr__(key, 'value')

    def test_attr_updates_and_key_updates_agree(self):
        d = DotDict(data=5)
        d.data += 1
        assert d['data'] == 6
        d['new'] = 'value'
        assert d.new == 'value'
        d.another_key = 'another_value'
        assert d['another_key'] == 'another_value'

    def test_del_with_getitem(self):
        d = DotDict(data=5)
        del d['data']
        assert 'data' not in d
        assert len(d) == 0

    def test_del_with_attr(self):
        d = DotDict(data=5)
        del d.data
        assert 'data' not in d
        assert len(d) == 0

    def test_get(self):
        d = DotDict(data=5)
        assert d.get('data') == 5
        assert d.get('no_data') is None
        assert d.get('no_data', 'fallback') == 'fallback'

    def test_keyerror_is_thrown_when_accessing_nonexistent_key(self):
        d = DotDict(data=5)
        with pytest.raises(KeyError):
            d['nothing']

    def test_attributeerror_is_thrown_when_accessing_nonexistent_attr(self):
        d = DotDict(data=5)
        with pytest.raises(AttributeError):
            d.nothing

    def test_setdefault_works(self):
        pass
