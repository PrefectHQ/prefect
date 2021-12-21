import pytest
import requests
import responses
from prefect.tasks.monte_carlo.monte_carlo_lineage import (
    MonteCarloCreateOrUpdateNodeWithTag,
    MonteCarloGetResources,
    MonteCarloCreateOrUpdateLineage,
)

MONTE_CARLO_API_URL = "https://api.getmontecarlo.com/graphql"


@responses.activate
def test_monte_carlo_fails_with_invalid_api_key():
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=403,
        json={
            "Message": "User is not authorized to access this resource with an explicit deny."
        },
    )
    response = requests.post(
        url=MONTE_CARLO_API_URL,
        json=dict(query="""{getUser {email  firstName  lastName}}""", variables={}),
        headers={
            "x-mcd-id": "bad key",
            "x-mcd-token": "bad token",
            "Content-Type": "application/json",
        },
    )
    assert response.json() == {
        "Message": "User is not authorized to access this resource with an explicit deny."
    }


@responses.activate
def test_monte_carlo_works_with_valid_api_key():
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=200,
        json={
            "data": {
                "getUser": {
                    "email": "marvin@prefect.io",
                    "firstName": "Marvin",
                    "lastName": "the Paranoid Android",
                }
            }
        },
    )
    response = requests.post(
        url=MONTE_CARLO_API_URL,
        json=dict(query="""{getUser {email  firstName  lastName}}""", variables={}),
        headers={
            "x-mcd-id": "valid_api_key_id",
            "x-mcd-token": "valid_api_token",
            "Content-Type": "application/json",
        },
    )
    assert response.json() == {
        "data": {
            "getUser": {
                "email": "marvin@prefect.io",
                "firstName": "Marvin",
                "lastName": "the Paranoid Android",
            }
        }
    }


@responses.activate
def test_monte_carlo_create_or_update_node_with_tag():
    node_name = "test_node"
    object_id = "test_node"
    object_type = "table"
    resource_name = "test_dwh"
    metadata_key = "test_key"
    metadata_value = "test_value"
    api_key_id = "your_api_key_id"
    api_token = "your_api_token"
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=200,
        json={
            "data": {"createOrUpdateLineageNode": {"node": {"mcon": "MCON++123456789"}}}
        },
    )
    result = MonteCarloCreateOrUpdateNodeWithTag(
        node_name,
        object_id,
        object_type,
        resource_name,
        metadata_key,
        metadata_value,
        api_key_id,
        api_token,
        prefect_context_tag=False,
    ).run()
    assert result == "MCON++123456789"


@responses.activate
def test_monte_carlo_create_or_update_lineage():
    api_key_id = "your_api_key_id"
    api_token = "your_api_token"
    source = dict(
        node_name="test_node",
        object_id="test_node",
        object_type="table",
        resource_name="test_system",
    )
    destination = dict(
        node_name="test_dwh_table",
        object_id="test_dwh_table",
        object_type="table",
        resource_name="test_dwh",
    )
    # source node:
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=200,
        json={
            "data": {"createOrUpdateLineageNode": {"node": {"mcon": "MCON++123456789"}}}
        },
    )
    # destination node:
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=200,
        json={
            "data": {"createOrUpdateLineageNode": {"node": {"mcon": "MCON++987654321"}}}
        },
    )
    # lineage edge:
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=200,
        json={
            "data": {
                "createOrUpdateLineageEdge": {
                    "edge": {
                        "edgeId": "f556899cfd39993517d7fc262f3d22d759fe94bd54324c5d89f4be48333dcab7",
                    }
                }
            }
        },
    )
    result = MonteCarloCreateOrUpdateLineage(
        source, destination, api_key_id, api_token, prefect_context_tag=False
    ).run()
    assert result == "f556899cfd39993517d7fc262f3d22d759fe94bd54324c5d89f4be48333dcab7"


@pytest.mark.parametrize(
    "source",
    [
        dict(
            object_id="test_node",
            object_type="table",
            resource_name="test_system",
        ),
        dict(
            node_name="test_node",
            object_type="table",
            resource_name="test_system",
        ),
        dict(
            node_name="test_node",
            object_id="test_node",
            object_type="table",
        ),
    ],
)
@pytest.mark.parametrize(
    "destination",
    [
        dict(
            object_id="test_node",
            object_type="table",
            resource_name="test_system",
        ),
        dict(
            node_name="test_node",
            object_type="table",
            resource_name="test_system",
        ),
        dict(
            node_name="test_node",
            object_id="test_node",
            object_type="table",
        ),
    ],
)
def test_monte_carlo_create_or_update_lineage_raises_with_missing_attributes(
    source, destination
):
    api_key_id = "your_api_key_id"
    api_token = "your_api_token"
    with pytest.raises(ValueError) as exc:
        MonteCarloCreateOrUpdateLineage(
            source, destination, api_key_id, api_token, prefect_context_tag=False
        ).run()
    assert "in both source and destination" in str(exc)


@pytest.mark.parametrize("node_name", [None, "node_name"])
@pytest.mark.parametrize("object_id", [None, "object_id"])
@pytest.mark.parametrize("object_type", [None, "table"])
@pytest.mark.parametrize("resource_name", [None, "resource_name"])
@pytest.mark.parametrize("metadata_key", [None, "metadata_key"])
@pytest.mark.parametrize("metadata_value", [None])
def test_monte_carlo_create_or_update_node_with_tag_raises_with_missing_attributes(
    node_name, object_id, object_type, resource_name, metadata_key, metadata_value
):
    api_key_id = "your_api_key_id"
    api_token = "your_api_token"
    with pytest.raises(ValueError) as exc:
        MonteCarloCreateOrUpdateNodeWithTag(
            node_name,
            object_id,
            object_type,
            resource_name,
            metadata_key,
            metadata_value,
            api_key_id,
            api_token,
            prefect_context_tag=False,
        ).run()
    assert "must be provided" in str(exc)


@responses.activate
def test_monte_carlo_get_resources():
    api_key_id = "your_api_key_id"
    api_token = "your_api_token"
    responses.add(
        responses.POST,
        MONTE_CARLO_API_URL,
        status=200,
        json={
            "data": {
                "getResources": [
                    {
                        "name": "YOUR_DATAWAREHOUSE_NAME",
                        "type": "snowflake",
                        "id": "123456789",
                        "uuid": "ecaac7b9-bde1-4585-8593-afbb5bdbf12b",
                        "isDefault": False,
                        "isUserProvided": False,
                    },
                    {
                        "name": "default",
                        "type": None,
                        "id": "987654321",
                        "uuid": "2cc3bc38-b1fe-4e3d-9685-bbcf8b3447d5",
                        "isDefault": True,
                        "isUserProvided": True,
                    },
                    {
                        "name": "XYZ",
                        "type": "source_system",
                        "id": "qwertzuiop12345",
                        "uuid": "65793a7a-8e1c-45f9-a463-b7bfe0ece5c3",
                        "isDefault": False,
                        "isUserProvided": True,
                    },
                ]
            }
        },
    )
    result = MonteCarloGetResources(api_key_id, api_token).run()
    assert result == [
        {
            "name": "YOUR_DATAWAREHOUSE_NAME",
            "type": "snowflake",
            "id": "123456789",
            "uuid": "ecaac7b9-bde1-4585-8593-afbb5bdbf12b",
            "isDefault": False,
            "isUserProvided": False,
        },
        {
            "name": "default",
            "type": None,
            "id": "987654321",
            "uuid": "2cc3bc38-b1fe-4e3d-9685-bbcf8b3447d5",
            "isDefault": True,
            "isUserProvided": True,
        },
        {
            "name": "XYZ",
            "type": "source_system",
            "id": "qwertzuiop12345",
            "uuid": "65793a7a-8e1c-45f9-a463-b7bfe0ece5c3",
            "isDefault": False,
            "isUserProvided": True,
        },
    ]
