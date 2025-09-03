from __future__ import annotations

import abc
import urllib.parse
from pathlib import Path
from shutil import copytree
from typing import Any, Callable, Dict, Optional

import anyio
import fsspec
from pydantic import BaseModel, Field, SecretStr, field_validator

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect._internal.schemas.validators import (
    stringify_path,
    validate_basepath,
)
from prefect.blocks.core import Block
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.filesystem import filter_files

from ._internal.compatibility.migration import getattr_migration


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
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        pass


class WritableDeploymentStorage(Block, abc.ABC):
    _block_schema_capabilities = ["get-directory", "put-directory"]

    @abc.abstractmethod
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        pass

    @abc.abstractmethod
    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
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
        "https://docs.prefect.io/latest/develop/results#specifying-a-default-filesystem"
    )

    basepath: Optional[str] = Field(
        default=None, description="Default local path for this block to write to."
    )

    @field_validator("basepath", mode="before")
    def cast_pathlib(cls, value: str | Path | None) -> str | None:
        if value is None:
            return value
        return stringify_path(value)

    def _resolve_path(self, path: str, validate: bool = False) -> Path:
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

        resolved_path: Path = Path(path).expanduser()

        if not resolved_path.is_absolute():
            resolved_path = basepath / resolved_path
        else:
            resolved_path = resolved_path.resolve()

        if validate:
            if basepath not in resolved_path.parents and (basepath != resolved_path):
                raise ValueError(
                    f"Provided path {resolved_path} is outside of the base path {basepath}."
                )
        return resolved_path

    async def aget_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """
        Copies a directory from one place to another on the local filesystem.

        Defaults to copying the entire contents of the block's basepath to the current working directory.
        """
        if not from_path:
            from_path = Path(self.basepath or ".").expanduser().resolve()
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

    @async_dispatch(aget_directory)
    def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """
        Copies a directory from one place to another on the local filesystem.

        Defaults to copying the entire contents of the block's basepath to the current working directory.
        """
        if not from_path:
            from_path = Path(self.basepath or ".").expanduser().resolve()
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
            with open(from_path / Path(".prefectignore")) as f:
                ignore_patterns = f.readlines()
            included_files = filter_files(
                root=from_path, ignore_patterns=ignore_patterns
            )

            def ignore_func(directory, files):
                relative_path = Path(directory).relative_to(from_path)
                files_to_ignore = [
                    f for f in files if str(relative_path / f) not in included_files
                ]
                return files_to_ignore
        else:
            ignore_func = None

        copytree(from_path, local_path, dirs_exist_ok=True, ignore=ignore_func)

    async def _get_ignore_func(self, local_path: str, ignore_file: str):
        with open(ignore_file) as f:
            ignore_patterns = f.readlines()
        included_files = filter_files(root=local_path, ignore_patterns=ignore_patterns)

        def ignore_func(directory, files):
            relative_path = Path(directory).relative_to(local_path)

            files_to_ignore = [
                f for f in files if str(relative_path / f) not in included_files
            ]
            return files_to_ignore

        return ignore_func

    async def aput_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> None:
        """
        Copies a directory from one place to another on the local filesystem.

        Defaults to copying the entire contents of the current working directory to the block's basepath.
        An `ignore_file` path may be provided that can include gitignore style expressions for filepaths to ignore.
        """
        destination_path = self._resolve_path(to_path, validate=True)

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

    @async_dispatch(aput_directory)
    def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> None:
        """
        Copies a directory from one place to another on the local filesystem.

        Defaults to copying the entire contents of the current working directory to the block's basepath.
        An `ignore_file` path may be provided that can include gitignore style expressions for filepaths to ignore.
        """
        destination_path = self._resolve_path(to_path, validate=True)

        if not local_path:
            local_path = Path(".")

        if ignore_file:
            with open(ignore_file) as f:
                ignore_patterns = f.readlines()
            included_files = filter_files(
                root=local_path, ignore_patterns=ignore_patterns
            )

            def ignore_func(directory, files):
                relative_path = Path(directory).relative_to(local_path)
                files_to_ignore = [
                    f for f in files if str(relative_path / f) not in included_files
                ]
                return files_to_ignore
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

    async def aread_path(self, path: str) -> bytes:
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

    @async_dispatch(aread_path)
    def read_path(self, path: str) -> bytes:
        path: Path = self._resolve_path(path)

        # Check if the path exists
        if not path.exists():
            raise ValueError(f"Path {path} does not exist.")

        # Validate that its a file
        if not path.is_file():
            raise ValueError(f"Path {path} is not a file.")

        with open(str(path), mode="rb") as f:
            content = f.read()

        return content

    async def awrite_path(self, path: str, content: bytes) -> str:
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

    @async_dispatch(awrite_path)
    def write_path(self, path: str, content: bytes) -> str:
        path: Path = self._resolve_path(path)

        # Construct the path if it does not exist
        path.parent.mkdir(exist_ok=True, parents=True)

        # Check if the file already exists
        if path.exists() and not path.is_file():
            raise ValueError(f"Path {path} already exists and is not a file.")

        with open(path, mode="wb") as f:
            f.write(content)
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
        "https://docs.prefect.io/latest/develop/results#specifying-a-default-filesystem"
    )

    basepath: str = Field(
        default=...,
        description="Default path for this block to write to.",
        examples=["s3://my-bucket/my-folder/"],
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional settings to pass through to fsspec.",
    )

    # Cache for the configured fsspec file system used for access
    _filesystem: fsspec.AbstractFileSystem = None

    @field_validator("basepath")
    def check_basepath(cls, value: str) -> str:
        return validate_basepath(value)

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
            with open(ignore_file) as f:
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

        if self.basepath.startswith("smb://"):
            parsed = urllib.parse.urlparse(dirpath)
            dirpath = parsed.path

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
    _documentation_url = (
        "https://docs.prefect.io/latest/develop/results#specifying-a-default-filesystem"
    )

    share_path: str = Field(
        default=...,
        description="SMB target (requires <SHARE>, followed by <PATH>).",
        examples=["/SHARE/dir/subdir"],
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
        default=..., title="SMB server/hostname", description="SMB server/hostname."
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


class NullFileSystem(BaseModel):
    """
    A file system that does not store any data.
    """

    async def read_path(self, path: str) -> None:
        pass

    async def write_path(self, path: str, content: bytes) -> None:
        pass

    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        pass

    async def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> None:
        pass


__getattr__: Callable[[str], Any] = getattr_migration(__name__)
