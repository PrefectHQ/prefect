"""Tests for the pure Pydantic v2 validated function implementation."""

from unittest.mock import patch

import pytest
from pydantic import BaseModel, ValidationError

from prefect._internal.pydantic.validated_func import ValidatedFunction


class TestBasicValidation:
    """Test basic function argument validation."""

    def test_simple_function(self):
        def greet(name: str, age: int = 0):
            return f"Hello {name}, you are {age} years old"

        vf = ValidatedFunction(greet)
        result = vf.validate_call_args(("Alice",), {"age": 30})

        assert result == {"name": "Alice", "age": 30}

    def test_simple_function_with_defaults(self):
        def greet(name: str, age: int = 25):
            return f"Hello {name}"

        vf = ValidatedFunction(greet)
        result = vf.validate_call_args(("Bob",), {})

        assert result == {"name": "Bob", "age": 25}

    def test_all_positional(self):
        def add(a: int, b: int):
            return a + b

        vf = ValidatedFunction(add)
        result = vf.validate_call_args((5, 10), {})

        assert result == {"a": 5, "b": 10}

    def test_all_keyword(self):
        def add(a: int, b: int):
            return a + b

        vf = ValidatedFunction(add)
        result = vf.validate_call_args((), {"a": 5, "b": 10})

        assert result == {"a": 5, "b": 10}

    def test_mixed_positional_and_keyword(self):
        def multiply(x: int, y: int, z: int = 1):
            return x * y * z

        vf = ValidatedFunction(multiply)
        result = vf.validate_call_args((2, 3), {"z": 4})

        assert result == {"x": 2, "y": 3, "z": 4}


class TestTypeValidation:
    """Test that types are validated correctly."""

    def test_type_coercion(self):
        def add(a: int, b: int):
            return a + b

        vf = ValidatedFunction(add)
        # Pydantic should coerce string to int
        result = vf.validate_call_args(("5", "10"), {})

        assert result == {"a": 5, "b": 10}

    def test_type_validation_error(self):
        def add(a: int, b: int):
            return a + b

        vf = ValidatedFunction(add)

        with pytest.raises(ValidationError) as exc_info:
            vf.validate_call_args(("not a number",), {"b": 10})

        assert "a" in str(exc_info.value)

    def test_pydantic_model_validation(self):
        class Person(BaseModel):
            name: str
            age: int

        def process_person(person: Person):
            return person

        vf = ValidatedFunction(process_person)
        result = vf.validate_call_args(({"name": "Alice", "age": 30},), {})

        assert isinstance(result["person"], Person)
        assert result["person"].name == "Alice"
        assert result["person"].age == 30


class TestVariadicArguments:
    """Test *args and **kwargs handling."""

    def test_var_positional(self):
        def sum_all(*numbers: int):
            return sum(numbers)

        vf = ValidatedFunction(sum_all)
        result = vf.validate_call_args((1, 2, 3, 4, 5), {})

        assert result == {"numbers": [1, 2, 3, 4, 5]}

    def test_var_keyword(self):
        def print_kwargs(**kwargs):
            return kwargs

        vf = ValidatedFunction(print_kwargs)
        result = vf.validate_call_args((), {"a": 1, "b": 2, "c": 3})

        assert result == {"kwargs": {"a": 1, "b": 2, "c": 3}}

    def test_mixed_with_var_positional(self):
        def func(a: int, b: int, *rest):
            return (a, b, rest)

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1, 2, 3, 4, 5), {})

        assert result == {"a": 1, "b": 2, "rest": [3, 4, 5]}

    def test_mixed_with_var_keyword(self):
        def func(a: int, b: int = 0, **kwargs):
            return (a, b, kwargs)

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1,), {"b": 2, "c": 3, "d": 4})

        assert result == {"a": 1, "b": 2, "kwargs": {"c": 3, "d": 4}}

    def test_both_var_args_and_kwargs(self):
        def func(a: int, *args, **kwargs):
            return (a, args, kwargs)

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1, 2, 3), {"x": 10, "y": 20})

        assert result == {"a": 1, "args": [2, 3], "kwargs": {"x": 10, "y": 20}}


class TestPositionalOnly:
    """Test positional-only parameters (Python 3.8+)."""

    def test_positional_only_valid(self):
        def func(a, b, /, c):
            return a + b + c

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1, 2, 3), {})

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_positional_only_with_keyword_for_c(self):
        def func(a, b, /, c):
            return a + b + c

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1, 2), {"c": 3})

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_positional_only_error(self):
        def func(a, b, /, c):
            return a + b + c

        vf = ValidatedFunction(func)

        with pytest.raises(
            TypeError, match="positional-only argument.*passed as keyword"
        ):
            vf.validate_call_args((1,), {"b": 2, "c": 3})


class TestKeywordOnly:
    """Test keyword-only parameters."""

    def test_keyword_only_valid(self):
        def func(a, *, b, c=3):
            return a + b + c

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1,), {"b": 2})

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_keyword_only_all_provided(self):
        def func(a, *, b, c):
            return a + b + c

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((1,), {"b": 2, "c": 3})

        assert result == {"a": 1, "b": 2, "c": 3}


class TestErrorHandling:
    """Test error handling and validation."""

    def test_missing_required_argument(self):
        def func(a: int, b: int):
            return a + b

        vf = ValidatedFunction(func)

        with pytest.raises(ValidationError) as exc_info:
            vf.validate_call_args((1,), {})

        assert "b" in str(exc_info.value)

    def test_too_many_positional_arguments(self):
        def func(a: int, b: int):
            return a + b

        vf = ValidatedFunction(func)

        with pytest.raises(
            TypeError, match="2 positional arguments expected but 3 given"
        ):
            vf.validate_call_args((1, 2, 3), {})

    def test_unexpected_keyword_argument(self):
        def func(a: int, b: int):
            return a + b

        vf = ValidatedFunction(func)

        with pytest.raises(TypeError, match="unexpected keyword argument.*'c'"):
            vf.validate_call_args((1,), {"b": 2, "c": 3})

    def test_duplicate_argument(self):
        def func(a: int, b: int):
            return a + b

        vf = ValidatedFunction(func)

        with pytest.raises(TypeError, match="multiple values for argument.*'a'"):
            vf.validate_call_args((1,), {"a": 2, "b": 3})


class TestCallable:
    """Test using ValidatedFunction as a callable."""

    def test_call_with_validation(self):
        def add(a: int, b: int):
            return a + b

        vf = ValidatedFunction(add)
        result = vf(5, 10)

        assert result == 15

    def test_call_with_keyword_args(self):
        def greet(name: str, greeting: str = "Hello"):
            return f"{greeting}, {name}!"

        vf = ValidatedFunction(greet)
        result = vf("Alice", greeting="Hi")

        assert result == "Hi, Alice!"

    def test_call_with_validation_error(self):
        def add(a: int, b: int):
            return a + b

        vf = ValidatedFunction(add)

        with pytest.raises(ValidationError):
            vf("not a number", 10)


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_function_with_all_parameter_types(self):
        def complex_func(a, b, /, c, d=4, *args, e, f=6, **kwargs):
            return {
                "a": a,
                "b": b,
                "c": c,
                "d": d,
                "args": args,
                "e": e,
                "f": f,
                "kwargs": kwargs,
            }

        vf = ValidatedFunction(complex_func)
        result = vf.validate_call_args(
            (1, 2, 3),  # a, b, c
            {"d": 5, "e": 7, "f": 8, "x": 9, "y": 10},
        )

        assert result == {
            "a": 1,
            "b": 2,
            "c": 3,
            "d": 5,
            "args": [],
            "e": 7,
            "f": 8,
            "kwargs": {"x": 9, "y": 10},
        }

    def test_function_with_no_type_hints(self):
        def add(a, b):
            return a + b

        vf = ValidatedFunction(add)
        result = vf.validate_call_args((1, 2), {})

        assert result == {"a": 1, "b": 2}

    def test_with_custom_config(self):
        def func(a: int):
            return a

        # Pass config as a dict (ConfigDict is a TypedDict and can't use isinstance in Python 3.14)
        config = {"strict": True}
        vf = ValidatedFunction(func, config=config)

        # With strict mode, string won't be coerced to int
        with pytest.raises(ValidationError):
            vf.validate_call_args(("5",), {})


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_no_parameters(self):
        def func():
            return "no params"

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((), {})

        assert result == {}

    def test_only_defaults(self):
        def func(a=1, b=2):
            return a + b

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((), {})

        assert result == {"a": 1, "b": 2}

    def test_empty_var_args(self):
        def func(*args):
            return args

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((), {})

        assert result == {"args": []}

    def test_empty_var_kwargs(self):
        def func(**kwargs):
            return kwargs

        vf = ValidatedFunction(func)
        result = vf.validate_call_args((), {})

        assert result == {"kwargs": {}}

    def test_reserved_parameter_name_v__args(self):
        """Test that using reserved parameter name v__args raises ValueError."""

        def func(v__args):
            return v__args

        with pytest.raises(
            ValueError, match="Function parameters conflict with internal field names"
        ):
            ValidatedFunction(func)

    def test_reserved_parameter_name_v__kwargs(self):
        """Test that using reserved parameter name v__kwargs raises ValueError."""

        def func(v__kwargs):
            return v__kwargs

        with pytest.raises(
            ValueError, match="Function parameters conflict with internal field names"
        ):
            ValidatedFunction(func)

    def test_reserved_parameter_name_v__positional_only(self):
        """Test that using reserved parameter name v__positional_only raises ValueError."""

        def func(v__positional_only):
            return v__positional_only

        with pytest.raises(
            ValueError, match="Function parameters conflict with internal field names"
        ):
            ValidatedFunction(func)

    def test_reserved_parameter_name_v__duplicate_kwargs(self):
        """Test that using reserved parameter name v__duplicate_kwargs raises ValueError."""

        def func(v__duplicate_kwargs):
            return v__duplicate_kwargs

        with pytest.raises(
            ValueError, match="Function parameters conflict with internal field names"
        ):
            ValidatedFunction(func)


class TestForwardReferences:
    """Test handling of forward references and `from __future__ import annotations`."""

    def test_pydantic_model_with_future_annotations(self):
        """Test that Pydantic models work with forward reference annotations.

        This is a regression test for issue #19288.
        When using `from __future__ import annotations`, type hints become strings
        and need to be resolved via model_rebuild() with the proper namespace.
        """
        # Define a test module namespace that simulates using future annotations
        namespace = {}

        # Create a model in that namespace
        exec(
            """
from pydantic import BaseModel, Field

class TestModel(BaseModel):
    name: str = Field(..., description="Test name")
    value: int = 42
""",
            namespace,
        )

        TestModel = namespace["TestModel"]

        # Define a function with the model as a parameter using string annotation
        # This simulates what happens with `from __future__ import annotations`
        def process_model(model: "TestModel") -> dict:  # noqa: F821
            return {"name": model.name, "value": model.value}

        # Update the function's globals to include the TestModel
        process_model.__globals__.update(namespace)

        # Create validated function
        vf = ValidatedFunction(process_model)

        # Create an instance of the model
        test_instance = TestModel(name="test")

        # This should work without raising PydanticUserError about undefined models
        result = vf.validate_call_args((test_instance,), {})

        assert isinstance(result["model"], TestModel)
        assert result["model"].name == "test"
        assert result["model"].value == 42

    def test_nested_pydantic_models_with_forward_refs(self):
        """Test nested Pydantic models with forward references work correctly."""

        class Inner(BaseModel):
            value: int

        class Outer(BaseModel):
            inner: Inner
            name: str

        # Simulate forward reference by using string annotation
        def process_nested(data: "Outer") -> str:  # noqa: F821
            return data.name

        # Add the types to the function's globals
        process_nested.__globals__["Outer"] = Outer
        process_nested.__globals__["Inner"] = Inner

        vf = ValidatedFunction(process_nested)

        # Create nested structure
        outer_instance = Outer(inner=Inner(value=42), name="test")

        result = vf.validate_call_args((outer_instance,), {})

        assert isinstance(result["data"], Outer)
        assert result["data"].name == "test"
        assert result["data"].inner.value == 42

    def test_no_rebuild_without_forward_refs(self):
        """Test that model_rebuild is not called when there are no forward references.

        This is a performance optimization test - we should avoid the overhead
        of model_rebuild() when it's not necessary.
        """

        class MyModel(BaseModel):
            name: str

        # Function with concrete type annotations (no forward refs)
        def process_data(model: MyModel, count: int = 0) -> dict:
            return {"name": model.name, "count": count}

        # Spy on model_rebuild to ensure it's NOT called during initialization
        with patch.object(BaseModel, "model_rebuild") as mock_rebuild:
            vf = ValidatedFunction(process_data)

            # model_rebuild should NOT have been called since there are no forward refs
            mock_rebuild.assert_not_called()

        # The model should work correctly without rebuild
        instance = MyModel(name="test")

        # Also verify model_rebuild is NOT called during validation
        with patch.object(vf.model, "model_rebuild") as mock_rebuild:
            result = vf.validate_call_args((instance,), {"count": 5})

            # model_rebuild should NOT be called during validation either
            mock_rebuild.assert_not_called()

        assert isinstance(result["model"], MyModel)
        assert result["model"].name == "test"
        assert result["count"] == 5

    def test_forward_ref_defined_after_decorator(self):
        """Test that forward references work when type is defined after the function.

        This is a regression test for issue #19447.
        When using `from __future__ import annotations`, the @flow decorator
        was failing if a forward-referenced Pydantic model was defined after
        the function using it.
        """
        # First, define A and the function WITHOUT B defined yet
        namespace = {}
        exec(
            """
from __future__ import annotations
from pydantic import BaseModel, Field

class A(BaseModel):
    a: B = Field()

def process_model(model: A):
    return model
""",
            namespace,
        )

        # At this point, B doesn't exist yet. Creating ValidatedFunction should not fail
        # (it should defer the model rebuild until validation time)
        vf = ValidatedFunction(namespace["process_model"])

        # Now define B in the namespace
        exec(
            """
class B(BaseModel):
    b: str = Field()
""",
            namespace,
        )

        # Update the function's globals to include B
        namespace["process_model"].__globals__.update(namespace)

        # Now test that validation actually works at runtime
        result = vf.validate_call_args((), {"model": {"a": {"b": "test"}}})

        assert result["model"].a.b == "test"
