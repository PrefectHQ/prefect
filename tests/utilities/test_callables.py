import datetime
from enum import Enum
from typing import Any, Dict, List, Tuple, Union

import pendulum
import pydantic.version
import pytest
from packaging.version import Version

from prefect.exceptions import ParameterBindError
from prefect.utilities import callables


class TestFunctionToSchema:
    def test_simple_function_with_no_arguments(self):
        def f():
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "properties": {},
            "title": "Parameters",
            "type": "object",
        }

    def test_function_with_pydantic_base_model_collisions(self):
        def f(
            json,
            copy,
            parse_obj,
            parse_raw,
            parse_file,
            from_orm,
            schema,
            schema_json,
            construct,
            validate,
            foo,
        ):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "foo": {"title": "foo", "position": 10},
                "json": {"title": "json", "position": 0},
                "copy": {"title": "copy", "position": 1},
                "parse_obj": {"title": "parse_obj", "position": 2},
                "parse_raw": {"title": "parse_raw", "position": 3},
                "parse_file": {"title": "parse_file", "position": 4},
                "from_orm": {"title": "from_orm", "position": 5},
                "schema": {"title": "schema", "position": 6},
                "schema_json": {"title": "schema_json", "position": 7},
                "construct": {"title": "construct", "position": 8},
                "validate": {"title": "validate", "position": 9},
            },
            "required": [
                "json",
                "copy",
                "parse_obj",
                "parse_raw",
                "parse_file",
                "from_orm",
                "schema",
                "schema_json",
                "construct",
                "validate",
                "foo",
            ],
        }

    def test_function_with_one_required_argument(self):
        def f(x):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "position": 0}},
            "required": ["x"],
        }

    def test_function_with_one_optional_argument(self):
        def f(x=42):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "default": 42, "position": 0}},
        }

    def test_function_with_one_optional_annotated_argument(self):
        def f(x: int = 42):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {"title": "x", "default": 42, "type": "integer", "position": 0}
            },
        }

    def test_function_with_two_arguments(self):
        def f(x: int, y: float = 5.0):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {"title": "x", "type": "integer", "position": 0},
                "y": {"title": "y", "default": 5.0, "type": "number", "position": 1},
            },
            "required": ["x"],
        }

    def test_function_with_datetime_arguments(self):
        def f(
            x: datetime.datetime,
            y: pendulum.DateTime = pendulum.datetime(2025, 1, 1),
            z: datetime.timedelta = datetime.timedelta(seconds=5),
        ):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {
                    "title": "x",
                    "type": "string",
                    "format": "date-time",
                    "position": 0,
                },
                "y": {
                    "title": "y",
                    "default": "2025-01-01T00:00:00+00:00",
                    "type": "string",
                    "format": "date-time",
                    "position": 1,
                },
                "z": {
                    "title": "z",
                    "default": 5.0,
                    "type": "number",
                    "format": "time-delta",
                    "position": 2,
                },
            },
            "required": ["x"],
        }

    def test_function_with_enum_argument(self):
        class Color(Enum):
            RED = "RED"
            GREEN = "GREEN"
            BLUE = "BLUE"

        def f(x: Color = "RED"):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {
                    "title": "x",
                    "default": "RED",
                    "allOf": [{"$ref": "#/definitions/Color"}],
                    "position": 0,
                }
            },
            "definitions": {
                "Color": {
                    "title": "Color",
                    "description": "An enumeration.",
                    "enum": ["RED", "GREEN", "BLUE"],
                }
            },
        }

    def test_function_with_generic_arguments(self):
        def f(
            a: List[str],
            b: Dict[str, Any],
            c: Any,
            d: Tuple[int, float],
            e: Union[str, bytes, int],
        ):
            pass

        # pydantic 1.9.0 adds min and max item counts to the parameter schema
        min_max_items = (
            {
                "minItems": 2,
                "maxItems": 2,
            }
            if Version(pydantic.version.VERSION) >= Version("1.9.0")
            else {}
        )

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "a": {
                    "title": "a",
                    "type": "array",
                    "items": {"type": "string"},
                    "position": 0,
                },
                "b": {"title": "b", "type": "object", "position": 1},
                "c": {"title": "c", "position": 2},
                "d": {
                    "title": "d",
                    "type": "array",
                    "items": [{"type": "integer"}, {"type": "number"}],
                    **min_max_items,
                    "position": 3,
                },
                "e": {
                    "title": "e",
                    "anyOf": [
                        {"type": "string"},
                        {"type": "string", "format": "binary"},
                        {"type": "integer"},
                    ],
                    "position": 4,
                },
            },
            "required": ["a", "b", "c", "d", "e"],
        }

    def test_function_with_user_defined_type(self):
        class Foo:
            y: int

        def f(x: Foo):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "position": 0}},
            "required": ["x"],
        }

    def test_function_with_user_defined_pydantic_model(self):
        class Foo(pydantic.BaseModel):
            y: int
            z: str

        def f(x: Foo):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "definitions": {
                "Foo": {
                    "properties": {
                        "y": {"title": "Y", "type": "integer"},
                        "z": {"title": "Z", "type": "string"},
                    },
                    "required": ["y", "z"],
                    "title": "Foo",
                    "type": "object",
                }
            },
            "properties": {
                "x": {
                    "allOf": [{"$ref": "#/definitions/Foo"}],
                    "title": "x",
                    "position": 0,
                }
            },
            "required": ["x"],
            "title": "Parameters",
            "type": "object",
        }


class TestMethodToSchema:
    def test_methods_with_no_arguments(self):
        class Foo:
            def f(self):
                pass

            @classmethod
            def g(cls):
                pass

            @staticmethod
            def h():
                pass

        for method in [Foo().f, Foo.g, Foo.h]:
            schema = callables.parameter_schema(method)
            assert schema.dict() == {
                "properties": {},
                "title": "Parameters",
                "type": "object",
            }

    def test_methods_with_enum_arguments(self):
        class Color(Enum):
            RED = "RED"
            GREEN = "GREEN"
            BLUE = "BLUE"

        class Foo:
            def f(self, color: Color = "RED"):
                pass

            @classmethod
            def g(cls, color: Color = "RED"):
                pass

            @staticmethod
            def h(color: Color = "RED"):
                pass

        for method in [Foo().f, Foo.g, Foo.h]:
            schema = callables.parameter_schema(method)
            assert schema.dict() == {
                "title": "Parameters",
                "type": "object",
                "properties": {
                    "color": {
                        "title": "color",
                        "default": "RED",
                        "allOf": [{"$ref": "#/definitions/Color"}],
                        "position": 0,
                    }
                },
                "definitions": {
                    "Color": {
                        "title": "Color",
                        "description": "An enumeration.",
                        "enum": ["RED", "GREEN", "BLUE"],
                    }
                },
            }

    def test_methods_with_complex_arguments(self):
        class Foo:
            def f(self, x: datetime.datetime, y: int = 42, z: bool = None):
                pass

            @classmethod
            def g(cls, x: datetime.datetime, y: int = 42, z: bool = None):
                pass

            @staticmethod
            def h(x: datetime.datetime, y: int = 42, z: bool = None):
                pass

        for method in [Foo().f, Foo.g, Foo.h]:
            schema = callables.parameter_schema(method)
            assert schema.dict() == {
                "title": "Parameters",
                "type": "object",
                "properties": {
                    "x": {
                        "title": "x",
                        "type": "string",
                        "format": "date-time",
                        "position": 0,
                    },
                    "y": {
                        "title": "y",
                        "default": 42,
                        "type": "integer",
                        "position": 1,
                    },
                    "z": {"title": "z", "type": "boolean", "position": 2},
                },
                "required": ["x"],
            }


class TestParseFlowDescriptionToSchema:
    def test_flow_with_args_docstring(self):
        def f(x):
            """Function f.

            Args:
                x: required argument x
            """

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {"title": "x", "description": "required argument x", "position": 0}
            },
            "required": ["x"],
        }

    def test_flow_without_docstring(self):
        def f(x):
            pass

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "position": 0}},
            "required": ["x"],
        }

    def test_flow_without_args_docstring(self):
        def f(x):
            """Function f."""

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "position": 0}},
            "required": ["x"],
        }

    def test_flow_with_complex_args_docstring(self):
        def f(x, y):
            """Function f.

            Second line of docstring.

            Args:
                x: required argument x
                y (str): required typed argument y
                  with second line

            Returns:
                None: nothing
            """

        schema = callables.parameter_schema(f)
        assert schema.dict() == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {
                    "title": "x",
                    "description": "required argument x",
                    "position": 0,
                },
                "y": {
                    "title": "y",
                    "description": "required typed argument y\nwith second line",
                    "position": 1,
                },
            },
            "required": ["x", "y"],
        }


class TestGetCallParameters:
    def test_raises_parameter_bind_with_no_kwargs(self):
        def dog(x):
            pass

        with pytest.raises(ParameterBindError):
            callables.get_call_parameters(dog, call_args=(), call_kwargs={})

    def test_raises_parameter_bind_with_wrong_kwargs_same_number(self):
        def dog(x, y):
            pass

        with pytest.raises(ParameterBindError):
            callables.get_call_parameters(
                dog, call_args=(), call_kwargs={"x": 2, "a": 42}
            )

    def test_raises_parameter_bind_with_missing_kwargs(self):
        def dog(x, y):
            pass

        with pytest.raises(ParameterBindError):
            callables.get_call_parameters(dog, call_args=(), call_kwargs={"x": 2})

    def test_raises_parameter_bind_error_with_excess_kwargs(self):
        def dog(x):
            pass

        with pytest.raises(ParameterBindError):
            callables.get_call_parameters(
                dog, call_args=(), call_kwargs={"x": "y", "a": "b"}
            )

    def test_raises_parameter_bind_error_with_excess_kwargs_no_args(self):
        def dog():
            pass

        with pytest.raises(ParameterBindError):
            callables.get_call_parameters(dog, call_args=(), call_kwargs={"x": "y"})
