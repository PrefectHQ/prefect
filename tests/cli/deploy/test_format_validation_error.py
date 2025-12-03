"""Tests for the _format_validation_error function."""

import pytest
from pydantic import ValidationError

from prefect.cli.deploy._config import _format_validation_error
from prefect.cli.deploy._models import PrefectYamlModel


def test_format_validation_error_with_invalid_schedule():
    """Test error formatting when schedule field is invalid."""
    raw_data = {
        "deployments": [
            {
                "name": "my-deployment",
                "entrypoint": "flow.py:my_flow",
                "schedule": "not a dict",  # Should be a dict
            }
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid fields in deployments:" in result
    assert "my-deployment: schedule" in result
    assert "https://docs.prefect.io/v3/concepts/deployments#deployment-schema" in result


def test_format_validation_error_with_multiple_invalid_fields():
    """Test error formatting with multiple invalid fields in one deployment."""
    raw_data = {
        "deployments": [
            {
                "name": "test-deploy",
                "entrypoint": 123,  # Should be string
                "schedule": False,  # Should be dict
                "tags": {},  # Should be list or string
            }
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid fields in deployments:" in result
    assert "test-deploy:" in result
    # Fields should be sorted alphabetically
    assert "entrypoint, schedule, tags" in result or (
        "entrypoint" in result and "schedule" in result and "tags" in result
    )


def test_format_validation_error_with_multiple_deployments():
    """Test error formatting with errors in multiple deployments."""
    raw_data = {
        "deployments": [
            {
                "name": "first-deployment",
                "entrypoint": "flow.py:my_flow",
                "schedule": [],  # Invalid
            },
            {
                "name": "second-deployment",
                "entrypoint": "flow.py:my_flow",
                "concurrency_limit": "not a number",  # Invalid
            },
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid fields in deployments:" in result
    assert "first-deployment: schedule" in result
    assert "second-deployment: concurrency_limit" in result


def test_format_validation_error_with_unnamed_deployment():
    """Test error formatting when deployment has no name."""
    raw_data = {
        "deployments": [
            {
                "entrypoint": "flow.py:my_flow",
                "tags": 123,  # Invalid
            }
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid fields in deployments:" in result
    assert "#0: tags" in result  # Should use index when no name


def test_format_validation_error_with_invalid_tags_type():
    """Test error formatting for invalid tags type."""
    raw_data = {
        "deployments": [
            {
                "name": "my-deployment",
                "entrypoint": "flow.py:my_flow",
                "tags": 123,  # Should be list or string
            }
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid fields in deployments:" in result
    assert "my-deployment: tags" in result


def test_format_validation_error_with_invalid_dict_keys():
    """Test error formatting when dict has wrong keys."""
    raw_data = {
        "deployments": [
            {
                "name": "bad-schedule",
                "entrypoint": "flow.py:my_flow",
                "schedule": {"foo": "0 4 * * *"},  # Invalid key
            }
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid fields in deployments:" in result
    # Should still identify schedule as the problem field
    assert "bad-schedule:" in result
    assert "schedule" in result or "foo" in result


def test_format_validation_error_empty_raw_data():
    """Test error formatting with minimal data."""
    raw_data = {}

    # This should validate fine (empty is valid)
    model = PrefectYamlModel.model_validate(raw_data)
    assert model.deployments == []


def test_format_validation_error_no_deployment_errors():
    """Test when there are no deployment-specific errors."""
    raw_data = {"invalid_top_level_field": "value", "deployments": []}

    # Extra fields are ignored, so this should validate fine
    model = PrefectYamlModel.model_validate(raw_data)
    assert model.deployments == []


def test_format_validation_error_with_top_level_field_error():
    """Test error formatting for top-level field validation errors (issue #19467)."""
    raw_data = {
        "prefect-version": 3,  # Should be a string, not an int
        "deployments": [
            {
                "name": "my-deployment",
                "entrypoint": "flow.py:my_flow",
            }
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    assert "Invalid top-level fields in config file:" in result
    assert "prefect-version: Input should be a valid string" in result
    assert "https://docs.prefect.io/v3/how-to-guides/deployments/prefect-yaml" in result
    # Should not include deployment error section
    assert "Invalid fields in deployments:" not in result


def test_format_validation_error_with_both_top_level_and_deployment_errors():
    """Test error formatting when both top-level and deployment errors exist."""
    raw_data = {
        "name": 123,  # Should be a string
        "deployments": [
            {
                "name": "my-deployment",
                "entrypoint": "flow.py:my_flow",
                "tags": {},  # Should be list or string
            }
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        PrefectYamlModel.model_validate(raw_data)

    result = _format_validation_error(exc_info.value, raw_data)

    # Should have both sections
    assert "Invalid top-level fields in config file:" in result
    assert "name: Input should be a valid string" in result
    assert "Invalid fields in deployments:" in result
    assert "my-deployment: tags" in result
    # Should have both links
    assert "https://docs.prefect.io/v3/how-to-guides/deployments/prefect-yaml" in result
    assert "https://docs.prefect.io/v3/concepts/deployments#deployment-schema" in result


def test_trigger_with_templated_enabled_field_should_not_raise():
    """
    Regression test for issue #19501: triggers with templated 'enabled' field
    should be accepted during YAML loading, allowing template resolution later.

    The 'enabled' field may contain a Jinja template like
    '{{ prefect.variables.deployment_trigger_is_active }}' which will be
    resolved to a boolean after variable resolution. The YAML validation
    should accept this string and defer strict type validation until after
    templating occurs.
    """
    raw_data = {
        "deployments": [
            {
                "name": "my-deployment",
                "entrypoint": "flow.py:my_flow",
                "triggers": [
                    {
                        "type": "event",
                        "enabled": "{{ prefect.variables.deployment_trigger_is_active }}",
                        "match": {"prefect.resource.id": "hello.world"},
                        "expect": ["external.resource.pinged"],
                    }
                ],
            }
        ]
    }

    # This should NOT raise a validation error - the trigger should be accepted
    # as a raw dict and validated later after template resolution
    model = PrefectYamlModel.model_validate(raw_data)
    assert len(model.deployments) == 1
    assert model.deployments[0].triggers is not None
    assert len(model.deployments[0].triggers) == 1
