import abc
import urllib.parse
from pathlib import Path
from typing import Optional

import anyio
import fsspec
from pydantic import Field, validator

from prefect.blocks.core import Block
from prefect.utilities.asyncutils import run_sync_in_worker_thread


class ReadableFileSystem(Block, abc.ABC):
    _block_schema_capabilities = ["read-path"]

    @abc.abstractmethod
    async def read_path(self, path: str) -> bytes:
        pass


class WritableFileSystem(Block, abc.ABC):
    _block_schema_capabilities = ["write-path"]

    @abc.abstractmethod
    async def write_path(self, path: str, content: bytes) -> None:
        pass


class LocalFileSystem(ReadableFileSystem, WritableFileSystem):
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
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/EVKjxM7fNyi4NGUSkeTEE/95c958c5dd5a56c59ea5033e919c1a63/image1.png?h=250"

    basepath: Optional[str] = None

    @validator("basepath", pre=True)
    def cast_pathlib(cls, value):
        if isinstance(value, Path):
            return str(value)
        return value

    def _resolve_path(self, path: str) -> Path:
        # Only resolve the base path at runtime, default to the current directory
        basepath = (
            Path(self.basepath).resolve() if self.basepath else Path(".").resolve()
        )

        # Determine the path to access relative to the base path, ensuring that paths
        # outside of the base path are off limits
        path: Path = Path(path)
        if not path.is_absolute():
            path = basepath / path
        else:
            path = path.resolve()
            if not basepath in path.parents:
                raise ValueError(
                    f"Attempted to write to path {path} outside of the base path {basepath}."
                )

        return path

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

    async def write_path(self, path: str, content: bytes) -> str:
        path: Path = self._resolve_path(path)

        # Construct the path if it does not exist
        path.parent.mkdir(exist_ok=True, parents=True)

        # Check if the file already exists
        if path.exists() and not path.is_file():
            raise ValueError(f"Path {path} already exists and is not a file.")

        async with await anyio.open_file(path, mode="wb") as f:
            await f.write(content)


class RemoteFileSystem(ReadableFileSystem, WritableFileSystem):
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
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/4CxjycqILlT9S9YchI7o1q/ee62e2089dfceb19072245c62f0c69d2/image12.png?h=250"

    basepath: str
    settings: dict = Field(default_factory=dict)

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
                "Base path scheme cannot be 'file'. Use `LocalFileSystem` instead for local file access."
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
                    f"Path {path!r} with scheme {scheme!r} must use the same scheme as the base path {base_scheme!r}."
                )

        if netloc:
            if (netloc != base_netloc) or not urlpath.startswith(base_urlpath):
                raise ValueError(
                    f"Path {path!r} is outside of the base path {self.basepath!r}."
                )

        return f"{self.basepath.rstrip('/')}/{urlpath.lstrip('/')}"

    async def read_path(self, path: str) -> bytes:
        path = self._resolve_path(path)

        with self.filesystem.open(path, "rb") as file:
            content = await run_sync_in_worker_thread(file.read)

        return content

    async def write_path(self, path: str, content: bytes) -> str:
        path = self._resolve_path(path)
        dirpath = path[: path.rindex("/")]

        self.filesystem.makedirs(dirpath, exist_ok=True)

        with self.filesystem.open(path, "wb") as file:
            await run_sync_in_worker_thread(file.write, content)

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
