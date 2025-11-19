from httpx import AsyncClient
import httpx
import pytest
import respx
from pydantic import SecretStr
from prefect_databricks import DatabricksCredentials


def test_databricks_credentials_get_client():
    client = DatabricksCredentials(
        databricks_instance="databricks_instance", token="token_value"
    ).get_client()
    assert isinstance(client, AsyncClient)
    assert client.headers["authorization"] == "Bearer token_value"


@pytest.mark.asyncio
async def test_databricks_credentials_with_service_principal_aws():
    with respx.mock(base_url="https://my-databricks-instance.com") as respx_mock:
        # Mock the token endpoint
        respx_mock.post("/oidc/v1/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "mock_oauth_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )

        creds = DatabricksCredentials(
            databricks_instance="my-databricks-instance.com",
            client_id=SecretStr("my-client-id"),
            client_secret=SecretStr("my-client-secret"),
        )

        client = creds.get_client()
        assert client.headers["authorization"] == "Bearer mock_oauth_token"
        assert str(client.base_url) == "https://my-databricks-instance.com/api/"


@pytest.mark.asyncio
async def test_databricks_credentials_with_service_principal_azure():
    tenant_id = "my-tenant-id"
    with respx.mock() as respx_mock:
        # Mock the Azure token endpoint
        respx_mock.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "mock_azure_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )

        creds = DatabricksCredentials(
            databricks_instance="adb-123.4.azuredatabricks.net",
            client_id=SecretStr("my-client-id"),
            client_secret=SecretStr("my-client-secret"),
            tenant_id=tenant_id,
        )

        client = creds.get_client()
        assert client.headers["authorization"] == "Bearer mock_azure_token"
        assert str(client.base_url) == "https://adb-123.4.azuredatabricks.net/api/"


def test_validation_error_missing_creds():
    with pytest.raises(
        ValueError,
        match="Either 'token' or both 'client_id' and 'client_secret' must be provided",
    ):
        DatabricksCredentials(databricks_instance="my-databricks-instance.com")
