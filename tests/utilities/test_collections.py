import pytest

from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict
from prefect.utilities.testing import check_for_type_errors


class TestFlatDict:
    @pytest.fixture
    def nested_dict(self):
        return {1: 2, 2: {1: 2, 3: 4}, 3: {1: 2, 3: {4: 5, 6: {7: 8}}}}

    def test_dict_to_flatdict(self, nested_dict):
        assert dict_to_flatdict(nested_dict) == {
            (1,): 2,
            (2, 1): 2,
            (2, 3): 4,
            (3, 1): 2,
            (3, 3, 4): 5,
            (3, 3, 6, 7): 8,
        }

    def test_flatdict_to_dict(self, nested_dict):
        assert flatdict_to_dict(dict_to_flatdict(nested_dict)) == nested_dict

    def test_dict_to_flatdict_return_type(self):
        check_for_type_errors(
            """
            from prefect.utilities.collections import dict_to_flatdict
            from typing import Dict, Tuple
            
            result = dict_to_flatdict({1: {2: "foo"}})
            expected: Dict[Tuple[int, ...], str] = result
            """
        )

    def test_flatdict_to_dict_return_type(self):
        check_for_type_errors(
            """
            from prefect.utilities.collections import flatdict_to_dict
            from typing import Dict, Union
            
            result = flatdict_to_dict({(1,2): "foo"})
            expected: Dict[int, Union[str, Dict[int, str]]] = result
            """
        )
