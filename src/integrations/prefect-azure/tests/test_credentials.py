from unittest.mock import MagicMock

import pytest
from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient
from conftest import CosmosClientMock
from prefect_azure.credentials import (
    AzureBlobStorageCredentials,
    AzureCosmosDbCredentials,
    AzureMlCredentials,
)

from prefect import flow


def test_get_service_client(blob_connection_string):
    @flow
    def test_flow():
        client = AzureBlobStorageCredentials(
            connection_string=blob_connection_string
        ).get_client()
        return client

    client = test_flow()
    assert isinstance(client, BlobServiceClient)


def test_get_blob_container_client(blob_connection_string):
    @flow
    def test_flow():
        client = AzureBlobStorageCredentials(
            connection_string=blob_connection_string
        ).get_container_client("container")
        return client

    client = test_flow()
    assert isinstance(client, ContainerClient)
    client.container_name == "container"


def test_get_blob_client(blob_connection_string):
    @flow
    def test_flow():
        client = AzureBlobStorageCredentials(
            connection_string=blob_connection_string
        ).get_blob_client("container", "blob")
        return client

    client = test_flow()
    assert isinstance(client, BlobClient)
    client.container_name == "container"
    client.blob_name == "blob"


def test_get_service_client_either_error():
    with pytest.raises(ValueError, match="either a connection string or"):
        AzureBlobStorageCredentials().get_client()


def test_get_service_client_both_error():
    with pytest.raises(ValueError, match="not both"):
        AzureBlobStorageCredentials(
            connection_string="connection_string", account_url="account"
        ).get_client()


def test_get_service_client_no_conn_str(account_url):
    client = AzureBlobStorageCredentials(account_url=account_url).get_client()
    assert isinstance(client, BlobServiceClient)


def test_get_blob_container_client_no_conn_str(account_url):
    client = AzureBlobStorageCredentials(account_url=account_url).get_container_client(
        "container"
    )
    assert isinstance(client, ContainerClient)
    client.container_name == "container"


def test_get_blob_client_no_conn_str(account_url):
    client = AzureBlobStorageCredentials(account_url=account_url).get_blob_client(
        "container", "blob"
    )
    assert isinstance(client, BlobClient)
    client.container_name == "container"
    client.blob_name == "blob"


def test_get_cosmos_client(cosmos_connection_string):
    @flow
    def test_flow():
        client = AzureCosmosDbCredentials(
            connection_string=cosmos_connection_string
        ).get_client()
        assert isinstance(client, CosmosClientMock)

    test_flow()


def test_get_database_client(cosmos_connection_string):
    @flow
    def test_flow():
        client = AzureCosmosDbCredentials(
            connection_string=cosmos_connection_string
        ).get_database_client("database")
        assert client.database == "database"

    test_flow()


def test_get_cosmos_container_client(cosmos_connection_string):
    @flow
    def test_flow():
        client = AzureCosmosDbCredentials(
            connection_string=cosmos_connection_string
        ).get_container_client("container", "database")
        assert client.container == "container"

    test_flow()


def test_get_workspace(monkeypatch):
    monkeypatch.setattr("prefect_azure.credentials.Workspace", MagicMock)

    @flow
    def test_flow():
        workspace = AzureMlCredentials(
            tenant_id="tenant_id",
            service_principal_id="service_principal_id",
            service_principal_password="service_principal_password",
            subscription_id="subscription_id",
            resource_group="resource_group",
            workspace_name="workspace_name",
        ).get_workspace()
        assert isinstance(workspace, MagicMock)

    test_flow()
