from unittest.mock import MagicMock

import cloudpickle
import pytest

import prefect
from prefect.client import Client
from prefect.utilities.configuration import set_temporary_config
from prefect.engine.results import AzureResult

pytest.importorskip("azure.storage.blob")


class TestAzureResult:
    @pytest.fixture
    def azure_client(self, monkeypatch):
        connection = MagicMock()
        azure = MagicMock(from_connection_string=connection)
        monkeypatch.setattr("azure.storage.blob.BlobServiceClient", azure)
        yield connection

    def test_azure_init(self, azure_client):
        result = AzureResult(container="bob", connection_string="conn")
        assert result.value == None
        assert result.connection_string == "conn"
        assert result.connection_string_secret == None
        assert azure_client.called is False
        result.initialize_service()
        assert azure_client.called is True

    def test_azure_init_with_values(self, azure_client):
        result = AzureResult(container="bob", connection_string="conn", value=3)
        assert result.value == 3

    def test_azure_init_connection_string(self, azure_client):
        result = AzureResult(container="bob", connection_string="con1")
        result.initialize_service()
        azure_client.assert_called_with(conn_str="con1")

        with prefect.context({"secrets": {"test": "con2"}}):
            result = AzureResult(container="bob", connection_string_secret="test")
            result.initialize_service()
            azure_client.assert_called_with(conn_str="con2")

    def test_azure_writes_to_blob_using_rendered_template_name(self, monkeypatch):
        client = MagicMock(upload_blob=MagicMock())
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        monkeypatch.setattr(
            "prefect.engine.results.azure_result.AzureResult.service", service
        )

        result = AzureResult(container="foo", location="{thing}/here.txt")
        new_result = result.write("so-much-data", thing=42)

        assert new_result.location == "42/here.txt"
        assert client.upload_blob.called
        assert service.get_blob_client.call_args[1]["blob"] == "42/here.txt"
        assert service.get_blob_client.call_args[1]["container"] == "foo"

    def test_azure_reads_and_updates_location(self, monkeypatch):
        client = MagicMock(download_blob=MagicMock(return_value=""))
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        monkeypatch.setattr(
            "prefect.engine.results.azure_result.AzureResult.service", service
        )

        result = AzureResult(container="foo", location="{thing}/here.txt")
        new_result = result.read("path/to/my/stuff.txt")

        assert new_result.location == "path/to/my/stuff.txt"
        assert new_result.value is None

    def test_azure_writes_binary_string(self, monkeypatch):
        client = MagicMock(upload_blob=MagicMock())
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        monkeypatch.setattr(
            "prefect.engine.results.azure_result.AzureResult.service", service
        )

        result = AzureResult(container="foo", location="nothing/here.txt")
        new_result = result.write(None)
        assert client.upload_blob.called
        assert isinstance(client.upload_blob.call_args[0][0], str)

    def test_azure_result_is_pickleable(self, azure_client):
        result = AzureResult("foo")
        res = cloudpickle.loads(cloudpickle.dumps(result))
        assert isinstance(res, AzureResult)

    def test_azure_exists(self, monkeypatch):
        client = MagicMock(get_blob_properties=MagicMock())
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        monkeypatch.setattr(
            "prefect.engine.results.azure_result.AzureResult.service", service
        )

        result = AzureResult(container="foo", location="{thing}/here.txt")
        assert result.exists("44.txt") is True

    def test_azure_does_not_exists(self, monkeypatch):
        from azure.core.exceptions import ResourceNotFoundError

        client = MagicMock(
            get_blob_properties=MagicMock(side_effect=ResourceNotFoundError)
        )
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        monkeypatch.setattr(
            "prefect.engine.results.azure_result.AzureResult.service", service
        )

        result = AzureResult(container="foo", location="{thing}/here.txt")
        assert result.exists("44.txt") is False
