"""Tests for the JSON Schema to Python type converter."""

import pytest

from prefect._sdk.schema_converter import (
    CircularReferenceError,
    ConversionContext,
    _split_union_top_level,
    extract_fields_from_schema,
    json_schema_to_python_type,
)


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


class TestNullableTypes:
    """Test conversion of nullable (anyOf with null) types."""

    def test_nullable_string(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        assert json_schema_to_python_type(schema) == "str | None"

    def test_nullable_integer(self):
        schema = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
        assert json_schema_to_python_type(schema) == "int | None"

    def test_null_first(self):
        """Null can be in any position."""
        schema = {"anyOf": [{"type": "null"}, {"type": "string"}]}
        assert json_schema_to_python_type(schema) == "str | None"

    def test_only_null(self):
        schema = {"anyOf": [{"type": "null"}]}
        assert json_schema_to_python_type(schema) == "None"


class TestUnionTypes:
    """Test conversion of union types (anyOf/oneOf)."""

    def test_string_or_integer(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        assert json_schema_to_python_type(schema) == "str | int"

    def test_multi_type_union(self):
        schema = {
            "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}]
        }
        assert json_schema_to_python_type(schema) == "str | int | bool"

    def test_nullable_union(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]}
        assert json_schema_to_python_type(schema) == "str | int | None"

    def test_one_of(self):
        """oneOf is treated the same as anyOf."""
        schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
        assert json_schema_to_python_type(schema) == "str | int"

    def test_duplicate_types_in_union(self):
        """Duplicate types should be deduplicated."""
        schema = {"anyOf": [{"type": "string"}, {"type": "string"}]}
        assert json_schema_to_python_type(schema) == "str"

    def test_nested_union_flattening(self):
        """Unions containing unions should be flattened and deduplicated."""
        # This simulates anyOf containing a variant that itself is a union
        # e.g., anyOf with str and (str | None)
        schema = {
            "anyOf": [
                {"type": "string"},
                {"anyOf": [{"type": "string"}, {"type": "null"}]},
            ]
        }
        # Should flatten to just "str | None", not "str | str | None"
        assert json_schema_to_python_type(schema) == "str | None"

    def test_nested_union_with_different_types(self):
        """Nested unions with different types should be properly flattened."""
        schema = {
            "anyOf": [
                {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
            ]
        }
        assert json_schema_to_python_type(schema) == "str | int | bool | None"

    def test_deeply_nested_unions(self):
        """Deeply nested unions should all flatten correctly."""
        schema = {
            "anyOf": [
                {"type": "string"},
                {
                    "anyOf": [
                        {"type": "integer"},
                        {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
                    ]
                },
            ]
        }
        assert json_schema_to_python_type(schema) == "str | int | bool | None"


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


class TestTypeArrays:
    """Test type specified as array (e.g., ["string", "null"])."""

    def test_string_or_null(self):
        schema = {"type": ["string", "null"]}
        assert json_schema_to_python_type(schema) == "str | None"

    def test_integer_or_null(self):
        schema = {"type": ["integer", "null"]}
        assert json_schema_to_python_type(schema) == "int | None"

    def test_multi_type(self):
        schema = {"type": ["string", "integer"]}
        assert json_schema_to_python_type(schema) == "str | int"

    def test_only_null(self):
        schema = {"type": ["null"]}
        assert json_schema_to_python_type(schema) == "None"

    def test_duplicate_types_deduplicated(self):
        """Duplicate types in type array should be deduplicated."""
        schema = {"type": ["string", "string", "null"]}
        assert json_schema_to_python_type(schema) == "str | None"

    def test_all_duplicates(self):
        """All duplicate types should result in single type."""
        schema = {"type": ["integer", "integer", "integer"]}
        assert json_schema_to_python_type(schema) == "int"


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


class TestFlattenUnion:
    """Test the union flattening helper behavior."""

    def test_simple_types(self):
        """Simple types should be joined with |."""
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        assert json_schema_to_python_type(schema) == "str | int"

    def test_none_at_end(self):
        """None should always be at the end."""
        # Multiple orderings should all result in None at end
        schema1 = {"anyOf": [{"type": "null"}, {"type": "string"}, {"type": "integer"}]}
        schema2 = {"anyOf": [{"type": "string"}, {"type": "null"}, {"type": "integer"}]}
        schema3 = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]}

        expected = "str | int | None"
        assert json_schema_to_python_type(schema1) == expected
        assert json_schema_to_python_type(schema2) == expected
        assert json_schema_to_python_type(schema3) == expected

    def test_preserves_order_of_non_null_types(self):
        """Non-null types should preserve their order of first appearance."""
        schema = {
            "anyOf": [{"type": "boolean"}, {"type": "string"}, {"type": "integer"}]
        }
        assert json_schema_to_python_type(schema) == "bool | str | int"

    def test_array_with_union_items_in_union(self):
        """Union containing array-of-union should not split inside brackets.

        e.g., anyOf: [ {"type":"array","items":{"anyOf":[str, int]}}, null ]
        should produce: list[str | int] | None (not corrupted)
        """
        schema = {
            "anyOf": [
                {
                    "type": "array",
                    "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                },
                {"type": "null"},
            ]
        }
        result = json_schema_to_python_type(schema)
        assert result == "list[str | int] | None"

    def test_literal_with_pipe_in_string(self):
        """Union containing Literal with ' | ' in string should not split inside quotes."""
        schema = {
            "anyOf": [
                {"enum": ["a | b", "c | d"]},
                {"type": "integer"},
            ]
        }
        result = json_schema_to_python_type(schema)
        assert result == "Literal['a | b', 'c | d'] | int"

    def test_complex_nested_union_with_brackets(self):
        """Complex nested types with unions inside brackets should be preserved."""
        schema = {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": {
                        "anyOf": [{"type": "string"}, {"type": "integer"}]
                    },
                },
                {"type": "array", "items": {"type": "boolean"}},
                {"type": "null"},
            ]
        }
        result = json_schema_to_python_type(schema)
        assert result == "dict[str, str | int] | list[bool] | None"


class TestSplitUnionTopLevel:
    """Test the _split_union_top_level helper function directly."""

    def test_simple_union(self):
        """Simple union should split correctly."""
        assert _split_union_top_level("str | int") == ["str", "int"]

    def test_no_union(self):
        """Non-union should return single element."""
        assert _split_union_top_level("str") == ["str"]

    def test_union_inside_brackets_not_split(self):
        """Union inside brackets should not be split."""
        assert _split_union_top_level("list[str | int]") == ["list[str | int]"]

    def test_union_inside_nested_brackets_not_split(self):
        """Union inside nested brackets should not be split."""
        result = _split_union_top_level("dict[str, list[int | float]]")
        assert result == ["dict[str, list[int | float]]"]

    def test_top_level_with_nested_brackets(self):
        """Top-level union with nested brackets should split correctly."""
        result = _split_union_top_level("list[str | int] | None")
        assert result == ["list[str | int]", "None"]

    def test_union_inside_single_quotes_not_split(self):
        """Union inside single quotes should not be split."""
        result = _split_union_top_level("Literal['a | b']")
        assert result == ["Literal['a | b']"]

    def test_union_inside_double_quotes_not_split(self):
        """Union inside double quotes should not be split."""
        result = _split_union_top_level('Literal["a | b"]')
        assert result == ['Literal["a | b"]']

    def test_escaped_quotes_handled(self):
        """Escaped quotes inside strings should be handled."""
        result = _split_union_top_level(r"Literal['it\'s | ok'] | int")
        assert result == [r"Literal['it\'s | ok']", "int"]

    def test_multiple_literals_in_union(self):
        """Multiple Literals in a union should work."""
        result = _split_union_top_level("Literal['a | b', 'c'] | int | None")
        assert result == ["Literal['a | b', 'c']", "int", "None"]

    def test_empty_string(self):
        """Empty string should return empty list."""
        assert _split_union_top_level("") == []

    def test_whitespace_handling(self):
        """Whitespace should be trimmed from parts."""
        result = _split_union_top_level("  str  |  int  ")
        assert result == ["str", "int"]

    def test_trailing_backslash(self):
        """Trailing backslash should be handled gracefully."""
        # Edge case: backslash at end of string
        result = _split_union_top_level("Literal['test\\")
        assert result == ["Literal['test\\"]


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
