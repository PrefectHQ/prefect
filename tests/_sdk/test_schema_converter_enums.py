"""Tests for enum and tuple type conversion in JSON Schema."""

from prefect._sdk.schema_converter import json_schema_to_python_type


class TestEnumTypes:
    """Test conversion of enum types to Literal."""

    def test_string_enum(self):
        schema = {"enum": ["A", "B", "C"], "type": "string"}
        assert json_schema_to_python_type(schema) == "Literal['A', 'B', 'C']"

    def test_integer_enum(self):
        schema = {"enum": [1, 2, 3], "type": "integer"}
        assert json_schema_to_python_type(schema) == "Literal[1, 2, 3]"

    def test_boolean_enum(self):
        schema = {"enum": [True, False]}
        assert json_schema_to_python_type(schema) == "Literal[True, False]"

    def test_mixed_enum(self):
        schema = {"enum": ["a", 1, True]}
        assert json_schema_to_python_type(schema) == "Literal['a', 1, True]"

    def test_enum_with_null(self):
        schema = {"enum": ["A", "B", None]}
        assert json_schema_to_python_type(schema) == "Literal['A', 'B', None]"

    def test_empty_enum(self):
        schema = {"enum": []}
        assert json_schema_to_python_type(schema) == "Any"

    def test_string_with_quotes(self):
        """Strings containing quotes should be properly escaped using repr()."""
        schema = {"enum": ['say "hello"', "it's"]}
        # repr() uses single quotes by default for strings
        result = json_schema_to_python_type(schema)
        assert result == """Literal['say "hello"', "it's"]"""

    def test_const(self):
        """const is treated as a single-value enum."""
        schema = {"const": "fixed_value"}
        assert json_schema_to_python_type(schema) == "Literal['fixed_value']"

    def test_float_enum(self):
        """Float enum values should be supported."""
        schema = {"enum": [1.5, 2.5, 3.0]}
        assert json_schema_to_python_type(schema) == "Literal[1.5, 2.5, 3.0]"

    def test_mixed_numeric_enum(self):
        """Mixed int and float enums should work."""
        schema = {"enum": [1, 2.5, 3]}
        assert json_schema_to_python_type(schema) == "Literal[1, 2.5, 3]"

    def test_string_with_control_characters(self):
        """Strings with control characters should be properly escaped."""
        schema = {"enum": ["line1\nline2", "tab\there", "back\\slash"]}
        result = json_schema_to_python_type(schema)
        # repr() properly escapes these
        assert result == r"Literal['line1\nline2', 'tab\there', 'back\\slash']"

    def test_string_with_unicode(self):
        """Unicode strings should be preserved."""
        schema = {"enum": ["café", "日本語", "emoji: 🎉"]}
        result = json_schema_to_python_type(schema)
        assert result == "Literal['café', '日本語', 'emoji: 🎉']"


class TestTupleTypes:
    """Test conversion of tuple types (prefixItems)."""

    def test_single_element_tuple(self):
        schema = {"type": "array", "prefixItems": [{"type": "string"}]}
        assert json_schema_to_python_type(schema) == "tuple[str]"

    def test_two_element_tuple(self):
        schema = {
            "type": "array",
            "prefixItems": [{"type": "string"}, {"type": "integer"}],
        }
        assert json_schema_to_python_type(schema) == "tuple[str, int]"

    def test_multi_element_tuple(self):
        schema = {
            "type": "array",
            "prefixItems": [
                {"type": "string"},
                {"type": "integer"},
                {"type": "boolean"},
            ],
        }
        assert json_schema_to_python_type(schema) == "tuple[str, int, bool]"

    def test_empty_tuple(self):
        schema = {"type": "array", "prefixItems": []}
        assert json_schema_to_python_type(schema) == "tuple[()]"

    def test_pydantic_v1_tuple_format(self):
        """Pydantic v1 uses 'items' as array for tuples."""
        schema = {
            "type": "array",
            "items": [{"type": "string"}, {"type": "integer"}],
            "minItems": 2,
            "maxItems": 2,
        }
        assert json_schema_to_python_type(schema) == "tuple[str, int]"
