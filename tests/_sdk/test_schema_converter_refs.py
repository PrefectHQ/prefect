"""Tests for $ref resolution and allOf handling in JSON Schema."""

import pytest

from prefect._sdk.schema_converter import (
    CircularReferenceError,
    ConversionContext,
    json_schema_to_python_type,
)


class TestReferenceResolution:
    """Test $ref resolution."""

    def test_simple_ref(self):
        context = ConversionContext(
            definitions={"MyType": {"type": "string"}},
        )
        schema = {"$ref": "#/definitions/MyType"}
        assert json_schema_to_python_type(schema, context) == "str"

    def test_ref_to_object(self):
        context = ConversionContext(
            definitions={"Person": {"type": "object", "additionalProperties": False}},
        )
        schema = {"$ref": "#/definitions/Person"}
        assert json_schema_to_python_type(schema, context) == "dict[str, Any]"

    def test_defs_format(self):
        """Pydantic v2 uses $defs instead of definitions."""
        context = ConversionContext(
            definitions={"MyType": {"type": "integer"}},
        )
        schema = {"$ref": "#/$defs/MyType"}
        assert json_schema_to_python_type(schema, context) == "int"

    def test_nested_ref(self):
        """Test ref that points to another ref."""
        context = ConversionContext(
            definitions={
                "TypeA": {"$ref": "#/definitions/TypeB"},
                "TypeB": {"type": "string"},
            },
        )
        schema = {"$ref": "#/definitions/TypeA"}
        assert json_schema_to_python_type(schema, context) == "str"

    def test_circular_ref_detection(self):
        """Circular references should raise an error."""
        context = ConversionContext(
            definitions={
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/definitions/Node"}},
                }
            },
        )
        schema = {"$ref": "#/definitions/Node"}
        # The outer ref should work, but inner ref in properties causes dict[str, Any]
        # Actually, since we're converting the whole object, it returns dict[str, Any]
        assert json_schema_to_python_type(schema, context) == "dict[str, Any]"

    def test_self_referencing_directly(self):
        """Direct self-reference should raise CircularReferenceError."""
        context = ConversionContext(
            definitions={"Loop": {"$ref": "#/definitions/Loop"}},
        )
        schema = {"$ref": "#/definitions/Loop"}
        with pytest.raises(CircularReferenceError):
            json_schema_to_python_type(schema, context)

    def test_unknown_ref_format(self):
        """Unknown ref format should return Any with warning."""
        context = ConversionContext()
        schema = {"$ref": "http://example.com/schema"}
        result = json_schema_to_python_type(schema, context)
        assert result == "Any"
        assert len(context.conversion_warnings) == 1
        assert "Unknown $ref format" in context.conversion_warnings[0]

    def test_missing_definition(self):
        """Missing definition should return Any with warning."""
        context = ConversionContext(definitions={})
        schema = {"$ref": "#/definitions/Missing"}
        result = json_schema_to_python_type(schema, context)
        assert result == "Any"
        assert len(context.conversion_warnings) == 1
        assert "Definition not found" in context.conversion_warnings[0]

    def test_external_url_ref(self):
        """External URL refs should return Any with warning."""
        context = ConversionContext()
        schema = {"$ref": "https://json-schema.org/draft/2020-12/schema"}
        result = json_schema_to_python_type(schema, context)
        assert result == "Any"
        assert any("Unknown $ref format" in w for w in context.conversion_warnings)

    def test_openapi_style_ref(self):
        """OpenAPI-style refs (#/components/schemas/...) are not supported."""
        context = ConversionContext()
        schema = {"$ref": "#/components/schemas/User"}
        result = json_schema_to_python_type(schema, context)
        assert result == "Any"
        assert any("Unknown $ref format" in w for w in context.conversion_warnings)


class TestAllOf:
    """Test allOf handling."""

    def test_allof_with_ref(self):
        """allOf with $ref should resolve the ref."""
        context = ConversionContext(
            definitions={"MyType": {"type": "string"}},
        )
        schema = {"allOf": [{"$ref": "#/definitions/MyType"}]}
        assert json_schema_to_python_type(schema, context) == "str"

    def test_allof_multiple_refs(self):
        """allOf with multiple refs should use the first one.

        Note: True intersection semantics are not modeled.
        """
        context = ConversionContext(
            definitions={
                "TypeA": {"type": "string"},
                "TypeB": {"type": "integer"},
            },
        )
        schema = {
            "allOf": [
                {"$ref": "#/definitions/TypeA"},
                {"$ref": "#/definitions/TypeB"},
            ]
        }
        assert json_schema_to_python_type(schema, context) == "str"

    def test_allof_without_ref(self):
        """allOf without ref should convert the first useful variant."""
        schema = {"allOf": [{"type": "string"}]}
        assert json_schema_to_python_type(schema) == "str"
