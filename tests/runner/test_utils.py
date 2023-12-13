from unittest.mock import Mock

import pytest

from prefect.runner.utils import (
    inject_schemas_into_openapi,
    merge_definitions,
    update_refs_in_schema,
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
def schema_item():
    return {"$ref": "#/definitions/Model1"}


@pytest.fixture
def deployment_openapi_schema(schema_item):
    return {
        "paths": {
            "/path": {
                "get": {
                    "requestBody": {
                        "content": {"application/json": {"schema": schema_item}}
                    }
                }
            }
        }
    }


@pytest.fixture
def openapi_schema():
    return {"components": {"schemas": {}}}


def test_inject_schemas_into_openapi(mock_app, deployment_schemas):
    augmented_schema = inject_schemas_into_openapi(mock_app, deployment_schemas)
    assert "Model1" in augmented_schema["components"]["schemas"]
    assert "Model2" in augmented_schema["components"]["schemas"]
    assert augmented_schema["components"]["schemas"]["Model1"]["type"] == "object"
    assert augmented_schema["components"]["schemas"]["Model2"]["type"] == "object"
    assert (
        augmented_schema["components"]["schemas"]["Model1"]["properties"]["field1"][
            "type"
        ]
        == "string"
    )
    assert (
        augmented_schema["components"]["schemas"]["Model2"]["properties"]["field2"][
            "type"
        ]
        == "integer"
    )


def test_merge_definitions(deployment_schemas, openapi_schema):
    merge_definitions(deployment_schemas, openapi_schema)
    assert "Model1" in openapi_schema["components"]["schemas"]
    assert "Model2" in openapi_schema["components"]["schemas"]
    assert openapi_schema["components"]["schemas"]["Model1"]["type"] == "object"
    assert openapi_schema["components"]["schemas"]["Model2"]["type"] == "object"
    assert (
        openapi_schema["components"]["schemas"]["Model1"]["properties"]["field1"][
            "type"
        ]
        == "string"
    )
    assert (
        openapi_schema["components"]["schemas"]["Model2"]["properties"]["field2"][
            "type"
        ]
        == "integer"
    )


def test_update_refs_in_schema(schema_item):
    update_refs_in_schema(schema_item, "#/components/schemas/")
    assert schema_item["$ref"] == "#/components/schemas/Model1"


def test_update_refs_to_components(deployment_openapi_schema):
    update_refs_to_components(deployment_openapi_schema)
    assert (
        deployment_openapi_schema["paths"]["/path"]["get"]["requestBody"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/Model1"
    )
