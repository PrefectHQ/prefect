import io
import os
import sys
import warnings
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import uuid4

import anyio
import fsspec
import httpx
import pendulum
import pydantic
from azure.storage.blob import BlobServiceClient
from fsspec.implementations.local import LocalFileSystem
from google.oauth2 import service_account
from pydantic import Field, SecretStr
from typing_extensions import Literal

from prefect.blocks.core import Block
from prefect.settings import PREFECT_HOME
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import is_local_path
from prefect.utilities.hashing import stable_hash

with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    from google.cloud import storage as gcs

# Storage block "key" type which should match for read/write in each implementation
T = TypeVar("T")


class StorageBlock(Block, Generic[T], ABC):
    """
    A `Block` base class for persisting data.

    Implementers must provide methods to read and write bytes. When data is persisted,
    an object of type `T` is returned that may be later be used to retrieve the data.

    The type `T` should be JSON serializable.
    """

    _block_schema_capabilities = ["writeable", "readable", "storage"]

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


class FileStorageBlock(StorageBlock):
    """
    Store data as a file on local or remote file systems.

    Supports any file system supported by `fsspec`. The file system is specified using
    a protocol. For example, "s3://my-bucket/my-folder/" will use S3.

    Credentials for external services will be retrieved.

    Each blob is stored in a separate file. The key type defaults to "hash" to avoid
    storing duplicates. If you always want to store a new file, you can use "uuid" or
    "timestamp".
    """

    _block_type_name = "File Storage"

    base_path: str = pydantic.Field(..., description="The folder to write files in.")
    key_type: Literal["hash", "uuid", "timestamp"] = pydantic.Field(
        "hash", description="The method to use to generate file names."
    )
    options: Dict[str, Any] = pydantic.Field(
        default_factory=dict,
        description="Additional options to pass to the underlying fsspec file system.",
    )

    def block_initialization(self) -> None:
        # Check for missing remote storage dependency
        try:
            fsspec.open(self.base_path + "check")
        except ImportError as exc:
            # The path is a remote file system that uses a lib that is not installed
            exc_message = str(exc).rstrip(".")
            warnings.warn(
                f"File storage created with remote base path "
                f"{self.base_path!r}, but you are missing a Python module required to "
                f"use the given remote storage protocol. {exc_message}.",
                stacklevel=3,
            )
        return super().block_initialization()

    @pydantic.validator("base_path", pre=True)
    def allow_pathlib_paths(cls, value):
        if isinstance(value, Path):
            return str(value)
        return value

    @pydantic.validator("base_path")
    def ensure_trailing_slash(cls, value):
        if is_local_path(value):
            if not value.endswith(os.sep):
                return value + os.sep
        else:
            if not value.endswith("/"):
                return value + "/"
        return value

    def _create_key(self, data: bytes):
        """
        Method for determining the filename to write to; depends on
        key type, OS, and filesystem type.
        """
        if self.key_type == "uuid":
            return uuid4().hex
        elif self.key_type == "hash":
            return stable_hash(data)
        elif self.key_type == "timestamp":
            # colons are not allowed in windows paths
            if (
                sys.platform == "win32"
                and type(fsspec.open(self.base_path).fs) == LocalFileSystem
            ):
                return pendulum.now().isoformat().replace(":", "_")
            else:
                return pendulum.now().isoformat()
        else:
            raise ValueError(f"Unknown key type {self.key_type!r}")

    async def write(self, data: bytes) -> str:
        key = self._create_key(data)
        ff = fsspec.open(self.base_path + key, "wb", **self.options)

        # TODO: Some file systems support async and would require passing the current
        #       event loop in `self.options`. This would probably be better for
        #       performance. https://filesystem-spec.readthedocs.io/en/latest/async.html

        await run_sync_in_worker_thread(self._write_sync, ff, data)
        return key

    async def read(self, key: str) -> bytes:
        ff = fsspec.open(self.base_path + key, "rb", **self.options)
        return await run_sync_in_worker_thread(self._read_sync, ff)

    def _write_sync(self, ff: fsspec.core.OpenFile, data: bytes) -> None:
        with ff as io:
            io.write(data)

    def _read_sync(self, ff: fsspec.core.OpenFile) -> bytes:
        with ff as io:
            return io.read()


class S3StorageBlock(StorageBlock):
    """Store data in an AWS S3 bucket."""

    _block_type_name = "S3 Storage"

    bucket: str
    aws_access_key_id: Optional[str] = Field(None, title="AWS Access Key ID")
    aws_secret_access_key: Optional[SecretStr] = Field(
        None, title="AWS Secret Access Key"
    )
    aws_session_token: Optional[str] = Field(None, title="AWS Session Token")
    profile_name: Optional[str] = None
    region_name: Optional[str] = None

    def block_initialization(self):
        import boto3

        aws_secret_access_key_value = (
            None
            if self.aws_secret_access_key is None
            else self.aws_secret_access_key.get_secret_value()
        )

        self.aws_session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key_value,
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


class TempStorageBlock(StorageBlock):
    """Store data in a temporary directory in a run's local file system."""

    _block_type_name = "Temporary Local Storage"

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


class LocalStorageBlock(StorageBlock):
    """Store data in a run's local file system."""

    _block_type_name = "Local Storage"

    storage_path: Optional[str]

    def block_initialization(self) -> None:
        self._storage_path = (
            self.storage_path
            if self.storage_path is not None
            else PREFECT_HOME.value() / "storage"
        )

    def basepath(self):
        return Path(self._storage_path).expanduser().absolute()

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


class GoogleCloudStorageBlock(StorageBlock):
    """Store data in a GCS bucket."""

    _block_type_name = "Google Cloud Storage"

    bucket: str
    project: Optional[str]
    service_account_info: Optional[Dict[str, str]]

    def _get_storage_client(self):
        if self.service_account_info:
            credentials = service_account.Credentials.from_service_account_info(
                self.service_account_info
            )
            return gcs.Client(
                project=self.project or credentials.project_id, credentials=credentials
            )
        else:
            return gcs.Client(project=self.project)

    async def read(self, key: str) -> bytes:
        storage_client = self._get_storage_client()
        bucket = storage_client.bucket(self.bucket)
        blob = bucket.blob(key)
        return await run_sync_in_worker_thread(blob.download_as_bytes)

    async def write(self, data: bytes) -> str:
        storage_client = self._get_storage_client()
        bucket = storage_client.bucket(self.bucket)
        key = str(uuid4())
        blob = bucket.blob(key)
        upload = partial(blob.upload_from_string, data)
        await run_sync_in_worker_thread(upload)
        return key


class AzureBlobStorageBlock(StorageBlock):
    """Store data in an Azure blob storage container."""

    _block_type_name = "Azure Blob Storage"

    container: str
    connection_string: SecretStr

    def block_initialization(self) -> None:
        self.blob_service_client = BlobServiceClient.from_connection_string(
            conn_str=self.connection_string.get_secret_value()
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


class KVServerStorageBlock(StorageBlock):
    """
    Store data by sending requests to a KV server.
    """

    _block_type_name = "KV Server Storage"

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
