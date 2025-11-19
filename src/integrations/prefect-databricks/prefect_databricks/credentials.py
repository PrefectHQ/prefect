"""Credential classes used to perform authenticated interactions with Databricks"""

from typing import Any, Dict, Optional

import httpx
from httpx import AsyncClient
from pydantic import Field, SecretStr, model_validator

from prefect.blocks.core import Block


class DatabricksCredentials(Block):
    """
    Block used to manage Databricks authentication.

    Attributes:
        databricks_instance:
            Databricks instance used in formatting the endpoint URL.
        token: The token to authenticate with Databricks.
        client_id: The service principal client ID.
        client_secret: The service principal client secret.
        tenant_id: The Azure tenant ID (optional, for Azure Databricks).
        client_kwargs: Additional keyword arguments to pass to AsyncClient.

    Examples:
        Load stored Databricks credentials:
        ```python
        from prefect_databricks import DatabricksCredentials
        databricks_credentials_block = DatabricksCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Databricks Credentials"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5GTHI1PH2dTiantfps6Fnc/1c750fab7f4c14ea1b93a62b9fea6a94/databricks_logo_icon_170295.png?h=250"  # noqa

    databricks_instance: str = Field(
        default=...,
        description="Databricks instance used in formatting the endpoint URL.",
    )
    token: Optional[SecretStr] = Field(
        default=None, description="The token to authenticate with Databricks."
    )
    client_id: Optional[SecretStr] = Field(
        default=None,
        description="The service principal client ID. Required if token is not provided.",
    )
    client_secret: Optional[SecretStr] = Field(
        default=None,
        description="The service principal client secret. Required if token is not provided.",
    )
    tenant_id: Optional[str] = Field(
        default=None,
        description="The Azure tenant ID (optional, for Azure Databricks).",
    )
    client_kwargs: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional keyword arguments to pass to AsyncClient."
    )

    @model_validator(mode="after")
    def validate_credentials(self):
        if not self.token and not (self.client_id and self.client_secret):
            raise ValueError(
                "Either 'token' or both 'client_id' and 'client_secret' must be provided."
            )
        return self

    def get_access_token(self) -> str:
        """
        Gets an access token for Databricks.

        Returns:
            The access token.
        """
        if self.token:
            return self.token.get_secret_value()

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Client credentials are required if token is not provided."
            )

        # Service Principal Authentication
        if self.tenant_id:
            # Azure Databricks
            token_url = (
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            )
            # Resource ID for Azure Databricks is standard
            scope = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id.get_secret_value(),
                "client_secret": self.client_secret.get_secret_value(),
                "scope": scope,
            }
        else:
            # AWS/GCP Databricks
            token_url = f"https://{self.databricks_instance}/oidc/v1/token"
            data = {
                "grant_type": "client_credentials",
                "scope": "all-apis",
            }

        # Making the request
        auth: Any = None
        if not self.tenant_id:
            # Standard Databricks OAuth uses Basic Auth with client credentials
            auth = (
                self.client_id.get_secret_value(),
                self.client_secret.get_secret_value(),
            )

        with httpx.Client() as client:
            response = client.post(token_url, data=data, auth=auth)
            response.raise_for_status()
            return response.json()["access_token"]

    def get_client(self) -> AsyncClient:
        """
        Gets an Databricks REST AsyncClient.

        Returns:
            An Databricks REST AsyncClient.

        Example:
            Gets a Databricks REST AsyncClient.
            ```python
            from prefect import flow
            from prefect_databricks import DatabricksCredentials

            @flow
            def example_get_client_flow():
                token = "consumer_key"
                databricks_credentials = DatabricksCredentials(token=token)
                client = databricks_credentials.get_client()
                return client

            example_get_client_flow()
            ```
        """
        base_url = f"https://{self.databricks_instance}/api/"

        client_kwargs = self.client_kwargs or {}
        token = self.get_access_token()
        client_kwargs["headers"] = {"Authorization": f"Bearer {token}"}
        client = AsyncClient(base_url=base_url, **client_kwargs)
        return client
