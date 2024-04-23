from unittest.mock import MagicMock

import pytest
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob.aio import ContainerClient
from prefect_azure.credentials import AzureBlobStorageCredentials

from prefect.testing.utilities import AsyncMock, prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield


class AsyncIter:
    def __init__(self, items):
        self.items = items

    async def __aiter__(self):
        for item in self.items:
            yield item


mock_container = {
    "prefect.txt": b"prefect_works",
    "folder/prefect.txt": b"prefect_works",
}


class BlobStorageClientMethodsMock:
    def __init__(self, blob="prefect.txt"):
        self.blob = blob

    @property
    def credential(self):
        return MagicMock(account_name="account_name", account_key="account_key")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def download_blob(self):
        return AsyncMock(
            name="blob_obj",
            content_as_bytes=AsyncMock(return_value=mock_container.get(self.blob)),
            download_to_stream=AsyncMock(
                side_effect=lambda f: f.write(mock_container.get(self.blob))
            ),
            readinto=AsyncMock(
                side_effect=lambda f: f.write(mock_container.get(self.blob))
            ),
        )

    async def upload_blob(self, data, overwrite=False):
        if not overwrite and self.blob in mock_container:
            raise ResourceExistsError("Cannot overwrite existing blob")
        if isinstance(data, (str, bytes)):
            mock_container[self.blob] = data
        else:
            mock_container[self.blob] = data.read()
        return self.blob

    def list_blobs(self, name_starts_with=None, include=None, **kwargs):
        sample_dicts = [
            {"name": "fakefolder", "metadata": None},
            *[{"name": f"fakefolder/file{i}", "metadata": None} for i in range(4)],
        ]
        if name_starts_with:
            to_return = [
                d for d in sample_dicts if d["name"].startswith(name_starts_with)
            ]
        else:
            to_return = sample_dicts
        if include:
            for d in to_return:
                d.update({"metadata": {"some_metadata": "true"}})
        return AsyncIter(to_return)

    async def close(self):
        return None


@pytest.fixture
def blob_storage_credentials():
    blob_storage_credentials = MagicMock()
    blob_storage_credentials.get_client.side_effect = (
        lambda: BlobStorageClientMethodsMock()
    )
    blob_storage_credentials.get_blob_client.side_effect = (
        lambda container, blob: BlobStorageClientMethodsMock(blob)
    )
    blob_storage_credentials.get_container_client.side_effect = (
        lambda container: BlobStorageClientMethodsMock()
    )
    return blob_storage_credentials


@pytest.fixture
def mock_blob_storage_credentials():
    blob_storage_credentials = AzureBlobStorageCredentials(connection_string="mock")
    mock_get_blob_client_with_container = MagicMock(
        side_effect=lambda container, blob: BlobStorageClientMethodsMock(blob)
    )

    blob_storage_credentials.get_blob_client = mock_get_blob_client_with_container

    mock_get_blob_client_without_container = MagicMock(
        side_effect=lambda blob: BlobStorageClientMethodsMock(blob)
    )

    blob_storage_credentials.get_container_client = MagicMock(spec=ContainerClient)
    block_mock = MagicMock()
    block_mock.name = "folder/prefect.txt"
    blob_storage_credentials.get_container_client().__aenter__.return_value = AsyncMock(
        list_blobs=MagicMock(return_value=AsyncIter([block_mock])),
        get_blob_client=mock_get_blob_client_without_container,
    )

    return blob_storage_credentials


class CosmosDbClientMethodsMock:
    def query_items(self, *args, **kwargs):
        return [{"name": "Someone", "age": 23}]

    def read_item(self, *args, **kwargs):
        return {"name": "Someone", "age": 23}

    def create_item(self, *args, **kwargs):
        return {"name": "Other", "age": 3}


@pytest.fixture
def cosmos_db_credentials():
    cosmos_db_credentials = MagicMock()
    cosmos_db_credentials.get_container_client.side_effect = (
        lambda container, database: CosmosDbClientMethodsMock()
    )
    return cosmos_db_credentials


@pytest.fixture
def ml_credentials():
    ml_credentials = MagicMock()
    ml_credentials.get_workspace.side_effect = lambda: MagicMock(datastores=["a", "b"])
    return ml_credentials


class DatastoreMethodsMock:
    def __init__(self, workspace, datastore_name="default"):
        self.workspace = workspace
        self.datastore_name = datastore_name

    def upload(self, *args, **kwargs):
        return kwargs

    def upload_files(self, *args, **kwargs):
        return kwargs


@pytest.fixture
def datastore(monkeypatch):
    DatastoreMock = MagicMock()
    DatastoreMock.get_default.side_effect = lambda workspace: DatastoreMethodsMock(
        workspace
    )
    DatastoreMock.get.side_effect = (
        lambda workspace, datastore_name: DatastoreMethodsMock(
            workspace, datastore_name=datastore_name
        )
    )
    DatastoreMock.register_azure_blob_container.side_effect = (
        lambda **kwargs: "registered"
    )

    monkeypatch.setattr("prefect_azure.ml_datastore.Datastore", DatastoreMock)


@pytest.fixture
def blob_connection_string():
    return "AccountName=account_name;AccountKey=account_key"


@pytest.fixture
def account_url(monkeypatch):
    monkeypatch.setattr(
        "azure.storage.blob._shared.base_client_async.AsyncStorageBearerTokenCredentialPolicy",  # noqa
        MagicMock(),
    )
    return "account_url"


class CosmosClientMock(MagicMock):
    def from_connection_string(connection_string):
        return CosmosClientMock()

    def get_client(self):
        return CosmosClientMock(client="client")

    def get_database_client(self, database):
        return CosmosClientMock(database=database)

    def get_container_client(self, container):
        return CosmosClientMock(container=container)


@pytest.fixture
def cosmos_connection_string(monkeypatch):
    monkeypatch.setattr("prefect_azure.credentials.CosmosClient", CosmosClientMock)
    return "AccountEndpoint=url/;AccountKey=AccountKey==;"
