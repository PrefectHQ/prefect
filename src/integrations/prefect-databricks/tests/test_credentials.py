from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, Response
from prefect_databricks import DatabricksCredentials


class TestDatabricksCredentialsPATAuth:
    """Tests for Personal Access Token (PAT) authentication."""

    def test_get_client_with_pat(self):
        """Test that get_client works with PAT authentication."""
        client = DatabricksCredentials(
            databricks_instance="databricks_instance", token="token_value"
        ).get_client()
        assert isinstance(client, AsyncClient)
        assert client.headers["authorization"] == "Bearer token_value"

    def test_backward_compatibility_with_token(self):
        """Test backward compatibility - existing PAT-based credentials work unchanged."""
        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            token="my-pat-token",
        )
        assert credentials.token.get_secret_value() == "my-pat-token"
        assert credentials.client_id is None
        assert credentials.client_secret is None
        assert credentials.tenant_id is None

    def test_get_client_with_pat_and_client_kwargs(self):
        """Test that client_kwargs are passed through correctly with PAT auth."""
        credentials = DatabricksCredentials(
            databricks_instance="databricks_instance",
            token="token_value",
            client_kwargs={"timeout": 30.0},
        )
        client = credentials.get_client()
        assert isinstance(client, AsyncClient)
        assert client.headers["authorization"] == "Bearer token_value"


class TestDatabricksCredentialsServicePrincipalAuth:
    """Tests for Service Principal (OAuth 2.0) authentication."""

    def test_service_principal_credentials_creation(self):
        """Test that service principal credentials can be created."""
        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )
        assert credentials.client_id == "my-client-id"
        assert credentials.client_secret.get_secret_value() == "my-client-secret"
        assert credentials.token is None

    def test_service_principal_with_tenant_id(self):
        """Test service principal credentials with tenant_id for Azure Databricks."""
        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
            tenant_id="my-tenant-id",
        )
        assert credentials.tenant_id == "my-tenant-id"

    @patch("prefect_databricks.credentials.Client")
    def test_get_client_with_azure_ad_service_principal(self, mock_client_class):
        """Test that get_client uses Azure AD endpoint when tenant_id is provided."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "azure-ad-access-token",
            "expires_in": 3600,
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        credentials = DatabricksCredentials(
            databricks_instance="adb-123456789.7.azuredatabricks.net",
            client_id="my-azure-client-id",
            client_secret="my-azure-client-secret",
            tenant_id="my-tenant-id",
        )
        client = credentials.get_client()

        assert isinstance(client, AsyncClient)
        assert client.headers["authorization"] == "Bearer azure-ad-access-token"

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert (
            call_args[0][0]
            == "https://login.microsoftonline.com/my-tenant-id/oauth2/v2.0/token"
        )
        assert call_args[1]["data"]["grant_type"] == "client_credentials"
        assert call_args[1]["data"]["client_id"] == "my-azure-client-id"
        assert call_args[1]["data"]["client_secret"] == "my-azure-client-secret"
        assert (
            call_args[1]["data"]["scope"]
            == "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"
        )

    @patch("prefect_databricks.credentials.Client")
    def test_get_client_with_service_principal(self, mock_client_class):
        """Test that get_client works with service principal authentication."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "oauth-access-token",
            "expires_in": 3600,
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )
        client = credentials.get_client()

        assert isinstance(client, AsyncClient)
        assert client.headers["authorization"] == "Bearer oauth-access-token"

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "https://dbc-test.cloud.databricks.com/oidc/v1/token"
        assert call_args[1]["data"]["grant_type"] == "client_credentials"
        assert call_args[1]["data"]["scope"] == "all-apis"

    @patch("prefect_databricks.credentials.Client")
    def test_oauth_token_caching(self, mock_client_class):
        """Test that OAuth tokens are cached and reused."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "oauth-access-token",
            "expires_in": 3600,
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )

        credentials.get_client()
        credentials.get_client()
        credentials.get_client()

        assert mock_client_instance.post.call_count == 1

    @patch("prefect_databricks.credentials.time")
    @patch("prefect_databricks.credentials.Client")
    def test_oauth_token_refresh_when_expired(self, mock_client_class, mock_time):
        """Test that OAuth tokens are refreshed when expired."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "oauth-access-token",
            "expires_in": 3600,
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        current_time = 1000.0
        mock_time.time.return_value = current_time

        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )

        credentials.get_client()
        assert mock_client_instance.post.call_count == 1

        mock_time.time.return_value = current_time + 3600
        credentials.get_client()
        assert mock_client_instance.post.call_count == 2

    @patch("prefect_databricks.credentials.Client")
    def test_oauth_token_acquisition_failure(self, mock_client_class):
        """Test that OAuth token acquisition failure raises RuntimeError."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )

        with pytest.raises(RuntimeError, match="Failed to acquire OAuth token"):
            credentials.get_client()

    @patch("prefect_databricks.credentials.Client")
    def test_oauth_token_response_missing_access_token(self, mock_client_class):
        """Test that missing access_token in response raises user-friendly error."""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Some error occurred",
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        credentials = DatabricksCredentials(
            databricks_instance="dbc-test.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )

        with pytest.raises(
            RuntimeError, match="OAuth token response did not contain an access_token"
        ):
            credentials.get_client()


class TestDatabricksCredentialsValidation:
    """Tests for authentication validation."""

    def test_validation_error_no_auth_provided(self):
        """Test that validation fails when no authentication is provided."""
        with pytest.raises(
            ValueError,
            match="Must provide either `token` for PAT authentication",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
            )

    def test_validation_error_both_auth_methods(self):
        """Test that validation fails when both PAT and service principal are provided."""
        with pytest.raises(
            ValueError,
            match="Cannot provide both `token` and service principal credentials",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                token="my-token",
                client_id="my-client-id",
                client_secret="my-client-secret",
            )

    def test_validation_error_partial_service_principal_client_id_only(self):
        """Test that validation fails when only client_id is provided."""
        with pytest.raises(
            ValueError,
            match="both `client_id` and `client_secret` must be provided",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                client_id="my-client-id",
            )

    def test_validation_error_partial_service_principal_client_secret_only(self):
        """Test that validation fails when only client_secret is provided."""
        with pytest.raises(
            ValueError,
            match="both `client_id` and `client_secret` must be provided",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                client_secret="my-client-secret",
            )

    def test_validation_error_token_with_client_id(self):
        """Test that validation fails when token is provided with client_id."""
        with pytest.raises(
            ValueError,
            match="Cannot provide both `token` and service principal credentials",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                token="my-token",
                client_id="my-client-id",
            )

    def test_validation_error_token_with_client_secret(self):
        """Test that validation fails when token is provided with client_secret."""
        with pytest.raises(
            ValueError,
            match="Cannot provide both `token` and service principal credentials",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                token="my-token",
                client_secret="my-client-secret",
            )

    def test_validation_error_empty_string_token(self):
        """Test that validation fails when token is an empty string."""
        with pytest.raises(
            ValueError,
            match="Must provide either `token` for PAT authentication",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                token="",
            )

    def test_validation_error_empty_string_client_id(self):
        """Test that validation fails when client_id is an empty string."""
        with pytest.raises(
            ValueError,
            match="both `client_id` and `client_secret` must be provided",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                client_id="",
                client_secret="my-client-secret",
            )

    def test_validation_error_empty_string_client_secret(self):
        """Test that validation fails when client_secret is an empty string."""
        with pytest.raises(
            ValueError,
            match="both `client_id` and `client_secret` must be provided",
        ):
            DatabricksCredentials(
                databricks_instance="dbc-test.cloud.databricks.com",
                client_id="my-client-id",
                client_secret="",
            )


def test_databricks_credentials_get_client():
    """Legacy test for backward compatibility."""
    client = DatabricksCredentials(
        databricks_instance="databricks_instance", token="token_value"
    ).get_client()
    assert isinstance(client, AsyncClient)
    assert client.headers["authorization"] == "Bearer token_value"
