"""Tests for primitive and basic JSON Schema type conversion."""

from prefect._sdk.schema_converter import json_schema_to_python_type


class TestPrimitiveTypes:
    """Test conversion of primitive JSON Schema types."""

    def test_string(self):
        assert json_schema_to_python_type({"type": "string"}) == "str"

    def test_integer(self):
        assert json_schema_to_python_type({"type": "integer"}) == "int"

    def test_number(self):
        assert json_schema_to_python_type({"type": "number"}) == "float"

    def test_boolean(self):
        assert json_schema_to_python_type({"type": "boolean"}) == "bool"

    def test_null(self):
        assert json_schema_to_python_type({"type": "null"}) == "None"


class TestEmptyAndBooleanSchemas:
    """Test handling of empty and boolean schemas."""

    def test_empty_schema(self):
        assert json_schema_to_python_type({}) == "Any"

    def test_boolean_true_schema(self):
        """Boolean true schema accepts anything."""
        assert json_schema_to_python_type(True) == "Any"

    def test_boolean_false_schema(self):
        """Boolean false schema accepts nothing.

        Note: We return "Any" rather than "Never" because false schemas are
        extremely rare in practice, and "Any" is more practical for type checking.
        """
        assert json_schema_to_python_type(False) == "Any"

    def test_no_type_key(self):
        """Schema with no 'type' key should return Any."""
        assert json_schema_to_python_type({"title": "Unknown"}) == "Any"


class TestArrayTypes:
    """Test conversion of array types."""

    def test_array_without_items(self):
        assert json_schema_to_python_type({"type": "array"}) == "list[Any]"

    def test_array_with_string_items(self):
        schema = {"type": "array", "items": {"type": "string"}}
        assert json_schema_to_python_type(schema) == "list[str]"

    def test_array_with_integer_items(self):
        schema = {"type": "array", "items": {"type": "integer"}}
        assert json_schema_to_python_type(schema) == "list[int]"

    def test_array_with_nested_array_items(self):
        schema = {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
        }
        assert json_schema_to_python_type(schema) == "list[list[str]]"

    def test_array_with_object_items(self):
        schema = {"type": "array", "items": {"type": "object"}}
        assert json_schema_to_python_type(schema) == "list[dict[str, Any]]"


class TestObjectTypes:
    """Test conversion of object types."""

    def test_object_without_additional_properties(self):
        schema = {"type": "object"}
        assert json_schema_to_python_type(schema) == "dict[str, Any]"

    def test_object_with_additional_properties_true(self):
        schema = {"type": "object", "additionalProperties": True}
        assert json_schema_to_python_type(schema) == "dict[str, Any]"

    def test_object_with_additional_properties_false(self):
        schema = {"type": "object", "additionalProperties": False}
        assert json_schema_to_python_type(schema) == "dict[str, Any]"

    def test_object_with_typed_additional_properties(self):
        schema = {"type": "object", "additionalProperties": {"type": "string"}}
        assert json_schema_to_python_type(schema) == "dict[str, str]"

    def test_object_with_typed_additional_properties_integer(self):
        schema = {"type": "object", "additionalProperties": {"type": "integer"}}
        assert json_schema_to_python_type(schema) == "dict[str, int]"

    def test_object_with_properties(self):
        """Object with properties but no additionalProperties still returns dict.

        Note: Nested TypedDict generation is handled by the template renderer,
        not this converter.
        """
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        }
        assert json_schema_to_python_type(schema) == "dict[str, Any]"


class TestImplicitTypes:
    """Test schemas that imply types without explicit type field."""

    def test_properties_implies_object(self):
        """Schema with properties but no type implies object."""
        schema = {"properties": {"name": {"type": "string"}}}
        assert json_schema_to_python_type(schema) == "dict[str, Any]"

    def test_items_implies_array(self):
        """Schema with items but no type implies array."""
        schema = {"items": {"type": "string"}}
        assert json_schema_to_python_type(schema) == "list[str]"
