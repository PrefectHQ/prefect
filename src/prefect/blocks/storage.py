import io
import os
from abc import abstractmethod
from functools import partial
from pathlib import Path
from tempfile import gettempdir
from typing import Dict, Generic, Optional, TypeVar
from uuid import uuid4

import anyio
import httpx
from azure.storage.blob import BlobServiceClient
from google.cloud import storage as gcs
from google.oauth2 import service_account

import prefect
from prefect.blocks.core import Block, register_block
from prefect.settings import PREFECT_HOME
from prefect.utilities.asyncio import run_sync_in_worker_thread

# Storage block "key" type which should match for read/write in each implementation
T = TypeVar("T")


class StorageBlock(Block, Generic[T]):
    """
    A `Block` base class for persisting data.

    Implementers must provide methods to read and write bytes. When data is persisted,
    an object of type `T` is returned that may be later be used to retrieve the data.

    The type `T` should be JSON serializable.
    """

    _block_spec_type: Optional[str] = "STORAGE"

    @abstractmethod
    async def write(self, data: bytes) -> T:
        """
        Persist bytes and returns an object that may be passed to `read` to retrieve the
        data.
        """

    @abstractmethod
    async def read(self, obj: T) -> bytes:
        """
        Retrieve persisted bytes given the return value of a prior call to `write`.
        """


@register_block("S3 Storage", version="1.0")
class S3StorageBlock(StorageBlock):
    """Store data in an AWS S3 bucket"""

    bucket: str
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    profile_name: Optional[str] = None
    region_name: Optional[str] = None

    def block_initialization(self):
        import boto3

        self.aws_session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            profile_name=self.profile_name,
            region_name=self.region_name,
        )

    async def write(self, data: bytes) -> str:
        key = str(uuid4())
        await run_sync_in_worker_thread(self._write_sync, key, data)
        return key

    async def read(self, key: str) -> bytes:
        return await run_sync_in_worker_thread(self._read_sync, key)

    def _write_sync(self, key: str, data: bytes) -> None:
        s3_client = self.aws_session.client("s3")
        with io.BytesIO(data) as stream:
            s3_client.upload_fileobj(Fileobj=stream, Bucket=self.bucket, Key=key)

    def _read_sync(self, key: str) -> bytes:
        s3_client = self.aws_session.client("s3")
        with io.BytesIO() as stream:
            s3_client.download_fileobj(Bucket=self.bucket, Key=key, Fileobj=stream)
            stream.seek(0)
            output = stream.read()
        return output


@register_block("Temporary Local Storage", version="1.0")
class TempStorageBlock(StorageBlock):
    """Store data in a temporary directory in a run's local file system"""

    def block_initialization(self) -> None:
        pass

    def basepath(self):
        return Path(gettempdir())

    async def write(self, data):
        # Ensure the basepath exists
        storage_dir = self.basepath() / "prefect"
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Write data
        storage_path = str(storage_dir / str(uuid4()))
        async with await anyio.open_file(storage_path, mode="wb") as fp:
            await fp.write(data)

        return storage_path

    async def read(self, storage_path):
        async with await anyio.open_file(storage_path, mode="rb") as fp:
            return await fp.read()


@register_block("Local Storage", version="1.0")
class LocalStorageBlock(StorageBlock):
    """Store data in a run's local file system"""

    storage_path: Optional[str]

    def block_initialization(self) -> None:
        self._storage_path = (
            self.storage_path
            if self.storage_path is not None
            else PREFECT_HOME.value() / "storage"
        )

    def basepath(self):
        return Path(self._storage_path).absolute()

    async def write(self, data: bytes) -> str:
        # Ensure the basepath exists
        storage_dir = self.basepath()
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Write data
        storage_path = str(storage_dir / str(uuid4()))
        async with await anyio.open_file(storage_path, mode="wb") as fp:
            await fp.write(data)

        return storage_path

    async def read(self, storage_path: str) -> bytes:
        async with await anyio.open_file(storage_path, mode="rb") as fp:
            return await fp.read()


@register_block("Google Cloud Storage", version="1.0")
class GoogleCloudStorageBlock(StorageBlock):
    """Store data in a GCS bucket"""

    bucket: str
    project: Optional[str]
    service_account_info: Optional[Dict[str, str]]

    def block_initialization(self) -> None:
        if self.service_account_info:
            credentials = service_account.Credentials.from_service_account_info(
                self.service_account_info
            )
            self.storage_client = gcs.Client(
                project=self.project or credentials.project_id, credentials=credentials
            )
        else:
            self.storage_client = gcs.Client(project=self.project)

    async def read(self, key: str) -> bytes:
        bucket = self.storage_client.bucket(self.bucket)
        blob = bucket.blob(key)
        return await run_sync_in_worker_thread(blob.download_as_bytes)

    async def write(self, data: bytes) -> str:
        bucket = self.storage_client.bucket(self.bucket)
        key = str(uuid4())
        blob = bucket.blob(key)
        upload = partial(blob.upload_from_string, data)
        await run_sync_in_worker_thread(upload)
        return key


@register_block("Azure Blob Storage", version="1.0")
class AzureBlobStorageBlock(StorageBlock):
    """Store data in an Azure blob storage container"""

    container: str
    connection_string: str

    def block_initialization(self) -> None:
        self.blob_service_client = BlobServiceClient.from_connection_string(
            conn_str=self.connection_string
        )

    async def read(self, key: str) -> bytes:
        blob = self.blob_service_client.get_blob_client(
            container=self.container,
            blob=key,
        )
        stream = blob.download_blob()
        return await run_sync_in_worker_thread(stream.readall)

    async def write(self, data: bytes) -> str:
        key = str(uuid4())
        blob = self.blob_service_client.get_blob_client(
            container=self.container,
            blob=key,
        )
        await run_sync_in_worker_thread(blob.upload_blob, data)
        return key


@register_block("KV Server Storage", version="1.0")
class KVServerStorageBlock(StorageBlock):
    """
    Store data by sending requests to a KV server
    """

    api_address: str

    def block_initialization(self) -> None:
        if os.path.exists("/.dockerenv"):
            self.api_address = self.api_address.replace(
                "127.0.0.1", "host.docker.internal"
            )

    async def write(self, data: bytes) -> str:
        key = str(uuid4())

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.api_address}/{key}", json=data.decode() if data else None
            )
        return key

    async def read(self, key: str) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.api_address}/{key}")
        response.raise_for_status()
        if response.content:
            return str(response.json()).encode()
