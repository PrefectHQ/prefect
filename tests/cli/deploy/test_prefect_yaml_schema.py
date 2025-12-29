"""Tests for the prefect.yaml JSON schema generation."""

import json

import pytest
from jsonschema import Draft202012Validator, ValidationError, validate

from prefect import __development_base_path__
from prefect.cli.deploy._models import PrefectYamlModel


@pytest.fixture
def schema():
    """Load the generated JSON schema."""
    schema_path = __development_base_path__ / "schemas" / "prefect.yaml.schema.json"
    if not schema_path.exists():
        pytest.skip(
            "Schema file not generated yet - run generate_prefect_yaml_schema.py"
        )
    with open(schema_path) as f:
        return json.load(f)


class TestPrefectYamlSchema:
    def test_schema_file_exists(self):
        """Verify the schema file exists in the expected location."""
        schema_path = __development_base_path__ / "schemas" / "prefect.yaml.schema.json"
        assert schema_path.exists(), (
            "Schema file should exist at schemas/prefect.yaml.schema.json"
        )

    def test_schema_is_valid_json_schema(self, schema):
        """Verify the generated schema is a valid JSON schema."""
        # This will raise if the schema itself is invalid
        Draft202012Validator.check_schema(schema)

    def test_schema_has_required_metadata(self, schema):
        """Verify the schema has the expected metadata fields."""
        assert schema.get("title") == "Prefect YAML"
        assert "$schema" in schema
        assert "$id" in schema
        assert "prefect.yaml.schema.json" in schema["$id"]

    def test_schema_validates_empty_config(self, schema):
        """An empty config should be valid."""
        validate({}, schema)

    def test_schema_validates_minimal_deployment(self, schema):
        """A minimal deployment config should be valid."""
        config = {
            "deployments": [
                {
                    "name": "my-deployment",
                    "entrypoint": "flows.py:my_flow",
                }
            ]
        }
        validate(config, schema)

    def test_schema_validates_full_deployment(self, schema):
        """A fully-specified deployment config should be valid."""
        config = {
            "name": "my-project",
            "prefect-version": "3.0.0",
            "build": [
                {"prefect.deployments.steps.run_shell_script": {"script": "echo hello"}}
            ],
            "push": [],
            "pull": [
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/org/repo"
                    }
                }
            ],
            "deployments": [
                {
                    "name": "my-deployment",
                    "version": "1.0.0",
                    "tags": ["prod", "critical"],
                    "description": "A test deployment",
                    "entrypoint": "flows.py:my_flow",
                    "parameters": {"param1": "value1"},
                    "work_pool": {
                        "name": "my-pool",
                        "work_queue_name": "default",
                        "job_variables": {"cpu": 2},
                    },
                    "schedules": [
                        {"cron": "0 0 * * *", "timezone": "America/New_York"},
                    ],
                }
            ],
        }
        validate(config, schema)

    def test_schema_rejects_invalid_deployments_type(self, schema):
        """deployments must be a list, not a string."""
        config = {"deployments": "not a list"}
        with pytest.raises(ValidationError) as exc_info:
            validate(config, schema)
        assert "not of type 'array'" in str(exc_info.value)

    def test_schema_matches_pydantic_model(self, schema):
        """The generated schema should match what PrefectYamlModel produces."""
        model_schema = PrefectYamlModel.model_json_schema()
        # Check that key definitions exist in both
        assert "DeploymentConfig" in schema.get("$defs", {})
        assert "DeploymentConfig" in model_schema.get("$defs", {})
