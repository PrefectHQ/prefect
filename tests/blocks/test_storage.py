import os.path
import sys
import uuid
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import boto3
import cloudpickle
import pendulum
import pytest
from moto import mock_s3
from pydantic import ValidationError

from prefect.blocks import storage
from prefect.utilities.hashing import stable_hash

TEST_DATA = [
    # Test a couple forms of bytes
    b"test!",
    bytes([0, 1, 2]),
]

FS_STORAGE_BLOCKS = [
    storage.TempStorageBlock.parse_obj({"blockref": "tempstorage-block"}),
    storage.LocalStorageBlock.parse_obj(
        {"blockref": "localstorage-block", "storage_path": TemporaryDirectory().name}
    ),
]


async def test_storage_block_schema_type():
    assert storage.StorageBlock._block_schema_type == "STORAGE"

    class MyStorageBlock(storage.StorageBlock):
        pass

    assert MyStorageBlock._block_schema_type == "STORAGE"


@pytest.mark.parametrize(
    ["user_data", "storage_block"], product(TEST_DATA, FS_STORAGE_BLOCKS)
)
async def test_write_and_read_rountdrips(
    user_data,
    storage_block,
):
    storage_token = await storage_block.write(user_data)
    assert await storage_block.read(storage_token) == user_data


class TestGoogleCloudStorageBlock:
    @pytest.mark.parametrize("user_data", TEST_DATA)
    async def test_write_and_read_roundtrips(self, user_data, monkeypatch):
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

    async def test_gcs_block_is_picklable(self):
        storage_block = storage.GoogleCloudStorageBlock.parse_obj(
            {"blockref": "googlecloudstorage-block", "bucket": "leaky"}
        )
        block_pickle = cloudpickle.dumps(storage_block)
        assert cloudpickle.loads(block_pickle) == storage_block


@pytest.mark.parametrize("user_data", TEST_DATA)
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


class TestFileStorageBlock:
    @pytest.mark.parametrize("key_type", ["hash", "uuid", "timestamp"])
    async def test_roundtrip_by_key_type(self, tmp_path, key_type):
        block = storage.FileStorageBlock(base_path=tmp_path, key_type=key_type)
        key = await block.write(b"hello")
        assert await block.read(key) == b"hello"

    def test_invalid_key_type(self, tmp_path):
        with pytest.raises(ValidationError):
            storage.FileStorageBlock(base_path=tmp_path, key_type="foo")

    async def test_write_when_directory_does_not_exist(self, tmp_path):
        block = storage.FileStorageBlock(base_path=tmp_path / "new_folder")
        key = await block.write(b"hello")
        assert await block.read(key) == b"hello"

    @pytest.mark.parametrize("key_type", ["hash", "uuid", "timestamp"])
    async def test_key_type_determines_file_name(self, tmp_path, key_type):
        block = storage.FileStorageBlock(base_path=tmp_path, key_type=key_type)
        key = await block.write(b"hello")

        if key_type == "hash":
            assert key == stable_hash(b"hello")
        elif key_type == "uuid":
            assert uuid.UUID(key)
        elif key_type == "timestamp":
            # colons are not allowed in windows paths
            assert pendulum.parse(key.replace("_", ":"))

        assert (tmp_path / key).exists()

    async def test_warns_on_missing_library_at_init_then_raises_on_usage(self):
        # Skip test if a developer happens to have this installed already
        try:
            import s3fs
        except:
            pass
        else:
            pytest.skip(reason="s3fs is installed so no warning would be raised")

        with pytest.warns(UserWarning, match="Install s3fs"):
            block = storage.FileStorageBlock(base_path="s3://prefect-test-bucket")

        assert (
            block.base_path == "s3://prefect-test-bucket/"
        ), "Base path still set correctly"

        with pytest.raises(ImportError, match="Install s3fs"):
            await block.read("test")

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix specific paths")
    async def test_adds_trailing_slash(self):
        block = storage.FileStorageBlock(base_path="/tmp/test")
        assert block.base_path == "/tmp/test/"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows specific paths")
    async def test_adds_trailing_sep(self):
        block = storage.FileStorageBlock(base_path="\\tmp\\test")
        assert block.base_path == "\\tmp\\test\\"

    async def test_includes_options_on_open(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr("fsspec.open", mock)

        block = storage.FileStorageBlock(
            base_path="/tmp/test", options={"test": 1, "foo": "bar"}
        )

        key = await block.write(b"")
        mock.assert_called_with(f"/tmp/test/{key}", "wb", test=1, foo="bar")

        await block.read(key)
        mock.assert_called_with(f"/tmp/test/{key}", "rb", test=1, foo="bar")


def test_local_storage_block_expands_home_directories():
    storage_path = Path("~") / ".prefect"
    local_storage_block = storage.LocalStorageBlock(storage_path=str(storage_path))
    # The path includes ~ still in the block's settings so that it is portable across systems
    assert "~" in str(local_storage_block.storage_path)
    basepath = str(local_storage_block.basepath())
    # The ~ has been expanded
    assert "~" not in basepath
    # The path is expanded correctly
    assert basepath == os.path.expanduser(storage_path)
