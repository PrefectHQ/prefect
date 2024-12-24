import pytest

from prefect._internal.schemas.validators import (
    validate_parameter_openapi_schema,
    validate_values_conform_to_schema,
)

# Tests for validate_schema function


def test_validate_schema_with_valid_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    # Should not raise any exception
    validate_parameter_openapi_schema(schema, {"enforce_parameter_schema": True})


def test_validate_schema_with_invalid_schema():
    schema = {"type": "object", "properties": {"name": {"type": "nonexistenttype"}}}
    with pytest.raises(ValueError) as excinfo:
        validate_parameter_openapi_schema(schema, {"enforce_parameter_schema": True})
    assert "The provided schema is not a valid json schema." in str(excinfo.value)
    assert (
        "Schema error: 'nonexistenttype' is not valid under any of the given schemas"
        in str(excinfo.value)
    )


def test_validate_schema_with_none_schema():
    # Should not raise any exception
    validate_parameter_openapi_schema(None, {"enforce_parameter_schema": True})


# Tests for validate_values_conform_to_schema function


def test_validate_values_conform_to_schema_valid_values_valid_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    values = {"name": "John"}
    # Should not raise any exception
    validate_values_conform_to_schema(values, schema)


def test_validate_values_conform_to_schema_invalid_values_valid_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    values = {"name": 123}
    with pytest.raises(ValueError) as excinfo:
        validate_values_conform_to_schema(values, schema)
    assert "Validation failed for field 'name'." in str(excinfo.value)
    assert "Failure reason: 123 is not of type 'string'" in str(excinfo.value)


def test_validate_values_conform_to_schema_valid_values_invalid_schema():
    schema = {"type": "object", "properties": {"name": {"type": "nonexistenttype"}}}
    values = {"name": "John"}
    with pytest.raises(ValueError) as excinfo:
        validate_values_conform_to_schema(values, schema)
    assert "The provided schema is not a valid json schema." in str(excinfo.value)
    assert (
        "Schema error: 'nonexistenttype' is not valid under any of the given schemas"
        in str(excinfo.value)
    )


def test_validate_values_conform_to_schema_ignore_required():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    values = {}
    # Should not raise any exception
    validate_values_conform_to_schema(values, schema, ignore_required=True)

    # Make sure that the schema is not modified
    assert schema == {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }


def test_validate_values_conform_to_schema_none_values_or_schema():
    # Should not raise any exception for either of these
    validate_values_conform_to_schema(None, {"type": "string"})
    validate_values_conform_to_schema({"name": "John"}, None)
    validate_values_conform_to_schema(None, None)
