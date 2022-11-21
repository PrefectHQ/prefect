import io
import json
import uuid
from dataclasses import dataclass
from typing import Any

import pydantic
import pytest

from prefect.utilities.collections import (
    AutoEnum,
    dict_to_flatdict,
    flatdict_to_dict,
    isiterable,
    remove_nested_keys,
    visit_collection,
)


class Color(AutoEnum):
    RED = AutoEnum.auto()
    BLUE = AutoEnum.auto()


class TestAutoEnum:
    def test_autoenum_generates_string_values(self):
        assert Color.RED.value == "RED"
        assert Color.BLUE.value == "BLUE"

    def test_autoenum_repr(self):
        assert repr(Color.RED) == str(Color.RED) == "Color.RED"

    def test_autoenum_can_be_json_serialized_with_default_encoder(self):
        json.dumps(Color.RED) == "RED"


@pytest.mark.parametrize(
    "d, expected",
    [
        (
            {1: 2},
            {(1,): 2},
        ),
        (
            {1: 2, 2: {1: 2, 3: 4}, 3: {1: 2, 3: {4: 5, 6: {7: 8}}}},
            {
                (1,): 2,
                (2, 1): 2,
                (2, 3): 4,
                (3, 1): 2,
                (3, 3, 4): 5,
                (3, 3, 6, 7): 8,
            },
        ),
        (
            {1: 2, 3: {}, 4: {5: {}}},
            {(1,): 2, (3,): {}, (4, 5): {}},
        ),
    ],
)
def test_flatdict_conversion(d, expected):
    flat = dict_to_flatdict(d)
    assert flat == expected
    assert flatdict_to_dict(flat) == d


def negative_even_numbers(x):
    print("Function called on", x)
    if isinstance(x, int) and x % 2 == 0:
        return -x
    return x


def all_negative_numbers(x):
    print("Function called on", x)
    if isinstance(x, int):
        return -x
    return x


EVEN = set()


def visit_even_numbers(x):
    if isinstance(x, int) and x % 2 == 0:
        EVEN.add(x)
    return x


VISITED = list()


def add_to_visited_list(x):
    VISITED.append(x)


@pytest.fixture(autouse=True)
def clear_sets():
    EVEN.clear()
    VISITED.clear()


@dataclass
class SimpleDataclass:
    x: int
    y: int


class SimplePydantic(pydantic.BaseModel):
    x: int
    y: int


class ExtraPydantic(pydantic.BaseModel):
    x: int

    class Config:
        extra = pydantic.Extra.allow


class PrivatePydantic(pydantic.BaseModel):
    """Pydantic model with private attrs"""

    x: int
    _y: int
    _z: Any = pydantic.PrivateAttr()

    class Config:
        underscore_attrs_are_private = True
        extra = pydantic.Extra.forbid  # Forbid extras to raise in tests


class ImmutablePrivatePydantic(PrivatePydantic):
    class Config:
        allow_mutation = False


@dataclass
class Foo:
    x: Any


@dataclass
class Bar:
    y: Any
    z: int = 2


class TestPydanticObjects:
    """
    Checks that the Pydantic test objects defined in this file behave as expected.

    These tests do not cover Prefect functionality and may break if Pydantic introduces
    breaking changes.
    """

    def test_private_pydantic_behaves_as_expected(self):
        input = PrivatePydantic(x=1)

        # Public attr accessible immediately
        assert input.x == 1
        # Extras not allowed
        with pytest.raises(ValueError):
            input._a = 1
        # Private attr not accessible until set
        with pytest.raises(AttributeError):
            input._y

        # Private attrs accessible after setting
        input._y = 4
        input._z = 5
        assert input._y == 4
        assert input._z == 5

    def test_immutable_pydantic_behaves_as_expected(self):

        input = ImmutablePrivatePydantic(x=1)

        # Public attr accessible immediately
        assert input.x == 1
        # Extras not allowed
        with pytest.raises(ValueError):
            input._a = 1
        # Private attr not accessible until set
        with pytest.raises(AttributeError):
            input._y

        # Private attrs accessible after setting
        input._y = 4
        input._z = 5
        assert input._y == 4
        assert input._z == 5

        # Mutating not allowed
        with pytest.raises(TypeError):
            input.x = 2

        # Can still mutate private attrs
        input._y = 6


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
            (ExtraPydantic(x=1, y=2, z=3), ExtraPydantic(x=1, y=-2, z=3)),
        ],
    )
    def test_visit_collection_and_transform_data(self, inp, expected):
        result = visit_collection(inp, visit_fn=negative_even_numbers, return_data=True)
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
            (ExtraPydantic(x=1, y=2, z=4), {2, 4}),
        ],
    )
    def test_visit_collection(self, inp, expected):
        result = visit_collection(inp, visit_fn=visit_even_numbers, return_data=False)
        assert result is None
        assert EVEN == expected

    @pytest.mark.parametrize(
        "inp,expected",
        [
            ({"x": 1}, [{"x": 1}, "x", 1]),
            (SimpleDataclass(x=1, y=2), [SimpleDataclass(x=1, y=2), 1, 2]),
        ],
    )
    def test_visit_collection_visits_nodes(self, inp, expected):
        result = visit_collection(inp, visit_fn=add_to_visited_list, return_data=False)
        assert result is None
        assert VISITED == expected

    @pytest.mark.parametrize(
        "inp,expected",
        [
            (sorted([1, 2, 3]), [1, -2, 3]),
            # Not treated as iterators:
            ("test", "test"),
            (b"test", b"test"),
        ],
    )
    def test_visit_collection_iterators(self, inp, expected):
        result = visit_collection(inp, visit_fn=negative_even_numbers, return_data=True)
        assert result == expected

    @pytest.mark.parametrize(
        "inp",
        [
            io.StringIO("test"),
            io.BytesIO(b"test"),
        ],
    )
    def test_visit_collection_io_iterators(self, inp):
        result = visit_collection(inp, visit_fn=lambda x: x, return_data=True)
        assert result is inp

    def test_visit_collection_allows_mutation_of_nodes(self):
        def collect_and_drop_x_from_dicts(node):
            add_to_visited_list(node)
            if isinstance(node, dict):
                return {key: value for key, value in node.items() if key != "x"}
            return node

        result = visit_collection(
            {"x": 1, "y": 2}, visit_fn=collect_and_drop_x_from_dicts, return_data=True
        )
        assert result == {"y": 2}
        assert VISITED == [{"x": 1, "y": 2}, "y", 2]

    def test_visit_collection_with_private_pydantic_attributes(self):
        """
        We should not visit private fields on Pydantic models.
        """
        input = PrivatePydantic(x=2)
        input._y = 3
        input._z = 4

        result = visit_collection(input, visit_fn=visit_even_numbers, return_data=False)
        assert EVEN == {2}, "Only the public field should be visited"
        assert result is None, "Data should not be returned"

        # The original model should not be mutated
        assert input._y == 3
        assert input._z == 4

    def test_visit_collection_includes_unset_pydantic_fields(self):
        class RandomPydantic(pydantic.BaseModel):
            val: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)

        input_model = RandomPydantic()
        output_model = visit_collection(
            input_model, visit_fn=visit_even_numbers, return_data=True
        )

        assert (
            output_model.val == input_model.val
        ), "The fields value should be used, not the default factory"

    @pytest.mark.parametrize("immutable", [True, False])
    def test_visit_collection_mutation_with_private_pydantic_attributes(
        self, immutable
    ):
        model = ImmutablePrivatePydantic if immutable else PrivatePydantic
        input = model(x=2)
        input._y = 3
        input._z = 4

        result = visit_collection(
            input, visit_fn=negative_even_numbers, return_data=True
        )

        assert result.x == -2, "The public attribute should be modified"

        # Pydantic dunders are retained
        assert result.__private_attributes__ == input.__private_attributes__
        assert result.__fields__ == input.__fields__
        assert result.__fields_set__ == input.__fields_set__

        # Private attributes are retained without modification
        assert result._y == 3
        assert result._z == 4

    @pytest.mark.skipif(True, reason="We will recurse forever in this case")
    def test_visit_collection_does_not_recurse_forever_in_reference_cycle(self):
        # Create references to each other
        foo = Foo(x=None)
        bar = Bar(y=foo)
        foo.x = bar

        visit_collection([foo, bar], visit_fn=negative_even_numbers, return_data=True)

    @pytest.mark.skipif(True, reason="We will recurse forever in this case")
    @pytest.mark.xfail(reason="We do not return correct results in this case")
    def test_visit_collection_returns_correct_result_in_reference_cycle(self):
        # Create references to each other
        foo = Foo(x=None)
        bar = Bar(y=foo)
        foo.x = bar

        result = visit_collection(
            [foo, bar], visit_fn=negative_even_numbers, return_data=True
        )
        expected_foo = Foo(x=None)
        expected_bar = Bar(y=foo, z=-2)
        expected_foo.x = expected_bar

        assert result == [expected_foo, expected_bar]

    def test_visit_collection_works_with_field_alias(self):
        class TargetConfigs(pydantic.BaseModel):
            type: str
            schema_: str = pydantic.Field(alias="schema")
            threads: int = 4

        target_configs = TargetConfigs(
            type="a_type", schema="a working schema", threads=1
        )
        result = visit_collection(
            target_configs, visit_fn=negative_even_numbers, return_data=True
        )

        assert result == target_configs

    @pytest.mark.parametrize(
        "inp,depth,expected",
        [
            (1, 0, -1),
            ([1, [2, [3, [4]]]], 0, [1, [2, [3, [4]]]]),
            ([1, [2, [3, [4]]]], 1, [-1, [2, [3, [4]]]]),
            ([1, [2, [3, [4]]]], 2, [-1, [-2, [3, [4]]]]),
            ([1, 1, 1, [2, 2, 2]], 1, [-1, -1, -1, [2, 2, 2]]),
        ],
    )
    def test_visit_collection_max_depth(self, inp, depth, expected):
        result = visit_collection(
            inp, visit_fn=all_negative_numbers, return_data=True, max_depth=depth
        )
        assert result == expected


class TestRemoveKeys:
    def test_remove_single_key(self):
        obj = {"a": "a", "b": "b", "c": "c"}
        assert remove_nested_keys(["a"], obj) == {"b": "b", "c": "c"}

    def test_remove_multiple_keys(self):
        obj = {"a": "a", "b": "b", "c": "c"}
        assert remove_nested_keys(["a", "b"], obj) == {"c": "c"}

    def test_remove_keys_recursively(self):
        obj = {
            "title": "Test",
            "description": "This is a docstring",
            "type": "object",
            "properties": {
                "a": {"title": "A", "description": "A field", "type": "string"}
            },
            "required": ["a"],
            "block_type_name": "Test",
            "block_schema_references": {},
        }
        assert remove_nested_keys(["description"], obj) == {
            "title": "Test",
            "type": "object",
            "properties": {"a": {"title": "A", "type": "string"}},
            "required": ["a"],
            "block_type_name": "Test",
            "block_schema_references": {},
        }

    def test_passes_through_non_dict(self):
        assert remove_nested_keys(["foo"], 1) == 1
        assert remove_nested_keys(["foo"], "foo") == "foo"
        assert remove_nested_keys(["foo"], b"foo") == b"foo"


class TestIsIterable:
    @pytest.mark.parametrize("obj", [[1, 2, 3], (1, 2, 3)])
    def test_is_iterable(self, obj):
        assert isiterable(obj)

    @pytest.mark.parametrize("obj", [5, Exception(), True, "hello", bytes()])
    def test_not_iterable(self, obj):
        assert not isiterable(obj)
