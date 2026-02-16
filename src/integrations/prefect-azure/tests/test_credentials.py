from unittest.mock import MagicMock

import pytest
from azure.storage.blob.aio import BlobClient, BlobServiceClient, ContainerClient
from conftest import CosmosClientMock
from prefect_azure.credentials import (
    AzureBlobStorageCredentials,
    AzureCosmosDbCredentials,
    AzureDevopsCredentials,
    AzureMlCredentials,
)
from pydantic import SecretStr

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
    assert client.container_name == "container"


def test_get_blob_client(blob_connection_string):
    @flow
    def test_flow():
        client = AzureBlobStorageCredentials(
            connection_string=blob_connection_string
        ).get_blob_client("container", "blob")
        return client

    client = test_flow()
    assert isinstance(client, BlobClient)
    assert client.container_name == "container"
    assert client.blob_name == "blob"


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
    assert client.container_name == "container"


def test_get_blob_client_no_conn_str(account_url):
    client = AzureBlobStorageCredentials(account_url=account_url).get_blob_client(
        "container", "blob"
    )
    assert isinstance(client, BlobClient)
    assert client.container_name == "container"
    assert client.blob_name == "blob"


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
            service_principal_password=SecretStr("service_principal_password"),
            subscription_id="subscription_id",
            resource_group="resource_group",
            workspace_name="workspace_name",
        ).get_workspace()
        assert isinstance(workspace, MagicMock)

    test_flow()


def test_get_azuredevops_auth_header_valid_token():
    @flow
    def test_flow():
        creds = AzureDevopsCredentials(token=SecretStr("fake-pat"))
        auth_header = creds.get_auth_header()

        import base64

        expected_token = base64.b64encode(b":fake-pat").decode()
        assert auth_header == {"Authorization": f"Basic {expected_token}"}

    test_flow()


def test_get_azuredevops_auth_header_missing_token():
    @flow
    def test_flow():
        creds = AzureDevopsCredentials(token=None)
        creds.get_auth_header()

    with pytest.raises(ValueError, match="Azure DevOps Personal Access Token.*not set"):
        test_flow()


# Service Principal Authentication Tests for AzureBlobStorageCredentials


def test_spn_requires_all_fields():
    """Test that partial SPN credentials raise an error."""
    with pytest.raises(
        ValueError,
        match="If any of `client_id`, `tenant_id`, or `client_secret` are provided",
    ):
        AzureBlobStorageCredentials(
            account_url="https://test.blob.core.windows.net",
            client_id="client-id",
            # Missing tenant_id and client_secret
        )


def test_spn_requires_account_url():
    """Test that SPN credentials without account_url raise an error."""
    with pytest.raises(
        ValueError, match="Must provide `account_url` when using service principal"
    ):
        AzureBlobStorageCredentials(
            client_id="client-id",
            tenant_id="tenant-id",
            client_secret=SecretStr("client-secret"),
        )


def test_spn_cannot_combine_with_connection_string():
    """Test that SPN credentials cannot be combined with connection string."""
    with pytest.raises(
        ValueError,
        match="Cannot provide both a connection string and service principal",
    ):
        AzureBlobStorageCredentials(
            account_url="https://test.blob.core.windows.net",
            connection_string="connection-string",
            client_id="client-id",
            tenant_id="tenant-id",
            client_secret=SecretStr("client-secret"),
        )


def test_spn_get_service_client(account_url, monkeypatch):
    """Test that SPN credentials work with get_client."""
    mock_client_secret_credential = MagicMock()
    monkeypatch.setattr(
        "prefect_azure.credentials.AClientSecretCredential",
        mock_client_secret_credential,
    )

    creds = AzureBlobStorageCredentials(
        account_url=account_url,
        client_id="client-id",
        tenant_id="tenant-id",
        client_secret=SecretStr("client-secret"),
    )
    client = creds.get_client()
    assert isinstance(client, BlobServiceClient)
    mock_client_secret_credential.assert_called_once_with(
        tenant_id="tenant-id",
        client_id="client-id",
        client_secret="client-secret",
    )


def test_spn_get_blob_client(account_url, monkeypatch):
    """Test that SPN credentials work with get_blob_client."""
    mock_client_secret_credential = MagicMock()
    monkeypatch.setattr(
        "prefect_azure.credentials.AClientSecretCredential",
        mock_client_secret_credential,
    )

    creds = AzureBlobStorageCredentials(
        account_url=account_url,
        client_id="client-id",
        tenant_id="tenant-id",
        client_secret=SecretStr("client-secret"),
    )
    client = creds.get_blob_client("container", "blob")
    assert isinstance(client, BlobClient)
    assert client.container_name == "container"
    assert client.blob_name == "blob"
    mock_client_secret_credential.assert_called_once_with(
        tenant_id="tenant-id",
        client_id="client-id",
        client_secret="client-secret",
    )


def test_spn_get_container_client(account_url, monkeypatch):
    """Test that SPN credentials work with get_container_client."""
    mock_client_secret_credential = MagicMock()
    monkeypatch.setattr(
        "prefect_azure.credentials.AClientSecretCredential",
        mock_client_secret_credential,
    )

    creds = AzureBlobStorageCredentials(
        account_url=account_url,
        client_id="client-id",
        tenant_id="tenant-id",
        client_secret=SecretStr("client-secret"),
    )
    client = creds.get_container_client("container")
    assert isinstance(client, ContainerClient)
    assert client.container_name == "container"
    mock_client_secret_credential.assert_called_once_with(
        tenant_id="tenant-id",
        client_id="client-id",
        client_secret="client-secret",
    )


def test_spn_credential_reuse(account_url, monkeypatch):
    """Test that the credential is reused across multiple client calls."""
    mock_client_secret_credential = MagicMock()
    monkeypatch.setattr(
        "prefect_azure.credentials.AClientSecretCredential",
        mock_client_secret_credential,
    )

    creds = AzureBlobStorageCredentials(
        account_url=account_url,
        client_id="client-id",
        tenant_id="tenant-id",
        client_secret=SecretStr("client-secret"),
    )

    # Make multiple client calls
    creds.get_client()
    creds.get_blob_client("container", "blob")
    creds.get_container_client("container")

    # Credential should only be created once
    mock_client_secret_credential.assert_called_once()
