from unittest.mock import MagicMock, patch

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


class TestAzureBlobStorageCredentialsSPN:
    """Tests for Service Principal Name (SPN) authentication in AzureBlobStorageCredentials."""

    def test_spn_credentials_with_all_fields(self, account_url: str) -> None:
        """Test that SPN credentials work when all three fields are provided."""
        creds = AzureBlobStorageCredentials(
            account_url=account_url,
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )
        assert creds.tenant_id == "test-tenant-id"
        assert creds.client_id == "test-client-id"
        assert creds.client_secret.get_secret_value() == "test-client-secret"

    def test_spn_credentials_missing_tenant_id(self, account_url: str) -> None:
        """Test validation error when tenant_id is missing."""
        with pytest.raises(
            ValueError,
            match="If any of `tenant_id`, `client_id`, or `client_secret` are provided",
        ):
            AzureBlobStorageCredentials(
                account_url=account_url,
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
            )

    def test_spn_credentials_missing_client_id(self, account_url: str) -> None:
        """Test validation error when client_id is missing."""
        with pytest.raises(
            ValueError,
            match="If any of `tenant_id`, `client_id`, or `client_secret` are provided",
        ):
            AzureBlobStorageCredentials(
                account_url=account_url,
                tenant_id="test-tenant-id",
                client_secret=SecretStr("test-client-secret"),
            )

    def test_spn_credentials_missing_client_secret(self, account_url: str) -> None:
        """Test validation error when client_secret is missing."""
        with pytest.raises(
            ValueError,
            match="If any of `tenant_id`, `client_id`, or `client_secret` are provided",
        ):
            AzureBlobStorageCredentials(
                account_url=account_url,
                tenant_id="test-tenant-id",
                client_id="test-client-id",
            )

    def test_spn_credentials_require_account_url(self) -> None:
        """Test validation error when SPN fields are provided without account_url."""
        with pytest.raises(
            ValueError,
            match="If service principal credentials are provided.*account_url",
        ):
            AzureBlobStorageCredentials(
                connection_string="fake-connection-string",
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
            )

    def test_spn_credentials_cannot_use_connection_string(self) -> None:
        """Test validation error when SPN fields are used with connection_string.

        Note: This test verifies that SPN + connection_string is rejected.
        The validation fails because SPN requires account_url, which effectively
        prevents using SPN with connection_string.
        """
        with pytest.raises(
            ValueError,
            match="If service principal credentials are provided.*account_url",
        ):
            AzureBlobStorageCredentials(
                connection_string="fake-connection-string",
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret=SecretStr("test-client-secret"),
            )

    def test_spn_get_client_uses_client_secret_credential(
        self, account_url: str
    ) -> None:
        """Test that get_client uses ClientSecretCredential when SPN fields are provided."""
        creds = AzureBlobStorageCredentials(
            account_url=account_url,
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        with patch(
            "prefect_azure.credentials.AClientSecretCredential"
        ) as mock_credential:
            mock_credential.return_value = MagicMock()
            client = creds.get_client()

            mock_credential.assert_called_once_with(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )
            assert isinstance(client, BlobServiceClient)

    def test_spn_get_blob_client_uses_client_secret_credential(
        self, account_url: str
    ) -> None:
        """Test that get_blob_client uses ClientSecretCredential when SPN fields are provided."""
        creds = AzureBlobStorageCredentials(
            account_url=account_url,
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        with patch(
            "prefect_azure.credentials.AClientSecretCredential"
        ) as mock_credential:
            mock_credential.return_value = MagicMock()
            client = creds.get_blob_client("container", "blob")

            mock_credential.assert_called_once_with(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )
            assert isinstance(client, BlobClient)

    def test_spn_get_container_client_uses_client_secret_credential(
        self, account_url: str
    ) -> None:
        """Test that get_container_client uses ClientSecretCredential when SPN fields are provided."""
        creds = AzureBlobStorageCredentials(
            account_url=account_url,
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
        )

        with patch(
            "prefect_azure.credentials.AClientSecretCredential"
        ) as mock_credential:
            mock_credential.return_value = MagicMock()
            client = creds.get_container_client("container")

            mock_credential.assert_called_once_with(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )
            assert isinstance(client, ContainerClient)
