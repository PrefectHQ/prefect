import asyncio
from itertools import product
from tempfile import TemporaryDirectory

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


@mock_s3
@pytest.mark.parametrize("user_data", TEST_DATA)
def test_s3_block_write_and_read_roundtrips(user_data):
    # initialize mock-aws with an S3 bucket to write to
    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket="with-holes")

    storage_block = storage.S3StorageBlock.parse_obj(
        {"blockref": "s3storage-block", "bucket": "with-holes"}
    )

    storage_token = asyncio.run(storage_block.write(user_data))
    assert asyncio.run(storage_block.read(storage_token)) == user_data
