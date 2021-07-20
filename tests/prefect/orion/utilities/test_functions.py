import datetime
import pendulum
from enum import Enum
import json
from prefect.orion.utilities import functions
from typing import List, Dict, Any, Tuple, Union


class TestFunctionToSchema:
    def test_simple_function_with_no_arguments(self):
        def f():
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "properties": {},
            "title": "Inputs",
            "type": "object",
        }

    def test_function_with_one_required_argument(self):
        def f(x):
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
            "type": "object",
            "properties": {"x": {"title": "x"}},
            "required": ["x"],
        }

    def test_function_with_one_optional_argument(self):
        def f(x=42):
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
            "type": "object",
            "properties": {"x": {"title": "x", "default": 42}},
        }

    def test_function_with_one_optional_annotated_argument(self):
        def f(x: int = 42):
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
            "type": "object",
            "properties": {"x": {"title": "x", "default": 42, "type": "integer"}},
        }

    def test_function_with_two_arguments(self):
        def f(x: int, y: float = 5.0):
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
            "type": "object",
            "properties": {
                "x": {"title": "x", "type": "integer"},
                "y": {"title": "y", "default": 5.0, "type": "number"},
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

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
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

    def test_function_with_enum_argument(self):
        class Color(Enum):
            RED = "RED"
            GREEN = "GREEN"
            BLUE = "BLUE"

        def f(x: Enum = "RED"):
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
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

    def test_function_with_generic_arguments(self):
        def f(
            a: List[str],
            b: Dict[str, Any],
            c: Any,
            d: Tuple[int, float],
            e: Union[str, bytes, int],
        ):
            pass

        schema = functions.input_schema(f)
        assert schema == {
            "title": "Inputs",
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
