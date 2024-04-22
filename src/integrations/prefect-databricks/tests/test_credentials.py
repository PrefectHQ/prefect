from httpx import AsyncClient
from prefect_databricks import DatabricksCredentials


def test_databricks_credentials_get_client():
    client = DatabricksCredentials(
        databricks_instance="databricks_instance", token="token_value"
    ).get_client()
    assert isinstance(client, AsyncClient)
    assert client.headers["authorization"] == "Bearer token_value"
