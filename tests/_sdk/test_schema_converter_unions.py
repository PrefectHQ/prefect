"""Tests for union type conversion in JSON Schema."""

from prefect._sdk.schema_converter import json_schema_to_python_type


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
