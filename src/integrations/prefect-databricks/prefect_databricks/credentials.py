"""Credential classes used to perform authenticated interactions with Databricks"""

from typing import Any, Dict, Optional

from httpx import AsyncClient

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, SecretStr
else:
    from pydantic import Field, SecretStr

from prefect.blocks.core import Block


class DatabricksCredentials(Block):
    """
    Block used to manage Databricks authentication.

    Attributes:
        databricks_instance:
            Databricks instance used in formatting the endpoint URL.
        token: The token to authenticate with Databricks.
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
    token: SecretStr = Field(
        default=..., description="The token to authenticate with Databricks."
    )
    client_kwargs: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional keyword arguments to pass to AsyncClient."
    )

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
        client_kwargs["headers"] = {
            "Authorization": f"Bearer {self.token.get_secret_value()}"
        }
        client = AsyncClient(base_url=base_url, **client_kwargs)
        return client
