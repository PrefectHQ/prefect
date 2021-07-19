import datetime
import pendulum
from enum import Enum
import json
from prefect.orion.utilities import parameters
from typing import List, Dict, Any, Tuple, Union


class TestFunctionToSchema:
    def test_simple_function_with_no_parameters(self):
        def f():
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "properties": {},
            "title": "Parameters",
            "type": "object",
        }

    def test_function_with_one_required_parameter(self):
        def f(x):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x"}},
            "required": ["x"],
        }

    def test_function_with_one_optional_parameter(self):
        def f(x=42):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "default": 42}},
        }

    def test_function_with_one_optional_annotated_parameter(self):
        def f(x: int = 42):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {"x": {"title": "x", "default": 42, "type": "integer"}},
        }

    def test_function_with_two_parameters(self):
        def f(x: int, y: float = 5.0):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {"title": "x", "type": "integer"},
                "y": {"title": "y", "default": 5.0, "type": "number"},
            },
            "required": ["x"],
        }

    def test_function_with_datetime_parameters(self):
        def f(
            x: datetime.datetime,
            y: pendulum.DateTime = pendulum.datetime(2025, 1, 1),
            z: datetime.timedelta = datetime.timedelta(seconds=5),
        ):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {"title": "x", "type": "string", "format": "date-time"},
                "y": {
                    "title": "y",
                    "default": "2025-01-01T00:00:00+00:00",
                    "type": "string",
                    "format": "date-time",
                },
                "z": {
                    "title": "z",
                    "default": 5.0,
                    "type": "number",
                    "format": "time-delta",
                },
            },
            "required": ["x"],
        }

    def test_function_with_enum_parameter(self):
        class Color(Enum):
            RED = "RED"
            GREEN = "GREEN"
            BLUE = "BLUE"

        def f(x: Enum = "RED"):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "x": {
                    "title": "x",
                    "default": "RED",
                    "allOf": [{"$ref": "#/definitions/Enum"}],
                }
            },
            "definitions": {
                "Enum": {
                    "title": "Enum",
                    "description": "Generic enumeration.\n\nDerive from this class to define new enumerations.",
                    "enum": [],
                }
            },
        }

    def test_function_with_generic_parameters(self):
        def f(
            a: List[str],
            b: Dict[str, Any],
            c: Any,
            d: Tuple[int, float],
            e: Union[str, bytes, int],
        ):
            pass

        schema = parameters.function_to_parameter_schema(f)
        assert schema == {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "a": {"title": "a", "type": "array", "items": {"type": "string"}},
                "b": {"title": "b", "type": "object"},
                "c": {"title": "c"},
                "d": {
                    "title": "d",
                    "type": "array",
                    "items": [{"type": "integer"}, {"type": "number"}],
                },
                "e": {
                    "title": "e",
                    "anyOf": [
                        {"type": "string"},
                        {"type": "string", "format": "binary"},
                        {"type": "integer"},
                    ],
                },
            },
            "required": ["a", "b", "c", "d", "e"],
        }
