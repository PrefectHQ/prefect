import abc
import io
import json
import urllib.parse
from pathlib import Path
from shutil import ignore_patterns
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Tuple, Union

import anyio
import fsspec

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, SecretStr, validator
else:
    from pydantic import Field, SecretStr, validator

from prefect.blocks.core import Block
from prefect.exceptions import InvalidRepositoryURLError
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.compat import copytree
from prefect.utilities.filesystem import filter_files
from prefect.utilities.processutils import run_process


class ReadableFileSystem(Block, abc.ABC):
    _block_schema_capabilities = ["read-path"]

    @abc.abstractmethod
    async def read_path(self, path: str) -> bytes:
        pass


class WritableFileSystem(Block, abc.ABC):
    _block_schema_capabilities = ["read-path", "write-path"]

    @abc.abstractmethod
    async def read_path(self, path: str) -> bytes:
        pass

    @abc.abstractmethod
    async def write_path(self, path: str, content: bytes) -> None:
        pass


class ReadableDeploymentStorage(Block, abc.ABC):
    _block_schema_capabilities = ["get-directory"]

    @abc.abstractmethod
    async def get_directory(
        self, from_path: str = None, local_path: str = None
    ) -> None:
        pass


class WritableDeploymentStorage(Block, abc.ABC):
    _block_schema_capabilities = ["get-directory", "put-directory"]

    @abc.abstractmethod
    async def get_directory(
        self, from_path: str = None, local_path: str = None
    ) -> None:
        pass

    @abc.abstractmethod
    async def put_directory(
        self, local_path: str = None, to_path: str = None, ignore_file: str = None
    ) -> None:
        pass


class LocalFileSystem(WritableFileSystem, WritableDeploymentStorage):
    """
    Store data as a file on a local file system.

    Example:
        Load stored local file system config:
        ```python
        from prefect.filesystems import LocalFileSystem

        local_file_system_block = LocalFileSystem.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Local File System"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/ad39089fa66d273b943394a68f003f7a19aa850e-48x48.png"
    _documentation_url = (
        "https://docs.prefect.io/concepts/filesystems/#local-filesystem"
    )

    basepath: Optional[str] = Field(
        default=None, description="Default local path for this block to write to."
    )

    @validator("basepath", pre=True)
    def cast_pathlib(cls, value):
        if isinstance(value, Path):
            return str(value)
        return value

    def _resolve_path(self, path: str) -> Path:
        # Only resolve the base path at runtime, default to the current directory
        basepath = (
            Path(self.basepath).expanduser().resolve()
            if self.basepath
            else Path(".").resolve()
        )

        # Determine the path to access relative to the base path, ensuring that paths
        # outside of the base path are off limits
        if path is None:
            return basepath

        path: Path = Path(path).expanduser()

        if not path.is_absolute():
            path = basepath / path
        else:
            path = path.resolve()
            if basepath not in path.parents and (basepath != path):
                raise ValueError(
                    f"Provided path {path} is outside of the base path {basepath}."
                )

        return path

    @sync_compatible
    async def get_directory(
        self, from_path: str = None, local_path: str = None
    ) -> None:
        """
        Copies a directory from one place to another on the local filesystem.

        Defaults to copying the entire contents of the block's basepath to the current working directory.
        """
        if not from_path:
            from_path = Path(self.basepath).expanduser().resolve()
        else:
            from_path = self._resolve_path(from_path)

        if not local_path:
            local_path = Path(".").resolve()
        else:
            local_path = Path(local_path).resolve()

        if from_path == local_path:
            # If the paths are the same there is no need to copy
            # and we avoid shutil.copytree raising an error
            return

        # .prefectignore exists in the original location, not the current location which
        # is most likely temporary
        if (from_path / Path(".prefectignore")).exists():
            ignore_func = await self._get_ignore_func(
                local_path=from_path, ignore_file=from_path / Path(".prefectignore")
            )
        else:
            ignore_func = None

        copytree(from_path, local_path, dirs_exist_ok=True, ignore=ignore_func)

    async def _get_ignore_func(self, local_path: str, ignore_file: str):
        with open(ignore_file, "r") as f:
            ignore_patterns = f.readlines()
        included_files = filter_files(root=local_path, ignore_patterns=ignore_patterns)

        def ignore_func(directory, files):
            relative_path = Path(directory).relative_to(local_path)

            files_to_ignore = [
                f for f in files if str(relative_path / f) not in included_files
            ]
            return files_to_ignore

        return ignore_func

    @sync_compatible
    async def put_directory(
        self, local_path: str = None, to_path: str = None, ignore_file: str = None
    ) -> None:
        """
        Copies a directory from one place to another on the local filesystem.

        Defaults to copying the entire contents of the current working directory to the block's basepath.
        An `ignore_file` path may be provided that can include gitignore style expressions for filepaths to ignore.
        """
        destination_path = self._resolve_path(to_path)

        if not local_path:
            local_path = Path(".").absolute()

        if ignore_file:
            ignore_func = await self._get_ignore_func(
                local_path=local_path, ignore_file=ignore_file
            )
        else:
            ignore_func = None

        if local_path == destination_path:
            pass
        else:
            copytree(
                src=local_path,
                dst=destination_path,
                ignore=ignore_func,
                dirs_exist_ok=True,
            )

    @sync_compatible
    async def read_path(self, path: str) -> bytes:
        path: Path = self._resolve_path(path)

        # Check if the path exists
        if not path.exists():
            raise ValueError(f"Path {path} does not exist.")

        # Validate that its a file
        if not path.is_file():
            raise ValueError(f"Path {path} is not a file.")

        async with await anyio.open_file(str(path), mode="rb") as f:
            content = await f.read()

        return content

    @sync_compatible
    async def write_path(self, path: str, content: bytes) -> str:
        path: Path = self._resolve_path(path)

        # Construct the path if it does not exist
        path.parent.mkdir(exist_ok=True, parents=True)

        # Check if the file already exists
        if path.exists() and not path.is_file():
            raise ValueError(f"Path {path} already exists and is not a file.")

        async with await anyio.open_file(path, mode="wb") as f:
            await f.write(content)
        # Leave path stringify to the OS
        return str(path)


class RemoteFileSystem(WritableFileSystem, WritableDeploymentStorage):
    """
    Store data as a file on a remote file system.

    Supports any remote file system supported by `fsspec`. The file system is specified
    using a protocol. For example, "s3://my-bucket/my-folder/" will use S3.

    Example:
        Load stored remote file system config:
        ```python
        from prefect.filesystems import RemoteFileSystem

        remote_file_system_block = RemoteFileSystem.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Remote File System"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/e86b41bc0f9c99ba9489abeee83433b43d5c9365-48x48.png"
    _documentation_url = (
        "https://docs.prefect.io/concepts/filesystems/#remote-file-system"
    )

    basepath: str = Field(
        default=...,
        description="Default path for this block to write to.",
        example="s3://my-bucket/my-folder/",
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional settings to pass through to fsspec.",
    )

    # Cache for the configured fsspec file system used for access
    _filesystem: fsspec.AbstractFileSystem = None

    @validator("basepath")
    def check_basepath(cls, value):
        scheme, netloc, _, _, _ = urllib.parse.urlsplit(value)

        if not scheme:
            raise ValueError(f"Base path must start with a scheme. Got {value!r}.")

        if not netloc:
            raise ValueError(
                f"Base path must include a location after the scheme. Got {value!r}."
            )

        if scheme == "file":
            raise ValueError(
                "Base path scheme cannot be 'file'. Use `LocalFileSystem` instead for"
                " local file access."
            )

        return value

    def _resolve_path(self, path: str) -> str:
        base_scheme, base_netloc, base_urlpath, _, _ = urllib.parse.urlsplit(
            self.basepath
        )
        scheme, netloc, urlpath, _, _ = urllib.parse.urlsplit(path)

        # Confirm that absolute paths are valid
        if scheme:
            if scheme != base_scheme:
                raise ValueError(
                    f"Path {path!r} with scheme {scheme!r} must use the same scheme as"
                    f" the base path {base_scheme!r}."
                )

        if netloc:
            if (netloc != base_netloc) or not urlpath.startswith(base_urlpath):
                raise ValueError(
                    f"Path {path!r} is outside of the base path {self.basepath!r}."
                )

        return f"{self.basepath.rstrip('/')}/{urlpath.lstrip('/')}"

    @sync_compatible
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """
        Downloads a directory from a given remote path to a local directory.

        Defaults to downloading the entire contents of the block's basepath to the current working directory.
        """
        if from_path is None:
            from_path = str(self.basepath)
        else:
            from_path = self._resolve_path(from_path)

        if local_path is None:
            local_path = Path(".").absolute()

        # validate that from_path has a trailing slash for proper fsspec behavior across versions
        if not from_path.endswith("/"):
            from_path += "/"

        return self.filesystem.get(from_path, local_path, recursive=True)

    @sync_compatible
    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
        overwrite: bool = True,
    ) -> int:
        """
        Uploads a directory from a given local path to a remote directory.

        Defaults to uploading the entire contents of the current working directory to the block's basepath.
        """
        if to_path is None:
            to_path = str(self.basepath)
        else:
            to_path = self._resolve_path(to_path)

        if local_path is None:
            local_path = "."

        included_files = None
        if ignore_file:
            with open(ignore_file, "r") as f:
                ignore_patterns = f.readlines()

            included_files = filter_files(
                local_path, ignore_patterns, include_dirs=True
            )

        counter = 0
        for f in Path(local_path).rglob("*"):
            relative_path = f.relative_to(local_path)
            if included_files and str(relative_path) not in included_files:
                continue

            if to_path.endswith("/"):
                fpath = to_path + relative_path.as_posix()
            else:
                fpath = to_path + "/" + relative_path.as_posix()

            if f.is_dir():
                pass
            else:
                f = f.as_posix()
                if overwrite:
                    self.filesystem.put_file(f, fpath, overwrite=True)
                else:
                    self.filesystem.put_file(f, fpath)

                counter += 1

        return counter

    @sync_compatible
    async def read_path(self, path: str) -> bytes:
        path = self._resolve_path(path)

        with self.filesystem.open(path, "rb") as file:
            content = await run_sync_in_worker_thread(file.read)

        return content

    @sync_compatible
    async def write_path(self, path: str, content: bytes) -> str:
        path = self._resolve_path(path)
        dirpath = path[: path.rindex("/")]

        self.filesystem.makedirs(dirpath, exist_ok=True)

        with self.filesystem.open(path, "wb") as file:
            await run_sync_in_worker_thread(file.write, content)
        return path

    @property
    def filesystem(self) -> fsspec.AbstractFileSystem:
        if not self._filesystem:
            scheme, _, _, _, _ = urllib.parse.urlsplit(self.basepath)

            try:
                self._filesystem = fsspec.filesystem(scheme, **self.settings)
            except ImportError as exc:
                # The path is a remote file system that uses a lib that is not installed
                raise RuntimeError(
                    f"File system created with scheme {scheme!r} from base path "
                    f"{self.basepath!r} could not be created. "
                    "You are likely missing a Python module required to use the given "
                    "storage protocol."
                ) from exc

        return self._filesystem


class S3(WritableFileSystem, WritableDeploymentStorage):
    """
    Store data as a file on AWS S3.

    Example:
        Load stored S3 config:
        ```python
        from prefect.filesystems import S3

        s3_block = S3.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "S3"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"
    _documentation_url = "https://docs.prefect.io/concepts/filesystems/#s3"

    bucket_path: str = Field(
        default=...,
        description="An S3 bucket path.",
        example="my-bucket/a-directory-within",
    )
    aws_access_key_id: Optional[SecretStr] = Field(
        default=None,
        title="AWS Access Key ID",
        description="Equivalent to the AWS_ACCESS_KEY_ID environment variable.",
        example="AKIAIOSFODNN7EXAMPLE",
    )
    aws_secret_access_key: Optional[SecretStr] = Field(
        default=None,
        title="AWS Secret Access Key",
        description="Equivalent to the AWS_SECRET_ACCESS_KEY environment variable.",
        example="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    )

    _remote_file_system: RemoteFileSystem = None

    @property
    def basepath(self) -> str:
        return f"s3://{self.bucket_path}"

    @property
    def filesystem(self) -> RemoteFileSystem:
        settings = {}
        if self.aws_access_key_id:
            settings["key"] = self.aws_access_key_id.get_secret_value()
        if self.aws_secret_access_key:
            settings["secret"] = self.aws_secret_access_key.get_secret_value()
        self._remote_file_system = RemoteFileSystem(
            basepath=f"s3://{self.bucket_path}", settings=settings
        )
        return self._remote_file_system

    @sync_compatible
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> bytes:
        """
        Downloads a directory from a given remote path to a local directory.

        Defaults to downloading the entire contents of the block's basepath to the current working directory.
        """
        return await self.filesystem.get_directory(
            from_path=from_path, local_path=local_path
        )

    @sync_compatible
    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> int:
        """
        Uploads a directory from a given local path to a remote directory.

        Defaults to uploading the entire contents of the current working directory to the block's basepath.
        """
        return await self.filesystem.put_directory(
            local_path=local_path, to_path=to_path, ignore_file=ignore_file
        )

    @sync_compatible
    async def read_path(self, path: str) -> bytes:
        return await self.filesystem.read_path(path)

    @sync_compatible
    async def write_path(self, path: str, content: bytes) -> str:
        return await self.filesystem.write_path(path=path, content=content)


class GCS(WritableFileSystem, WritableDeploymentStorage):
    """
    Store data as a file on Google Cloud Storage.

    Example:
        Load stored GCS config:
        ```python
        from prefect.filesystems import GCS

        gcs_block = GCS.load("BLOCK_NAME")
        ```
    """

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/422d13bb838cf247eb2b2cf229ce6a2e717d601b-256x256.png"
    _documentation_url = "https://docs.prefect.io/concepts/filesystems/#gcs"

    bucket_path: str = Field(
        default=...,
        description="A GCS bucket path.",
        example="my-bucket/a-directory-within",
    )
    service_account_info: Optional[SecretStr] = Field(
        default=None,
        description="The contents of a service account keyfile as a JSON string.",
    )
    project: Optional[str] = Field(
        default=None,
        description=(
            "The project the GCS bucket resides in. If not provided, the project will"
            " be inferred from the credentials or environment."
        ),
    )

    @property
    def basepath(self) -> str:
        return f"gcs://{self.bucket_path}"

    @property
    def filesystem(self) -> RemoteFileSystem:
        settings = {}
        if self.service_account_info:
            try:
                settings["token"] = json.loads(
                    self.service_account_info.get_secret_value()
                )
            except json.JSONDecodeError:
                raise ValueError(
                    "Unable to load provided service_account_info. Please make sure"
                    " that the provided value is a valid JSON string."
                )
        remote_file_system = RemoteFileSystem(
            basepath=f"gcs://{self.bucket_path}", settings=settings
        )
        return remote_file_system

    @sync_compatible
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> bytes:
        """
        Downloads a directory from a given remote path to a local directory.

        Defaults to downloading the entire contents of the block's basepath to the current working directory.
        """
        return await self.filesystem.get_directory(
            from_path=from_path, local_path=local_path
        )

    @sync_compatible
    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> int:
        """
        Uploads a directory from a given local path to a remote directory.

        Defaults to uploading the entire contents of the current working directory to the block's basepath.
        """
        return await self.filesystem.put_directory(
            local_path=local_path, to_path=to_path, ignore_file=ignore_file
        )

    @sync_compatible
    async def read_path(self, path: str) -> bytes:
        return await self.filesystem.read_path(path)

    @sync_compatible
    async def write_path(self, path: str, content: bytes) -> str:
        return await self.filesystem.write_path(path=path, content=content)


class Azure(WritableFileSystem, WritableDeploymentStorage):
    """
    Store data as a file on Azure Datalake and Azure Blob Storage.

    Example:
        Load stored Azure config:
        ```python
        from prefect.filesystems import Azure

        az_block = Azure.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Azure"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"
    _documentation_url = "https://docs.prefect.io/concepts/filesystems/#azure"

    bucket_path: str = Field(
        default=...,
        description="An Azure storage bucket path.",
        example="my-bucket/a-directory-within",
    )
    azure_storage_connection_string: Optional[SecretStr] = Field(
        default=None,
        title="Azure storage connection string",
        description=(
            "Equivalent to the AZURE_STORAGE_CONNECTION_STRING environment variable."
        ),
    )
    azure_storage_account_name: Optional[SecretStr] = Field(
        default=None,
        title="Azure storage account name",
        description=(
            "Equivalent to the AZURE_STORAGE_ACCOUNT_NAME environment variable."
        ),
    )
    azure_storage_account_key: Optional[SecretStr] = Field(
        default=None,
        title="Azure storage account key",
        description="Equivalent to the AZURE_STORAGE_ACCOUNT_KEY environment variable.",
    )
    azure_storage_tenant_id: Optional[SecretStr] = Field(
        None,
        title="Azure storage tenant ID",
        description="Equivalent to the AZURE_TENANT_ID environment variable.",
    )
    azure_storage_client_id: Optional[SecretStr] = Field(
        None,
        title="Azure storage client ID",
        description="Equivalent to the AZURE_CLIENT_ID environment variable.",
    )
    azure_storage_client_secret: Optional[SecretStr] = Field(
        None,
        title="Azure storage client secret",
        description="Equivalent to the AZURE_CLIENT_SECRET environment variable.",
    )
    azure_storage_anon: bool = Field(
        default=True,
        title="Azure storage anonymous connection",
        description=(
            "Set the 'anon' flag for ADLFS. This should be False for systems that"
            " require ADLFS to use DefaultAzureCredentials."
        ),
    )

    _remote_file_system: RemoteFileSystem = None

    @property
    def basepath(self) -> str:
        return f"az://{self.bucket_path}"

    @property
    def filesystem(self) -> RemoteFileSystem:
        settings = {}
        if self.azure_storage_connection_string:
            settings["connection_string"] = (
                self.azure_storage_connection_string.get_secret_value()
            )
        if self.azure_storage_account_name:
            settings["account_name"] = (
                self.azure_storage_account_name.get_secret_value()
            )
        if self.azure_storage_account_key:
            settings["account_key"] = self.azure_storage_account_key.get_secret_value()
        if self.azure_storage_tenant_id:
            settings["tenant_id"] = self.azure_storage_tenant_id.get_secret_value()
        if self.azure_storage_client_id:
            settings["client_id"] = self.azure_storage_client_id.get_secret_value()
        if self.azure_storage_client_secret:
            settings["client_secret"] = (
                self.azure_storage_client_secret.get_secret_value()
            )
        settings["anon"] = self.azure_storage_anon
        self._remote_file_system = RemoteFileSystem(
            basepath=f"az://{self.bucket_path}", settings=settings
        )
        return self._remote_file_system

    @sync_compatible
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> bytes:
        """
        Downloads a directory from a given remote path to a local directory.

        Defaults to downloading the entire contents of the block's basepath to the current working directory.
        """
        return await self.filesystem.get_directory(
            from_path=from_path, local_path=local_path
        )

    @sync_compatible
    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> int:
        """
        Uploads a directory from a given local path to a remote directory.

        Defaults to uploading the entire contents of the current working directory to the block's basepath.
        """
        return await self.filesystem.put_directory(
            local_path=local_path, to_path=to_path, ignore_file=ignore_file
        )

    @sync_compatible
    async def read_path(self, path: str) -> bytes:
        return await self.filesystem.read_path(path)

    @sync_compatible
    async def write_path(self, path: str, content: bytes) -> str:
        return await self.filesystem.write_path(path=path, content=content)


class SMB(WritableFileSystem, WritableDeploymentStorage):
    """
    Store data as a file on a SMB share.

    Example:
        Load stored SMB config:

        ```python
        from prefect.filesystems import SMB
        smb_block = SMB.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "SMB"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/3f624663f7beb97d011d011bffd51ecf6c499efc-195x195.png"
    _documentation_url = "https://docs.prefect.io/concepts/filesystems/#smb"

    share_path: str = Field(
        default=...,
        description="SMB target (requires <SHARE>, followed by <PATH>).",
        example="/SHARE/dir/subdir",
    )
    smb_username: Optional[SecretStr] = Field(
        default=None,
        title="SMB Username",
        description="Username with access to the target SMB SHARE.",
    )
    smb_password: Optional[SecretStr] = Field(
        default=None, title="SMB Password", description="Password for SMB access."
    )
    smb_host: str = Field(
        default=..., tile="SMB server/hostname", description="SMB server/hostname."
    )
    smb_port: Optional[int] = Field(
        default=None, title="SMB port", description="SMB port (default: 445)."
    )

    _remote_file_system: RemoteFileSystem = None

    @property
    def basepath(self) -> str:
        return f"smb://{self.smb_host.rstrip('/')}/{self.share_path.lstrip('/')}"

    @property
    def filesystem(self) -> RemoteFileSystem:
        settings = {}
        if self.smb_username:
            settings["username"] = self.smb_username.get_secret_value()
        if self.smb_password:
            settings["password"] = self.smb_password.get_secret_value()
        if self.smb_host:
            settings["host"] = self.smb_host
        if self.smb_port:
            settings["port"] = self.smb_port
        self._remote_file_system = RemoteFileSystem(
            basepath=f"smb://{self.smb_host.rstrip('/')}/{self.share_path.lstrip('/')}",
            settings=settings,
        )
        return self._remote_file_system

    @sync_compatible
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> bytes:
        """
        Downloads a directory from a given remote path to a local directory.
        Defaults to downloading the entire contents of the block's basepath to the current working directory.
        """
        return await self.filesystem.get_directory(
            from_path=from_path, local_path=local_path
        )

    @sync_compatible
    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> int:
        """
        Uploads a directory from a given local path to a remote directory.
        Defaults to uploading the entire contents of the current working directory to the block's basepath.
        """
        return await self.filesystem.put_directory(
            local_path=local_path,
            to_path=to_path,
            ignore_file=ignore_file,
            overwrite=False,
        )

    @sync_compatible
    async def read_path(self, path: str) -> bytes:
        return await self.filesystem.read_path(path)

    @sync_compatible
    async def write_path(self, path: str, content: bytes) -> str:
        return await self.filesystem.write_path(path=path, content=content)


class GitHub(ReadableDeploymentStorage):
    """
    Interact with files stored on GitHub repositories.
    """

    _block_type_name = "GitHub"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/41971cfecfea5f79ff334164f06ecb34d1038dd4-250x250.png"
    _documentation_url = "https://docs.prefect.io/concepts/filesystems/#github"

    repository: str = Field(
        default=...,
        description=(
            "The URL of a GitHub repository to read from, in either HTTPS or SSH"
            " format."
        ),
    )
    reference: Optional[str] = Field(
        default=None,
        description="An optional reference to pin to; can be a branch name or tag.",
    )
    access_token: Optional[SecretStr] = Field(
        name="Personal Access Token",
        default=None,
        description=(
            "A GitHub Personal Access Token (PAT) with repo scope."
            " To use a fine-grained PAT, provide '{username}:{PAT}' as the value."
        ),
    )
    include_git_objects: bool = Field(
        default=True,
        description=(
            "Whether to include git objects when copying the repo contents to a"
            " directory."
        ),
    )

    @validator("access_token")
    def _ensure_credentials_go_with_https(cls, v: str, values: dict) -> str:
        """Ensure that credentials are not provided with 'SSH' formatted GitHub URLs.

        Note: validates `access_token` specifically so that it only fires when
        private repositories are used.
        """
        if v is not None:
            if urllib.parse.urlparse(values["repository"]).scheme != "https":
                raise InvalidRepositoryURLError(
                    "Crendentials can only be used with GitHub repositories "
                    "using the 'HTTPS' format. You must either remove the "
                    "credential if you wish to use the 'SSH' format and are not "
                    "using a private repository, or you must change the repository "
                    "URL to the 'HTTPS' format. "
                )

        return v

    def _create_repo_url(self) -> str:
        """Format the URL provided to the `git clone` command.

        For private repos: https://<oauth-key>@github.com/<username>/<repo>.git
        All other repos should be the same as `self.repository`.
        """
        url_components = urllib.parse.urlparse(self.repository)
        if url_components.scheme == "https" and self.access_token is not None:
            updated_components = url_components._replace(
                netloc=f"{self.access_token.get_secret_value()}@{url_components.netloc}"
            )
            full_url = urllib.parse.urlunparse(updated_components)
        else:
            full_url = self.repository

        return full_url

    @staticmethod
    def _get_paths(
        dst_dir: Union[str, None], src_dir: str, sub_directory: str
    ) -> Tuple[str, str]:
        """Returns the fully formed paths for GitHubRepository contents in the form
        (content_source, content_destination).
        """
        if dst_dir is None:
            content_destination = Path(".").absolute()
        else:
            content_destination = Path(dst_dir)

        content_source = Path(src_dir)

        if sub_directory:
            content_destination = content_destination.joinpath(sub_directory)
            content_source = content_source.joinpath(sub_directory)

        return str(content_source), str(content_destination)

    @sync_compatible
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """
        Clones a GitHub project specified in `from_path` to the provided `local_path`;
        defaults to cloning the repository reference configured on the Block to the
        present working directory.

        Args:
            from_path: If provided, interpreted as a subdirectory of the underlying
                repository that will be copied to the provided local path.
            local_path: A local path to clone to; defaults to present working directory.
        """
        # CONSTRUCT COMMAND
        cmd = ["git", "clone", self._create_repo_url()]
        if self.reference:
            cmd += ["-b", self.reference]

        # Limit git history
        cmd += ["--depth", "1"]

        # Clone to a temporary directory and move the subdirectory over
        with TemporaryDirectory(suffix="prefect") as tmp_dir:
            cmd.append(tmp_dir)

            err_stream = io.StringIO()
            out_stream = io.StringIO()
            process = await run_process(cmd, stream_output=(out_stream, err_stream))
            if process.returncode != 0:
                err_stream.seek(0)
                raise OSError(f"Failed to pull from remote:\n {err_stream.read()}")

            content_source, content_destination = self._get_paths(
                dst_dir=local_path, src_dir=tmp_dir, sub_directory=from_path
            )

            ignore_func = None
            if not self.include_git_objects:
                ignore_func = ignore_patterns(".git")

            copytree(
                src=content_source,
                dst=content_destination,
                dirs_exist_ok=True,
                ignore=ignore_func,
            )
