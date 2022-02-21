from itertools import product
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_s3

from prefect.blocks import storage

TEST_DATA = [
    # Test a couple forms of bytes
    b"test!",
    bytes([0, 1, 2]),
]

FS_STORAGE_BLOCKS = [
    storage.OrionStorageBlock.parse_obj({"blockref": "orionstorage-block"}),
    storage.TempStorageBlock.parse_obj({"blockref": "tempstorage-block"}),
    storage.LocalStorageBlock.parse_obj(
        {"blockref": "localstorage-block", "storage_path": TemporaryDirectory().name}
    ),
]


@pytest.mark.parametrize(
    ["user_data", "storage_block"], product(TEST_DATA, FS_STORAGE_BLOCKS)
)
async def test_write_and_read_rountdrips(
    user_data,
    storage_block,
):
    storage_token = await storage_block.write(user_data)
    assert await storage_block.read(storage_token) == user_data


@pytest.mark.parametrize("user_data", TEST_DATA)
async def test_gcs_block_write_and_read_roundtrips(user_data, monkeypatch):
    mock_bucket = {}
    gcs_mock = MagicMock()
    gcs_mock.Client().bucket().blob.side_effect = lambda key: MagicMock(
        upload_from_string=lambda data: mock_bucket.update({key: data}),
        download_as_bytes=lambda: mock_bucket.get(key),
    )
    monkeypatch.setattr("prefect.blocks.storage.gcs", gcs_mock)

    storage_block = storage.GoogleCloudStorageBlock.parse_obj(
        {"blockref": "googlecloudstorage-block", "bucket": "leaky"}
    )

    key = await storage_block.write(user_data)
    assert await storage_block.read(key) == user_data


async def test_azure_blob_storage_block_write_and_read_roundtrips(
    user_data, monkeypatch
):
    mock_container = {}
    BlobServiceClientMock = MagicMock()
    BlobServiceClientMock.from_connection_string().get_blob_client.side_effect = (
        lambda container, blob: MagicMock(
            download_blob=lambda: MagicMock(readall=lambda: mock_container.get(blob)),
            upload_blob=lambda data: mock_container.update({blob: data}),
        )
    )

    monkeypatch.setattr(
        "prefect.blocks.storage.BlobServiceClient", BlobServiceClientMock
    )
    storage_block = storage.AzureBlobStorageBlock.parse_obj(
        {
            "blockref": "azureblobstorage-block",
            "container": "cracked",
            "connection_string": "trust_me",
        }
    )

    key = await storage_block.write(user_data)
    assert await storage_block.read(key) == user_data


@pytest.mark.parametrize("user_data", TEST_DATA)
async def test_s3_block_write_and_read_roundtrips(user_data):
    with mock_s3():
        # initialize mock-aws with an S3 bucket to write to
        s3_client = boto3.client("s3")
        s3_client.create_bucket(Bucket="with-holes")

        storage_block = storage.S3StorageBlock.parse_obj(
            {"blockref": "s3storage-block", "bucket": "with-holes"}
        )

        storage_token = await storage_block.write(user_data)
        assert await storage_block.read(storage_token) == user_data
