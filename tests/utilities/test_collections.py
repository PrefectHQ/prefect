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

    def test_initialization_with_mutable_mapping(self, mutable_mapping):
        d = DotDict(mutable_mapping)

    def test_update_with_kwargs(self):
        d = DotDict(chris=10, attr='string', other=lambda x: {})
        d.update(another=500)

    def test_update_with_mutable_mapping(self, mutable_mapping):
        d = DotDict({'chris': 10, 'attr': 'string', 'other': lambda x: {}})
        d.update(mutable_mapping)
