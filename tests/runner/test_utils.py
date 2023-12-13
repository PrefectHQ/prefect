from unittest.mock import Mock

import pytest

from prefect import __version__ as PREFECT_VERSION
from prefect.runner.utils import (
    inject_schemas_into_openapi,
    merge_definitions,
    update_refs_to_components,
)


@pytest.fixture
def mock_app():
    app = Mock()
    app.routes = [Mock(name="dummy_route", methods=["GET"], path="/dummy")]
    return app


@pytest.fixture
def deployment_schemas():
    return {
        "deployment1": {
            "definitions": {
                "Model1": {
                    "type": "object",
                    "properties": {"field1": {"type": "string"}},
                }
            }
        },
        "deployment2": {
            "definitions": {
                "Model2": {
                    "type": "object",
                    "properties": {"field2": {"type": "integer"}},
                }
            }
        },
    }


@pytest.fixture
def openapi_schema():
    return {
        "openapi": "3.1.0",
        "info": {"title": "FastAPI Prefect Runner", "version": PREFECT_VERSION},
        "components": {"schemas": {}},
        "paths": {},
    }


@pytest.fixture
def schema_with_refs():
    return {
        "paths": {
            "/path": {
                "get": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/definitions/Model1"}
                            }
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def nested_schema_with_refs():
    return {
        "definitions": {
            "NestedModel": {
                "type": "object",
                "properties": {"nestedField": {"$ref": "#/definitions/Model1"}},
            }
        },
        "paths": {
            "/nested": {
                "get": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/definitions/NestedModel"}
                            }
                        }
                    }
                }
            }
        },
    }


@pytest.fixture
def augmented_openapi_schema(deployment_schemas, openapi_schema):
    merged_schema = merge_definitions(deployment_schemas, openapi_schema)
    return update_refs_to_components(merged_schema)


def test_inject_schemas_into_openapi(
    mock_app, deployment_schemas, augmented_openapi_schema
):
    result_schema = inject_schemas_into_openapi(mock_app, deployment_schemas)
    assert result_schema == augmented_openapi_schema


class TestMergeDefinitions:
    def test_merge_definitions(self, deployment_schemas, openapi_schema):
        result_schema = merge_definitions(deployment_schemas, openapi_schema)

        expected_models = {}
        for definitions in deployment_schemas.values():
            if "definitions" in definitions:
                expected_models.update(definitions["definitions"])

        assert result_schema["components"]["schemas"] == expected_models

    def test_merge_definitions_empty_schemas(self, openapi_schema):
        result_schema = merge_definitions({}, openapi_schema)
        assert result_schema["components"]["schemas"] == {}

    def test_merge_definitions_preserves_unrelated_schema_parts(
        self, deployment_schemas, openapi_schema
    ):
        original_paths = {"dummy_path": "dummy_value"}
        openapi_schema["paths"] = original_paths
        result_schema = merge_definitions(deployment_schemas, openapi_schema)
        assert result_schema["paths"] == original_paths


class TestUpdateRefsToComponents:
    def test_update_refs_to_components(
        self, openapi_schema, deployment_schemas, schema_with_refs
    ):
        result_schema = update_refs_to_components(schema_with_refs)
        assert (
            result_schema["paths"]["/path"]["get"]["requestBody"]["content"][
                "application/json"
            ]["schema"]["$ref"]
            == "#/components/schemas/Model1"
        )

    def test_update_refs_to_components_empty_schema(self):
        empty_schema = {"paths": {}}
        result_schema = update_refs_to_components(empty_schema)
        assert result_schema == empty_schema

    def test_update_refs_to_components_nested_schema(self, nested_schema_with_refs):
        result_schema = update_refs_to_components(nested_schema_with_refs)
        assert (
            result_schema["paths"]["/nested"]["get"]["requestBody"]["content"][
                "application/json"
            ]["schema"]["$ref"]
            == "#/components/schemas/NestedModel"
        )
        assert (
            result_schema["definitions"]["NestedModel"]["properties"]["nestedField"][
                "$ref"
            ]
            == "#/components/schemas/Model1"
        )
