"""Tests for complex schemas, unknown types, and edge cases."""

from prefect._sdk.schema_converter import (
    ConversionContext,
    json_schema_to_python_type,
)


class TestComplexSchemas:
    """Test complex real-world schema patterns."""

    def test_pydantic_v2_optional_pattern(self):
        """Pydantic v2 optional fields use anyOf."""
        schema = {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "default": None,
        }
        assert json_schema_to_python_type(schema) == "int | None"

    def test_nested_array_of_objects(self):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        }
        assert json_schema_to_python_type(schema) == "list[dict[str, str]]"

    def test_deeply_nested(self):
        schema = {
            "type": "array",
            "items": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
        assert json_schema_to_python_type(schema) == "list[list[list[str]]]"

    def test_union_of_arrays(self):
        schema = {
            "anyOf": [
                {"type": "array", "items": {"type": "string"}},
                {"type": "array", "items": {"type": "integer"}},
            ]
        }
        assert json_schema_to_python_type(schema) == "list[str] | list[int]"


class TestUnknownTypes:
    """Test handling of unknown or unsupported types."""

    def test_unknown_type(self):
        """Unknown type values should return Any."""
        context = ConversionContext()
        schema = {"type": "unknowntype"}
        result = json_schema_to_python_type(schema, context)
        assert result == "Any"
        assert len(context.conversion_warnings) == 1
        assert "Unknown type" in context.conversion_warnings[0]

    def test_unsupported_enum_value(self):
        """Unsupported enum value types should return Any."""
        schema = {"enum": [{"complex": "object"}]}
        assert json_schema_to_python_type(schema) == "Any"


class TestEdgeCases:
    """Test edge cases for improved coverage."""

    def test_allof_all_any_types(self):
        """allOf where all variants return Any should return Any."""
        schema = {"allOf": [{}, {}]}  # Empty schemas return Any
        assert json_schema_to_python_type(schema) == "Any"

    def test_array_with_prefixitems_converted_to_tuple(self):
        """Array with prefixItems should be converted to tuple."""
        schema = {"type": "array", "prefixItems": [{"type": "string"}]}
        assert json_schema_to_python_type(schema) == "tuple[str]"

    def test_object_with_non_standard_additional_properties(self):
        """Object with unusual additionalProperties value."""
        # additionalProperties as a non-dict, non-bool value
        # In practice this shouldn't happen, but test the fallback
        schema = {"type": "object", "additionalProperties": "invalid"}
        assert json_schema_to_python_type(schema) == "dict[str, Any]"
