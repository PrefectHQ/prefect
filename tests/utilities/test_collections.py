import io
import json
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
import pydantic
import pytest

from prefect.utilities.annotations import BaseAnnotation, quote
from prefect.utilities.collections import (
    AutoEnum,
    StopVisiting,
    deep_merge,
    deep_merge_dicts,
    dict_to_flatdict,
    flatdict_to_dict,
    get_from_dict,
    isiterable,
    remove_nested_keys,
    set_in_dict,
    visit_collection,
)


class ExampleAnnotation(BaseAnnotation):
    pass


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
    model_config = pydantic.ConfigDict(extra="allow")
    x: int


class PrivatePydantic(pydantic.BaseModel):
    """Pydantic model with private attrs"""

    model_config = pydantic.ConfigDict(extra="forbid")

    x: int
    _y: int  # this is an implicit private attribute
    _z: Any = pydantic.PrivateAttr()  # this is an explicit private attribute


class ImmutablePrivatePydantic(PrivatePydantic):
    model_config = pydantic.ConfigDict(frozen=True)


class PydanticWithDefaults(pydantic.BaseModel):
    name: str
    val: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    num: int = 0


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
            input.a = 1

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
            input.a = 1
        # Private attr not accessible until set
        with pytest.raises(AttributeError):
            input._y

        # Private attrs accessible after setting
        input._y = 4
        input._z = 5
        assert input._y == 4
        assert input._z == 5

        # Mutating not allowed because frozen=True
        with pytest.raises(pydantic.ValidationError):
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
            (ExampleAnnotation(4), ExampleAnnotation(-4)),
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
            (ExtraPydantic(x=1, y=2, z=4).model_copy(), {2, 4}),
            (ExampleAnnotation(4), {4}),
        ],
    )
    def test_visit_collection(self, inp, expected):
        result = visit_collection(inp, visit_fn=visit_even_numbers, return_data=False)
        assert result is None
        assert EVEN == expected

    def test_visit_collection_does_not_consume_generators(self):
        def f():
            yield from [1, 2, 3]

        result = visit_collection([f()], visit_fn=visit_even_numbers, return_data=False)
        assert result is None
        assert not EVEN

    def test_visit_collection_does_not_consume_generators_when_returning_data(self):
        def f():
            yield from [1, 2, 3]

        val = [f()]
        result = visit_collection(val, visit_fn=visit_even_numbers, return_data=True)
        assert result is val
        assert not EVEN

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

        assert output_model.val == input_model.val, (
            "The fields value should be used, not the default factory"
        )

    @pytest.mark.parametrize(
        "input",
        [
            {"name": "prefect"},
            {"name": "prefect", "num": 1},
            {"name": "prefect", "num": 1, "val": uuid.UUID(int=0)},
            {"name": "prefect", "val": uuid.UUID(int=0)},
        ],
    )
    def test_visit_collection_remembers_unset_pydantic_fields(self, input: dict):
        input_model = PydanticWithDefaults(**input)
        output_model = visit_collection(
            input_model, visit_fn=visit_even_numbers, return_data=True
        )
        assert output_model.model_dump(exclude_unset=True) == input, (
            "Unset fields values should be remembered and preserved"
        )

    @pytest.mark.parametrize("immutable", [True, False])
    def test_visit_collection_mutation_with_private_pydantic_attributes(
        self, immutable
    ):
        model = ImmutablePrivatePydantic if immutable else PrivatePydantic
        model_instance = model(x=2)
        model_instance._y = 3
        model_instance._z = 4

        result = visit_collection(
            model_instance, visit_fn=negative_even_numbers, return_data=True
        )

        assert isinstance(result, model), "The model should be returned"

        assert result.x == -2, "The public attribute should be modified"

        # Verify that private attributes are retained
        assert getattr(result, "_y") == 3
        assert getattr(result, "_z") == 4

        # Verify fields set indirectly by checking the expected fields are still set
        for field in model_instance.model_fields_set:
            assert hasattr(result, field), (
                f"The field '{field}' should be set in the result"
            )

    def test_visit_collection_recursive_1(self):
        obj = dict()
        obj["a"] = obj
        # this would raise a RecursionError if we didn't handle it properly
        val = visit_collection(obj, lambda x: x, return_data=True)
        assert val is obj

    def test_visit_recursive_collection_2(self):
        # Create references to each other
        foo = Foo(x=None)
        bar = Bar(y=foo)
        foo.x = bar

        val = [foo, bar]

        result = visit_collection(val, lambda x: x, return_data=True)
        assert result is val

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

    def test_visit_collection_context(self):
        # Create a list of integers with various levels of nesting
        foo = [1, 2, [3, 4], [5, [6, 7]], 8, 9]

        def visit(expr, context):
            # When visiting a list, add one to the depth and return the list
            if isinstance(expr, list):
                context["depth"] += 1
                return expr
            # When visiting an integer, return it plus the depth
            else:
                return expr + context["depth"]

        result = visit_collection(foo, visit, context={"depth": 0}, return_data=True)
        # Seeded with a depth of 0, we expect all of the items in the root list to be
        # incremented by one, items in a nested list to be incremented by one, etc.
        # We confirm that integers in the root list visited after the nested lists see
        # the depth of one
        assert result == [2, 3, [5, 6], [7, [9, 10]], 9, 10]

    def test_visit_collection_context_from_annotation(self):
        foo = quote([1, 2, [3]])

        def visit(expr, context):
            # If we're not visiting the first expression...
            if not isinstance(expr, quote):
                assert isinstance(context.get("annotation"), quote)
            return expr

        result = visit_collection(foo, visit, context={}, return_data=True)
        assert result == quote([1, 2, [3]])

    def test_visit_collection_remove_annotations(self):
        foo = quote([1, 2, quote([3])])

        def visit(expr, context):
            if isinstance(expr, int):
                return expr + 1
            return expr

        result = visit_collection(
            foo, visit, context={}, return_data=True, remove_annotations=True
        )
        assert result == [2, 3, [4]]

    def test_visit_collection_stop_visiting(self):
        foo = [1, 2, quote([3, [4, 5, 6]])]

        def visit(expr, context):
            if isinstance(context.get("annotation"), quote):
                raise StopVisiting()

            if isinstance(expr, int):
                return expr + 1
            else:
                return expr

        result = visit_collection(
            foo, visit, context={}, return_data=True, remove_annotations=True
        )
        # Only the first two items should be visited
        assert result == [2, 3, [3, [4, 5, 6]]]

    @pytest.mark.parametrize(
        "val",
        [
            1,
            [1, 2, 3],
            SimplePydantic(x=1, y=2),
            {"x": 1},
        ],
    )
    def test_visit_collection_simple_identity(self, val):
        """test that visit collection does not modify an object at all in the identity case"""
        result = visit_collection(val, lambda x: x, return_data=True)
        # same object, unmodified
        assert result is val

    def test_visit_collection_only_modify_changed_objects_1(self):
        val = [[1, 2], [3, 5]]
        result = visit_collection(val, negative_even_numbers, return_data=True)
        assert result == [[1, -2], [3, 5]]
        assert result is not val
        assert result[0] is not val[0]
        assert result[1] is val[1]

    def test_visit_collection_only_modify_changed_objects_2(self):
        val = [[[1], {2: 3}], [3, 5]]
        result = visit_collection(val, negative_even_numbers, return_data=True)
        assert result == [[[1], {-2: 3}], [3, 5]]
        assert result[0] is not val[0]
        assert result[0][0] is val[0][0]
        assert result[0][1] is not val[0][1]
        assert result[1] is val[1]

    def test_visit_collection_only_modify_changed_objects_3(self):
        class Foo(pydantic.BaseModel):
            x: list
            y: dict

        val = Foo(x=[[1, 2], [3, 5]], y=dict(a=dict(b=1, c=2), d=dict(e=3, f=5)))
        result: Foo = visit_collection(val, negative_even_numbers, return_data=True)
        assert result is not val
        assert result.x[0] is not val.x[0]
        assert result.x[1] is val.x[1]
        assert result.y["a"] is not val.y["a"]
        assert result.y["d"] is val.y["d"]

    def test_visit_collection_respects_lazy_evaluation(self):
        """Test that visit_collection does not trigger lazy evaluation in Pydantic models

        This is a regression test for https://github.com/PrefectHQ/prefect/issues/17631
        """

        class Lazy(pydantic.BaseModel):
            key: str
            _evaluated: bool = pydantic.PrivateAttr(default=False)

            def data(self):
                self._evaluated = True
                return np.random.randn(2, 2)

        class Data(pydantic.BaseModel):
            data: Lazy

            def __getattribute__(self, item: str) -> Any:
                if item == "data":
                    # Get the raw Lazy object
                    lazy = super().__getattribute__("data")
                    # But return its evaluated data
                    return lazy.data()
                return super().__getattribute__(item)

        lazy = Lazy(key="test")
        container = Data(data=lazy)

        # Before visitation, data should not be evaluated
        assert not lazy._evaluated  # type: ignore

        # Visit the container - this should not trigger evaluation
        visit_collection(container, lambda x: x, return_data=True)

        # After visitation, data should still not be evaluated
        assert not lazy._evaluated  # type: ignore

    def test_visit_collection_shared_references(self):
        """Test that shared references are transformed consistently"""

        def _visitor(x: int):
            if x == 0:
                return 2
            return x

        # Create a structure with shared references
        shared_list = [0, 1, 0, 1]
        result = visit_collection(
            {"a": shared_list, "b": shared_list}, _visitor, return_data=True
        )

        # Both 'a' and 'b' should have the transformed list
        assert result == {"a": [2, 1, 2, 1], "b": [2, 1, 2, 1]}

        # And they should point to the same object
        assert result["a"] is result["b"]

    def test_visit_collection_shared_dict_references(self):
        """Test that shared dict references are transformed consistently"""

        def _visitor(x: int):
            if x == 0:
                return 2
            return x

        shared_dict = {"x": 0, "y": 1}
        result = visit_collection(
            {"first": shared_dict, "second": shared_dict}, _visitor, return_data=True
        )

        # Both should be transformed
        assert result == {"first": {"x": 2, "y": 1}, "second": {"x": 2, "y": 1}}

        # And they should be the same object
        assert result["first"] is result["second"]

    def test_visit_collection_deeply_nested_shared_references(self):
        """Test deeply nested structures with shared references"""

        def _visitor(x):
            if isinstance(x, int) and x % 2 == 0:
                return x * 10
            return x

        shared_list = [2, 3, 4]
        unique_list = [5, 6, 7]

        data = {
            "level1": {
                "shared": shared_list,
                "unique": unique_list,
                "level2": {"also_shared": shared_list, "also_unique": unique_list},
            },
            "another_ref": shared_list,
        }

        result = visit_collection(data, _visitor, return_data=True)

        # Check all shared references point to the same transformed object
        assert result["level1"]["shared"] == [20, 3, 40]
        assert result["level1"]["shared"] is result["level1"]["level2"]["also_shared"]
        assert result["level1"]["shared"] is result["another_ref"]

        # Check unique references are transformed but remain separate
        assert result["level1"]["unique"] == [5, 60, 7]
        assert result["level1"]["unique"] is result["level1"]["level2"]["also_unique"]

    def test_visit_collection_circular_references(self):
        """Test that circular references are handled without infinite recursion"""

        def _visitor(x: int):
            if x == 1:
                return 2
            return x

        # Create a circular reference
        circular = {"a": 1}
        circular["self"] = circular

        # This should not raise RecursionError
        result = visit_collection(circular, _visitor, return_data=True)

        # The top-level value should be transformed
        assert result["a"] == 2

        # The circular reference is preserved (though not with perfect identity)
        assert "self" in result
        assert "self" in result["self"]


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


class TestGetFromDict:
    @pytest.mark.parametrize(
        "dct, keys, expected, default",
        [
            ({}, "a.b.c", None, None),
            ({"a": {"b": {"c": [1, 2, 3, 4]}}}, "a.b.c[1]", 2, None),
            ({"a": {"b": {"c": [1, 2, 3, 4]}}}, "a.b.c.1", 2, None),
            ({"a": {"b": [0, {"c": [1, 2]}]}}, "a.b.1.c.1", 2, None),
            ({"a": {"b": [0, {"c": [1, 2]}]}}, ["a", "b", 1, "c", 1], 2, None),
            ({"a": {"b": [0, {"c": [1, 2]}]}}, "a.b.1.c.2", None, None),
            (
                {"a": {"b": [0, {"c": [1, 2]}]}},
                "a.b.1.c.2",
                "default_value",
                "default_value",
            ),
        ],
    )
    def test_get_from_dict(self, dct, keys, expected, default):
        assert get_from_dict(dct, keys, default) == expected


class TestSetInDict:
    @pytest.mark.parametrize(
        "dct, keys, value, expected",
        [
            ({}, "a.b.c", 1, {"a": {"b": {"c": 1}}}),
            ({"a": {"b": {"c": 1}}}, "a.b.c", 2, {"a": {"b": {"c": 2}}}),
            ({"a": {"b": {"c": 1}}}, "a.b.d", 2, {"a": {"b": {"c": 1, "d": 2}}}),
            ({"a": {"b": {"c": 1}}}, "a", 2, {"a": 2}),
            (
                {"a": {"b": {"c": 1}}},
                ["a", "b", "d"],
                2,
                {"a": {"b": {"c": 1, "d": 2}}},
            ),
        ],
    )
    def test_set_in_dict(self, dct, keys, value, expected):
        set_in_dict(dct, keys, value)
        assert dct == expected

    def test_set_in_dict_raises_key_error(self):
        with pytest.raises(
            TypeError, match="Key path exists and contains a non-dict value"
        ):
            set_in_dict({"a": {"b": [2]}}, ["a", "b", "c"], 1)


class TestDeepMerge:
    @pytest.mark.parametrize(
        "dct, merge, expected",
        [
            ({"a": 1}, {"b": 2}, {"a": 1, "b": 2}),
            ({"a": 1}, {"a": 2}, {"a": 2}),
            ({"a": {"b": 1}}, {"a": {"c": 2}}, {"a": {"b": 1, "c": 2}}),
            ({"a": {"b": 2}}, {"a": {"c": {"d": 1}}}, {"a": {"b": 2, "c": {"d": 1}}}),
        ],
    )
    def test_deep_merge(self, dct, merge, expected):
        assert deep_merge(dct, merge) == expected


class TestDeepMergeDicts:
    @pytest.mark.parametrize(
        "dicts, expected",
        [
            (
                [{"a": 1}, {"b": 2}],
                {"a": 1, "b": 2},
            ),
            (
                [{"a": 1}, {"a": 2}],
                {"a": 2},
            ),
            (
                [{"a": {"b": 1}}, {"a": {"c": 2}}],
                {"a": {"b": 1, "c": 2}},
            ),
            (
                [{"a": {"b": 2}}, {"a": {"c": {"d": 1}}}],
                {"a": {"b": 2, "c": {"d": 1}}},
            ),
            (
                [{"a": {"b": 2}}, {"a": {"c": {"d": 1}}}, {"a": {"c": {"d": 3}}}],
                {"a": {"b": 2, "c": {"d": 3}}},
            ),
        ],
    )
    def test_deep_merge_dicts(self, dicts, expected):
        assert deep_merge_dicts(*dicts) == expected
