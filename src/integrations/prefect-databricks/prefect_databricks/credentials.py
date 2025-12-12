"""Credential classes used to perform authenticated interactions with Databricks"""

import base64
import time
from typing import Any, Dict, Optional

from httpx import AsyncClient, Client
from pydantic import Field, PrivateAttr, SecretStr, model_validator

from prefect.blocks.core import Block


class DatabricksCredentials(Block):
    """
    Block used to manage Databricks authentication.

    Supports two authentication methods:
    1. Personal Access Token (PAT): Provide a `token` field.
    2. Service Principal (OAuth 2.0): Provide `client_id`, `client_secret`,
       and optionally `tenant_id` for Azure Databricks.

    Attributes:
        databricks_instance:
            Databricks instance used in formatting the endpoint URL.
        token: The token to authenticate with Databricks (for PAT authentication).
        client_id: The service principal client ID (for OAuth authentication).
        client_secret: The service principal client secret (for OAuth authentication).
        tenant_id: The tenant ID for Azure Databricks (optional, for OAuth authentication).
        client_kwargs: Additional keyword arguments to pass to AsyncClient.

    Examples:
        Load stored Databricks credentials using PAT:
        ```python
        from prefect_databricks import DatabricksCredentials

        databricks_credentials_block = DatabricksCredentials.load("BLOCK_NAME")
        ```

        Using service principal authentication:
        ```python
        from prefect_databricks import DatabricksCredentials

        credentials = DatabricksCredentials(
            databricks_instance="dbc-abc123-def4.cloud.databricks.com",
            client_id="my-client-id",
            client_secret="my-client-secret",
        )
        client = credentials.get_client()
        ```
    """

    _block_type_name = "Databricks Credentials"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5GTHI1PH2dTiantfps6Fnc/1c750fab7f4c14ea1b93a62b9fea6a94/databricks_logo_icon_170295.png?h=250"  # noqa

    _cached_token: Optional[str] = PrivateAttr(default=None)
    _token_expiry: Optional[float] = PrivateAttr(default=None)

    databricks_instance: str = Field(
        default=...,
        description="Databricks instance used in formatting the endpoint URL.",
    )
    token: Optional[SecretStr] = Field(
        default=None,
        description="The token to authenticate with Databricks (for PAT authentication).",
    )
    client_id: Optional[str] = Field(
        default=None,
        title="Client ID",
        description=(
            "The service principal client ID for OAuth authentication. "
            "If provided, `client_secret` must also be provided."
        ),
    )
    client_secret: Optional[SecretStr] = Field(
        default=None,
        description=(
            "The service principal client secret for OAuth authentication. "
            "If provided, `client_id` must also be provided."
        ),
    )
    tenant_id: Optional[str] = Field(
        default=None,
        title="Tenant ID",
        description=(
            "The tenant ID for Azure Databricks. "
            "Optional, only needed for Azure Databricks service principal authentication."
        ),
    )
    client_kwargs: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional keyword arguments to pass to AsyncClient."
    )

    @model_validator(mode="before")
    @classmethod
    def validate_auth_method(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates that either PAT or service principal authentication is configured,
        but not both.

        Valid configurations:
        1. token only (PAT authentication)
        2. client_id + client_secret (service principal authentication)
        3. client_id + client_secret + tenant_id (Azure service principal authentication)
        """
        token = values.get("token")
        client_id = values.get("client_id")
        client_secret = values.get("client_secret")

        # Guard against both None and empty strings
        has_token = token is not None and token != ""
        has_client_id = client_id is not None and client_id != ""
        has_client_secret = client_secret is not None and client_secret != ""

        has_any_sp = has_client_id or has_client_secret
        has_all_sp = has_client_id and has_client_secret

        if has_token and has_any_sp:
            raise ValueError(
                "Cannot provide both `token` and service principal credentials "
                "(`client_id`, `client_secret`). Use one authentication method."
            )

        if has_any_sp and not has_all_sp:
            raise ValueError(
                "If using service principal authentication, both `client_id` and "
                "`client_secret` must be provided."
            )

        if not has_token and not has_all_sp:
            raise ValueError(
                "Must provide either `token` for PAT authentication or "
                "`client_id` and `client_secret` for service principal authentication."
            )

        return values

    def _get_oauth_token(self) -> str:
        """
        Acquires an OAuth token using the service principal credentials.

        Implements token caching and automatic refresh when the token is expired
        or about to expire (within 60 seconds of expiration).

        For Azure Databricks with a tenant_id, uses Microsoft Entra ID (Azure AD)
        token endpoint. For Databricks-managed service principals (no tenant_id),
        uses the Databricks OIDC endpoint.

        Returns:
            A valid OAuth access token.

        Raises:
            RuntimeError: If token acquisition fails.
        """
        if (
            self._cached_token is not None
            and self._token_expiry is not None
            and time.time() < self._token_expiry - 60
        ):
            return self._cached_token

        if self.tenant_id is not None:
            # Azure AD (Microsoft Entra ID) authentication
            token_url = (
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            )
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }
            # Azure Databricks resource ID
            azure_databricks_resource_id = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret.get_secret_value(),
                "scope": f"{azure_databricks_resource_id}/.default",
            }
        else:
            # Databricks-managed service principal authentication
            token_url = f"https://{self.databricks_instance}/oidc/v1/token"
            credentials = f"{self.client_id}:{self.client_secret.get_secret_value()}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "grant_type": "client_credentials",
                "scope": "all-apis",
            }

        with Client() as client:
            response = client.post(token_url, headers=headers, data=data)

            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to acquire OAuth token: {response.status_code} - {response.text}"
                )

            token_data = response.json()
            if "access_token" not in token_data:
                raise RuntimeError(
                    "OAuth token response did not contain an access_token. "
                    f"Response: {token_data}"
                )
            self._cached_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in

            return self._cached_token

    def get_client(self) -> AsyncClient:
        """
        Gets a Databricks REST AsyncClient.

        Returns:
            A Databricks REST AsyncClient.

        Example:
            Gets a Databricks REST AsyncClient using PAT authentication.
            ```python
            from prefect import flow
            from prefect_databricks import DatabricksCredentials

            @flow
            def example_get_client_flow():
                databricks_credentials = DatabricksCredentials(
                    databricks_instance="dbc-abc123-def4.cloud.databricks.com",
                    token="my-token",
                )
                client = databricks_credentials.get_client()
                return client

            example_get_client_flow()
            ```

            Gets a Databricks REST AsyncClient using service principal authentication.
            ```python
            from prefect import flow
            from prefect_databricks import DatabricksCredentials

            @flow
            def example_get_client_flow():
                databricks_credentials = DatabricksCredentials(
                    databricks_instance="dbc-abc123-def4.cloud.databricks.com",
                    client_id="my-client-id",
                    client_secret="my-client-secret",
                )
                client = databricks_credentials.get_client()
                return client

            example_get_client_flow()
            ```
        """
        base_url = f"https://{self.databricks_instance}/api/"

        if self.client_id is not None:
            auth_token = self._get_oauth_token()
        else:
            auth_token = self.token.get_secret_value()

        client_kwargs = self.client_kwargs or {}
        client_kwargs["headers"] = {"Authorization": f"Bearer {auth_token}"}
        client = AsyncClient(base_url=base_url, **client_kwargs)
        return client
