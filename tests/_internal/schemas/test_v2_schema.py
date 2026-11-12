import inspect
from typing import Annotated

import pytest
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

    def test_process_v2_params_with_annotated_fieldinfo(self):
        """Test parameter processing with a FieldInfo in an Annotated type."""
        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default="default_name",
            annotation=Annotated[str, Field(description="Annotated field description")],
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings={"name": "Docstring description"}, aliases={}
        )

        assert name == "name"
        assert field.default == "default_name"
        assert field.title == "name"
        assert field.description == "Annotated field description"

    def test_process_v2_params_with_annotated_fieldinfo_uses_last_description(self):
        """Test parameter processing with several FieldInfo objects in Annotated."""
        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Annotated[
                str,
                Field(description="First description"),
                Field(description="Second description"),
                Field(max_length=10),
            ],
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings={}, aliases={}
        )

        assert name == "name"
        assert field.description == "Second description"

    @pytest.mark.parametrize("cleared_description", [None, ""])
    @pytest.mark.parametrize(
        "docstrings, expected_description",
        [({}, None), ({"name": "Docstring description"}, "Docstring description")],
    )
    def test_process_v2_params_with_annotated_fieldinfo_later_field_clears_description(
        self,
        cleared_description: str | None,
        docstrings: dict[str, str],
        expected_description: str | None,
    ):
        """Test that a later FieldInfo in Annotated can clear an earlier description."""
        param = inspect.Parameter(
            "name",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Annotated[
                str,
                Field(description="Earlier description"),
                Field(description=cleared_description),
            ],
        )

        name, type_, field = process_v2_params(
            param, position=0, docstrings=docstrings, aliases={}
        )

        assert name == "name"
        assert field.description == expected_description
