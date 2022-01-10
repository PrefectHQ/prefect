import pytest
import requests
import responses
from prefect.tasks.monte_carlo.monte_carlo_lineage import (
    MonteCarloCreateOrUpdateNodeWithTags,
    MonteCarloGetResources,
    MonteCarloCreateOrUpdateLineage,
    MonteCarloIncorrectTagsFormat,
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
def test_monte_carlo_create_or_update_node_with_tags():
    node_name = "test_node"
    object_id = "test_node"
    object_type = "table"
    resource_name = "test_dwh"
    lineage_tags = [
        {"propertyName": "prefect_test_key", "propertyValue": "prefect_test_value"}
    ]
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
    result = MonteCarloCreateOrUpdateNodeWithTags(
        node_name,
        object_id,
        object_type,
        resource_name,
        lineage_tags,
        api_key_id,
        api_token,
        prefect_context_tags=False,
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
        source, destination, api_key_id, api_token, prefect_context_tags=False
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
    with pytest.raises(ValueError, match="in both source and destination"):
        MonteCarloCreateOrUpdateLineage(
            source, destination, api_key_id, api_token, prefect_context_tags=False
        ).run()


@pytest.mark.parametrize("node_name", [None, "node_name"])
@pytest.mark.parametrize("object_id", [None, "object_id"])
@pytest.mark.parametrize("object_type", [None, "table"])
@pytest.mark.parametrize("resource_name", [None])
def test_monte_carlo_create_or_update_node_with_tags_raises_with_missing_attributes(
    node_name, object_id, object_type, resource_name
):
    with pytest.raises(ValueError, match="must be provided"):
        MonteCarloCreateOrUpdateNodeWithTags(
            node_name=node_name,
            object_id=object_id,
            object_type=object_type,
            resource_name=resource_name,
            lineage_tags=None,
            api_key_id="your_api_key_id",
            api_token="your_api_token",
            prefect_context_tags=False,
        ).run()


def test_monte_carlo_create_or_update_lineage_node_with_tags_raises_with_incorrect_tag_format():
    node_name = "test_node"
    object_id = "test_node"
    object_type = "table"
    resource_name = "test_dwh"
    api_key_id = "your_api_key_id"
    api_token = "your_api_token"
    lineage_tags = [
        {"wrong_key_name": "tag_name", "propertyValue": "tag_value"},
        {"propertyName": "tag_name", "wrong_value": "tag_value"},
    ]
    with pytest.raises(
        MonteCarloIncorrectTagsFormat, match="Must provide tags in the format"
    ):
        MonteCarloCreateOrUpdateNodeWithTags(
            node_name,
            object_id,
            object_type,
            resource_name,
            lineage_tags,
            api_key_id,
            api_token,
            prefect_context_tags=False,
        ).run()


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
