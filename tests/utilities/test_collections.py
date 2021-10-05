import pydantic
import pytest
from dataclasses import dataclass

from prefect.utilities.collections import (
    dict_to_flatdict,
    flatdict_to_dict,
    visit_collection,
)


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


async def negative_even_numbers(x):
    if isinstance(x, int) and x % 2 == 0:
        return -x
    return x


EVEN = set()


async def visit_even_numbers(x):
    if isinstance(x, int) and x % 2 == 0:
        EVEN.add(x)


@pytest.fixture(autouse=True)
def clear_even_set():
    EVEN.clear()


@dataclass
class SimpleDataclass:
    x: int
    y: int


class SimplePydantic(pydantic.BaseModel):
    x: int
    y: int


class TestVisitCollection:
    @pytest.mark.parametrize(
        "inp,expected",
        [
            (3, 3),
            (4, -4),
            ([3, 4], [3, -4]),
            ((3, 4), (3, -4)),
            ([3, 4, [5, [6]]], [3, -4, [5, [-6]]]),
            ({3: 4, 6: 7}, {3: -4, -6: 7}),
            ({3: [4, {6: 7}]}, {3: [-4, {-6: 7}]}),
            ({3, 4, 5}, {3, -4, 5}),
            (SimpleDataclass(x=1, y=2), SimpleDataclass(x=1, y=-2)),
            (SimplePydantic(x=1, y=2), SimplePydantic(x=1, y=-2)),
        ],
    )
    async def test_visit_collection_and_transform_data(self, inp, expected):
        result = await visit_collection(
            inp, visit_fn=negative_even_numbers, return_data=True
        )
        assert result == expected

    @pytest.mark.parametrize(
        "inp,expected",
        [
            (3, set()),
            (4, {4}),
            ([3, 4], {4}),
            ((3, 4), {4}),
            ([3, 4, [5, [6]]], {4, 6}),
            ({3: 4, 6: 7}, {4, 6}),
            ({3: [4, {6: 7}]}, {4, 6}),
            ({3, 4, 5}, {4}),
            (SimpleDataclass(x=1, y=2), {2}),
            (SimplePydantic(x=1, y=2), {2}),
        ],
    )
    async def test_visit_collection(self, inp, expected):
        result = await visit_collection(
            inp, visit_fn=visit_even_numbers, return_data=False
        )
        assert result is None
        assert EVEN == expected
