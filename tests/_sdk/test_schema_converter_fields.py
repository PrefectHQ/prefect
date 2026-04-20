"""Tests for extracting field information from JSON Schema."""

from prefect._sdk.schema_converter import extract_fields_from_schema


class TestExtractFieldsFromSchema:
    """Test extracting field information from schemas."""

    def test_simple_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        fields, warnings = extract_fields_from_schema(schema)
        assert len(fields) == 2
        assert len(warnings) == 0

        name_field = next(f for f in fields if f.name == "name")
        assert name_field.python_type == "str"
        assert name_field.required is True

        age_field = next(f for f in fields if f.name == "age")
        assert age_field.python_type == "int"
        assert age_field.required is False

    def test_field_with_default_not_required(self):
        """Field in required list but with default should be optional."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 0},
            },
            "required": ["count"],
        }
        fields, _ = extract_fields_from_schema(schema)
        assert len(fields) == 1
        assert fields[0].name == "count"
        assert fields[0].required is False  # Has default, so not required
        assert fields[0].has_default is True
        assert fields[0].default == 0

    def test_field_descriptions(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The user's name"},
                "age": {"type": "integer", "title": "User Age"},
            },
        }
        fields, _ = extract_fields_from_schema(schema)

        name_field = next(f for f in fields if f.name == "name")
        assert name_field.description == "The user's name"

        age_field = next(f for f in fields if f.name == "age")
        assert age_field.description == "User Age"  # Falls back to title

    def test_with_definitions(self):
        """Fields can reference definitions."""
        schema = {
            "type": "object",
            "properties": {
                "user": {"$ref": "#/definitions/User"},
            },
            "definitions": {
                "User": {"type": "object", "additionalProperties": False},
            },
        }
        fields, _ = extract_fields_from_schema(schema)
        assert len(fields) == 1
        assert fields[0].python_type == "dict[str, Any]"

    def test_with_defs(self):
        """Fields can reference $defs (Pydantic v2 format)."""
        schema = {
            "type": "object",
            "properties": {
                "user": {"$ref": "#/$defs/User"},
            },
            "$defs": {
                "User": {"type": "object"},
            },
        }
        fields, _ = extract_fields_from_schema(schema)
        assert len(fields) == 1
        assert fields[0].python_type == "dict[str, Any]"

    def test_circular_reference_in_field(self):
        """Circular references in fields should be handled gracefully."""
        schema = {
            "type": "object",
            "properties": {
                "node": {"$ref": "#/definitions/Node"},
            },
            "definitions": {
                "Node": {"$ref": "#/definitions/Node"},
            },
        }
        fields, warnings = extract_fields_from_schema(schema)
        assert len(fields) == 1
        assert fields[0].python_type == "Any"  # Circular ref fallback
        assert any("Circular" in w for w in warnings)

    def test_empty_properties(self):
        schema = {"type": "object", "properties": {}}
        fields, warnings = extract_fields_from_schema(schema)
        assert len(fields) == 0
        assert len(warnings) == 0

    def test_no_properties(self):
        schema = {"type": "object"}
        fields, warnings = extract_fields_from_schema(schema)
        assert len(fields) == 0
        assert len(warnings) == 0
