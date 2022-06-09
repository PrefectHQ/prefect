import json
from dataclasses import dataclass

import pydantic
import pytest

from prefect.utilities.collections import (
    AutoEnum,
    PartialModel,
    dict_to_flatdict,
    flatdict_to_dict,
    visit_collection,
)


class Color(AutoEnum):
    RED = AutoEnum.auto()
    BLUE = AutoEnum.auto()


class TestAutoEnum:
    async def test_autoenum_generates_string_values(self):
        assert Color.RED.value == "RED"
        assert Color.BLUE.value == "BLUE"

    async def test_autoenum_repr(self):
        assert repr(Color.RED) == str(Color.RED) == "Color.RED"

    async def test_autoenum_can_be_json_serialized_with_default_encoder(self):
        json.dumps(Color.RED) == "RED"


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


class ExtraPydantic(pydantic.BaseModel):
    x: int
    _y: int

    class Config:
        extra = pydantic.Extra.allow


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
            (ExtraPydantic(x=1, _y=2, z=3), ExtraPydantic(x=1, _y=-2, z=3)),
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
            (ExtraPydantic(x=1, _y=2, z=4), {2, 4}),
        ],
    )
    async def test_visit_collection(self, inp, expected):
        result = await visit_collection(
            inp, visit_fn=visit_even_numbers, return_data=False
        )
        assert result is None
        assert EVEN == expected


class TestPartialModel:
    def test_init(self):
        p = PartialModel(SimplePydantic)
        assert p.model_cls == SimplePydantic
        assert p.fields == {}

    def test_init_with_fields(self):
        p = PartialModel(SimplePydantic, x=1, y=2)
        assert p.fields == {"x": 1, "y": 2}
        m = p.finalize()
        assert isinstance(m, SimplePydantic)
        assert m == SimplePydantic(x=1, y=2)

    def test_init_with_invalid_field(self):
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            PartialModel(SimplePydantic, x=1, z=2)

    def test_set_attribute(self):
        p = PartialModel(SimplePydantic)
        p.x = 1
        p.y = 2
        assert p.finalize() == SimplePydantic(x=1, y=2)

    def test_set_invalid_attribute(self):
        p = PartialModel(SimplePydantic)
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            p.z = 1

    def test_set_already_set_attribute(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="Field 'x' has already been set"):
            p.x = 2

    def test_finalize_with_fields(self):
        p = PartialModel(SimplePydantic)
        m = p.finalize(x=1, y=2)
        assert isinstance(m, SimplePydantic)
        assert m == SimplePydantic(x=1, y=2)

    def test_finalize_with_invalid_field(self):
        p = PartialModel(SimplePydantic)
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            p.finalize(z=1)

    def test_finalize_with_already_set_field(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="Field 'x' has already been set"):
            p.finalize(x=1)

    def test_finalize_with_missing_field(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="validation error"):
            p.finalize()
