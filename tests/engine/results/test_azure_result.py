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
        credential = MagicMock(return_value="mocked!")
        monkeypatch.setattr("azure.identity.DefaultAzureCredential", credential)
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

    def test_azure_init_without_connection_string(self, azure_client):
        result = AzureResult(container="bob", connection_string=None)
        with pytest.raises(ValueError):
            result.initialize_service()

    def test_azure_init_connection_string(self, azure_client):
        result = AzureResult(container="bob", connection_string="con1;AccountKey=abc")
        result.initialize_service()
        azure_client.assert_called_with(conn_str="con1;AccountKey=abc", credential=None)

        with prefect.context({"secrets": {"test": "con2;AccountKey=abc"}}):
            result = AzureResult(container="bob", connection_string_secret="test")
            result.initialize_service()
            azure_client.assert_called_with(
                conn_str="con2;AccountKey=abc", credential=None
            )

    def test_azure_init_connection_string_without_key(self, azure_client):
        result = AzureResult(container="bob", connection_string="con1")
        result.initialize_service()
        azure_client.assert_called_with(conn_str="con1", credential="mocked!")

        with prefect.context({"secrets": {"test": "con2"}}):
            result = AzureResult(container="bob", connection_string_secret="test")
            result.initialize_service()
            azure_client.assert_called_with(conn_str="con2", credential="mocked!")

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
        client = MagicMock(
            download_blob=MagicMock(
                return_value=MagicMock(content_as_bytes=MagicMock(return_value=b""))
            )
        )
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
        assert isinstance(client.upload_blob.call_args[0][0], bytes)

    def test_azure_result_is_pickleable(self, azure_client):
        result = AzureResult("foo")
        res = cloudpickle.loads(cloudpickle.dumps(result))
        assert isinstance(res, AzureResult)

    @pytest.mark.parametrize("exists", [True, False])
    def test_azure_exists(self, monkeypatch, exists):
        client = MagicMock(exists=MagicMock(return_value=exists))
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        monkeypatch.setattr(
            "prefect.engine.results.azure_result.AzureResult.service", service
        )

        result = AzureResult(container="foo", location="{thing}/here.txt")
        assert result.exists("44.txt") is exists
