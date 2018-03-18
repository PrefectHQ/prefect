import pytest
from prefect.utilities import collections


@pytest.fixture
def nested_dict():
    return {
        1: 2,
        2: {
            1: 2,
            3: 4
        },
        3: {
            1: 2,
            3: {
                4: 5,
                6: {
                    7: 8
                }
            }
        },
    }


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
