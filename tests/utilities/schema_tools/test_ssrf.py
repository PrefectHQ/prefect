from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest

from prefect.utilities.schema_tools.validation import (
    ValidationError,
    validate,
)

EXTERNAL_REFS = [
    "https://a.example.com/schema.json",
    "http://b.example.com.namespace.svc/schema.json",
    "http://169.254.169.254/latest/meta-data/",
]


@pytest.fixture
def no_network() -> Iterator[mock.MagicMock]:
    with mock.patch("urllib.request.urlopen") as urlopen:
        urlopen.side_effect = AssertionError(
            "validation attempted an outbound network request"
        )
        yield urlopen


def external_ref_schema(ref: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"x": {"$ref": ref}},
    }


@pytest.mark.parametrize("ref", EXTERNAL_REFS)
def test_external_ref_raises_controlled_error_without_network(
    ref: str, no_network: mock.MagicMock
):
    with pytest.raises(ValidationError):
        validate(
            {"x": 1}, external_ref_schema(ref), raise_on_error=True, preprocess=False
        )
    no_network.assert_not_called()


@pytest.mark.parametrize("ref", EXTERNAL_REFS)
def test_external_ref_non_raise_path_raises_without_network(
    ref: str, no_network: mock.MagicMock
):
    with pytest.raises(ValidationError):
        validate(
            {"x": 1}, external_ref_schema(ref), raise_on_error=False, preprocess=False
        )
    no_network.assert_not_called()


IN_DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"x": {"$ref": "#/$defs/PositiveInt"}},
    "$defs": {"PositiveInt": {"type": "integer", "minimum": 0}},
}


def test_in_document_ref_passing_instance_validates(no_network: mock.MagicMock):
    errors = validate({"x": 5}, IN_DOCUMENT_SCHEMA, preprocess=False)
    assert errors == []
    no_network.assert_not_called()


def test_in_document_ref_failing_instance_reports_error(no_network: mock.MagicMock):
    errors = validate({"x": -1}, IN_DOCUMENT_SCHEMA, preprocess=False)
    assert len(errors) == 1
    no_network.assert_not_called()


def test_in_document_ref_failing_instance_raises(no_network: mock.MagicMock):
    with pytest.raises(ValidationError):
        validate({"x": -1}, IN_DOCUMENT_SCHEMA, raise_on_error=True, preprocess=False)
    no_network.assert_not_called()
