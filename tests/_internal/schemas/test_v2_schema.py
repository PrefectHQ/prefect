import inspect

from pydantic import Field
from pydantic_core import PydanticUndefined

from prefect._internal.pydantic.v2_schema import process_v2_params


class TestProcessV2Params:
    """Test the process_v2_params functions with and without FieldInfo."""

    def test_process_v2_params_with_existing_fieldinfo(self):
        """Test parameter processing with an existing FieldInfo object as default."""
        existing_field = Field(
            default="default_name",
            description="Existing field description",
            json_schema_extra={"position": 99},
        )

        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=existing_field,
            annotation=str,
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings={"name": "Docstring description"}, aliases={}
        )

        assert name == "name"
        assert type_ is str
        assert field.default == "default_name"
        assert field.title == "name"
        assert field.description == "Existing field description"
        assert field.json_schema_extra == {"position": 99}

    def test_process_v2_params_with_existing_fieldinfo_no_description(self):
        """Test parameter processing with existing FieldInfo that has no description."""
        existing_field = Field(
            default="default_name", description=None, json_schema_extra={"position": 99}
        )

        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=existing_field,
            annotation=str,
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings={"name": "Docstring description"}, aliases={}
        )

        assert name == "name"
        assert field.description == "Docstring description"

    def test_process_v2_params_with_existing_fieldinfo_empty_description(self):
        """Test parameter processing with existing FieldInfo that has empty description."""
        existing_field = Field(
            default="default_name", description="", json_schema_extra={"position": 99}
        )

        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=existing_field,
            annotation=str,
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings={"name": "Docstring description"}, aliases={}
        )

        assert name == "name"
        assert field.description == "Docstring description"

    def test_process_v2_params_with_existing_fieldinfo_required(self):
        """Test parameter processing with existing FieldInfo for a required field."""
        existing_field = Field(description="Required field with existing info")

        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=existing_field,
            annotation=str,
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings={}, aliases={}
        )

        assert name == "name"
        assert field.default is PydanticUndefined  # Required field
        assert field.description == "Required field with existing info"

    def test_process_v2_params_with_existing_fieldinfo_no_json_schema_extra(self):
        """Test parameter processing with existing FieldInfo that has no json_schema_extra."""
        existing_field = Field(
            default="default_value", description="Field without json_schema_extra"
        )

        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=existing_field,
            annotation=str,
        )

        name, type_, field = process_v2_params(
            param, position=5, docstrings={}, aliases={}
        )

        assert name == "name"
        assert field.json_schema_extra == {"position": 5}
