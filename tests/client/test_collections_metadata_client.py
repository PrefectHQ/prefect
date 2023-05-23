from unittest.mock import patch

from prefect.client.collections import (
    get_collections_metadata_client,
)
from prefect.client.cloud import CloudClient
from prefect.client.orchestration import PrefectClient, ServerType


class TestGetCollectionsMetadataClient:
    @patch("prefect.client.collections.get_client")
    @patch("prefect.client.collections.get_cloud_client")
    async def test_returns_cloud_client_when_server_type_is_cloud(
        self, mock_get_cloud_client, mock_get_client
    ):
        mock_get_client.return_value.server_type = ServerType.CLOUD
        mock_get_cloud_client.return_value = CloudClient(
            host="test-host", api_key="test-api-key"
        )

        result = get_collections_metadata_client()

        mock_get_client.assert_called_once()
        mock_get_cloud_client.assert_called_once()
        assert isinstance(result, CloudClient)

    @patch("prefect.client.collections.get_client")
    async def test_returns_orchestration_client_when_server_type_is_server(
        self, mock_get_client
    ):
        mock_get_client.return_value = PrefectClient(api="test-api")
        mock_get_client.return_value.server_type = ServerType.SERVER

        result = get_collections_metadata_client()

        mock_get_client.assert_called_once()
        assert isinstance(result, PrefectClient)

    @patch("prefect.client.collections.get_client")
    async def test_returns_orchestration_client_when_server_type_is_ephemeral(
        self, mock_get_client
    ):
        mock_get_client.return_value = PrefectClient(api="test-api")
        mock_get_client.return_value.server_type = ServerType.EPHEMERAL

        result = get_collections_metadata_client()

        mock_get_client.assert_called_once()
        assert isinstance(result, PrefectClient)
