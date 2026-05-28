"""Integrations for interacting with Azure Blob Storage"""

import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, List, Optional, Union

from azure.core.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from azure.storage.blob import BlobProperties


from pydantic import Field

from prefect import task
from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.blocks.abstract import ObjectStorageBlock
from prefect.filesystems import WritableDeploymentStorage, WritableFileSystem
from prefect.logging import get_run_logger
from prefect.utilities.filesystem import filter_files
from prefect_azure.credentials import AzureBlobStorageCredentials


@task
async def blob_storage_download(
    container: str,
    blob: str,
    blob_storage_credentials: "AzureBlobStorageCredentials",
) -> bytes:
    """
    Downloads a blob with a given key from a given Blob Storage container.
    Args:
        blob: Name of the blob within this container to retrieve.
        container: Name of the Blob Storage container to retrieve from.
        blob_storage_credentials: Credentials to use for authentication with Azure.
    Returns:
        A `bytes` representation of the downloaded blob.
    Example:
        Download a file from a Blob Storage container
        ```python
        from prefect import flow

        from prefect_azure import AzureBlobStorageCredentials
        from prefect_azure.blob_storage import blob_storage_download

        @flow
        def example_blob_storage_download_flow():
            connection_string = "connection_string"
            blob_storage_credentials = AzureBlobStorageCredentials(
                connection_string=connection_string,
            )
            data = blob_storage_download(
                container="prefect",
                blob="prefect.txt",
                blob_storage_credentials=blob_storage_credentials,
            )
            return data

        example_blob_storage_download_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Downloading blob from container %s with key %s", container, blob)

    async with blob_storage_credentials as credentials:
        async with credentials.get_blob_client(container, blob) as blob_client:
            blob_obj = await blob_client.download_blob()
        output = await blob_obj.content_as_bytes()

    return output


@task
async def blob_storage_upload(
    data: bytes,
    container: str,
    blob_storage_credentials: "AzureBlobStorageCredentials",
    blob: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """
    Uploads data to an Blob Storage container.
    Args:
        data: Bytes representation of data to upload to Blob Storage.
        container: Name of the Blob Storage container to upload to.
        blob_storage_credentials: Credentials to use for authentication with Azure.
        blob: Name of the blob within this container to retrieve.
        overwrite: If `True`, an existing blob with the same name will be overwritten.
            Defaults to `False` and an error will be thrown if the blob already exists.
    Returns:
        The blob name of the uploaded object
    Example:
        Read and upload a file to a Blob Storage container
        ```python
        from prefect import flow

        from prefect_azure import AzureBlobStorageCredentials
        from prefect_azure.blob_storage import blob_storage_upload

        @flow
        def example_blob_storage_upload_flow():
            connection_string = "connection_string"
            blob_storage_credentials = AzureBlobStorageCredentials(
                connection_string=connection_string,
            )
            with open("data.csv", "rb") as f:
                blob = blob_storage_upload(
                    data=f.read(),
                    container="container",
                    blob="data.csv",
                    blob_storage_credentials=blob_storage_credentials,
                    overwrite=False,
                )
            return blob

        example_blob_storage_upload_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Uploading blob to container %s with key %s", container, blob)

    # create key if not provided
    if blob is None:
        blob = str(uuid.uuid4())

    async with blob_storage_credentials as credentials:
        async with credentials.get_blob_client(container, blob) as blob_client:
            await blob_client.upload_blob(data, overwrite=overwrite)

    return blob


@task
async def blob_storage_list(
    container: str,
    blob_storage_credentials: "AzureBlobStorageCredentials",
    name_starts_with: Optional[str] = None,
    include: Union[str, List[str], None] = None,
    **kwargs,
) -> List["BlobProperties"]:
    """
    List objects from a given Blob Storage container.
    Args:
        container: Name of the Blob Storage container to retrieve from.
        blob_storage_credentials: Credentials to use for authentication with Azure.
        name_starts_with: Filters the results to return only blobs whose names
            begin with the specified prefix.
        include: Specifies one or more additional datasets to include in the response.
            Options include: 'snapshots', 'metadata', 'uncommittedblobs', 'copy',
            'deleted', 'deletedwithversions', 'tags', 'versions', 'immutabilitypolicy',
            'legalhold'.
        **kwargs: Additional kwargs passed to `ContainerClient.list_blobs()`
    Returns:
        A `list` of `dict`s containing metadata about the blob.
    Example:
        ```python
        from prefect import flow

        from prefect_azure import AzureBlobStorageCredentials
        from prefect_azure.blob_storage import blob_storage_list

        @flow
        def example_blob_storage_list_flow():
            connection_string = "connection_string"
            blob_storage_credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            data = blob_storage_list(
                container="container",
                blob_storage_credentials=blob_storage_credentials,
            )
            return data

        example_blob_storage_list_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Listing blobs from container %s", container)

    async with blob_storage_credentials as credentials:
        async with credentials.get_container_client(container) as container_client:
            blobs = [
                blob
                async for blob in container_client.list_blobs(
                    name_starts_with=name_starts_with, include=include, **kwargs
                )
            ]

        return blobs


class AzureBlobStorageContainer(
    ObjectStorageBlock, WritableFileSystem, WritableDeploymentStorage
):
    """
    Represents a container in Azure Blob Storage.

    This class provides methods for downloading and uploading files and folders
    to and from the Azure Blob Storage container.

    Attributes:
        container_name: The name of the Azure Blob Storage container.
        credentials: The credentials to use for authentication with Azure.
        base_folder: A base path to a folder within the container to use
            for reading and writing objects.
    """

    _block_type_name = "Azure Blob Storage Container"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"  # noqa
    _documentation_url = "https://docs.prefect.io/integrations/prefect-azure"  # noqa

    container_name: str = Field(
        default=..., description="The name of a Azure Blob Storage container."
    )
    credentials: AzureBlobStorageCredentials = Field(
        default_factory=AzureBlobStorageCredentials,
        description="The credentials to use for authentication with Azure.",
    )
    base_folder: Optional[str] = Field(
        default=None,
        description=(
            "A base path to a folder within the container to use "
            "for reading and writing objects."
        ),
    )

    def _get_path_relative_to_base_folder(self, path: Optional[str] = None) -> str:
        if path is None and self.base_folder is None:
            return ""
        if path is None:
            return self.base_folder
        if self.base_folder is None:
            return path
        return (Path(self.base_folder) / Path(path)).as_posix()

    async def adownload_folder_to_path(
        self,
        from_folder: str,
        to_folder: Union[str, Path],
        **download_kwargs: Dict[str, Any],
    ) -> Path:
        """Download a folder from the container to a local path (async version).

        See `download_folder_to_path` for details.
        """
        self.logger.info(
            "Downloading folder from container %s to path %s",
            self.container_name,
            to_folder,
        )
        full_container_path = self._get_path_relative_to_base_folder(from_folder)
        async with self.credentials as credentials:
            async with credentials.get_container_client(
                self.container_name
            ) as container_client:
                try:
                    async for blob in container_client.list_blobs(
                        name_starts_with=full_container_path
                    ):
                        blob_path = blob.name
                        local_path = Path(to_folder) / Path(blob_path).relative_to(
                            full_container_path
                        )
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        async with container_client.get_blob_client(
                            blob_path
                        ) as blob_client:
                            blob_obj = await blob_client.download_blob(
                                **download_kwargs
                            )

                        with local_path.open(mode="wb") as to_file:
                            await blob_obj.readinto(to_file)
                except ResourceNotFoundError as exc:
                    raise RuntimeError(
                        "An error occurred when attempting to download from container"
                        f" {self.container_name}: {exc.reason}"
                    ) from exc

                return Path(to_folder)

    @async_dispatch(adownload_folder_to_path)
    def download_folder_to_path(
        self,
        from_folder: str,
        to_folder: Union[str, Path],
        **download_kwargs: Dict[str, Any],
    ) -> Path:
        """Download a folder from the container to a local path.

        Args:
            from_folder: The folder path in the container to download.
            to_folder: The local path to download the folder to.
            **download_kwargs: Additional keyword arguments passed into
                `BlobClient.download_blob`.

        Returns:
            The local path where the folder was downloaded.

        Example:
            Download the contents of container folder `folder` from the container
                to the local folder `local_folder`:

            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            block.download_folder_to_path(
                from_folder="folder",
                to_folder="local_folder"
            )
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.adownload_folder_to_path,
                from_folder,
                to_folder,
                **download_kwargs,
            )
        ).result()

    async def adownload_object_to_file_object(
        self,
        from_path: str,
        to_file_object: BinaryIO,
        **download_kwargs: Dict[str, Any],
    ) -> BinaryIO:
        """Download an object from the container to a file object (async version).

        See `download_object_to_file_object` for details.
        """
        self.logger.info(
            "Downloading object from container %s to file object", self.container_name
        )
        full_container_path = self._get_path_relative_to_base_folder(from_path)
        async with self.credentials as credentials:
            async with credentials.get_blob_client(
                self.container_name, full_container_path
            ) as blob_client:
                try:
                    blob_obj = await blob_client.download_blob(**download_kwargs)
                    await blob_obj.download_to_stream(to_file_object)
                except ResourceNotFoundError as exc:
                    raise RuntimeError(
                        "An error occurred when attempting to download from container"
                        f" {self.container_name}: {exc.reason}"
                    ) from exc

            return to_file_object

    @async_dispatch(adownload_object_to_file_object)
    def download_object_to_file_object(
        self,
        from_path: str,
        to_file_object: BinaryIO,
        **download_kwargs: Dict[str, Any],
    ) -> BinaryIO:
        """
        Downloads an object from the container to a file object.

        Args:
            from_path : The path of the object to download within the container.
            to_file_object: The file object to download the object to.
            **download_kwargs: Additional keyword arguments for the download
                operation.

        Returns:
            The file object that the object was downloaded to.

        Example:
            Download the object `object` from the container to a file object:

            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            with open("file.txt", "wb") as f:
                block.download_object_to_file_object(
                    from_path="object",
                    to_file_object=f
                )
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.adownload_object_to_file_object,
                from_path,
                to_file_object,
                **download_kwargs,
            )
        ).result()

    async def adownload_object_to_path(
        self,
        from_path: str,
        to_path: Union[str, Path],
        **download_kwargs: Dict[str, Any],
    ) -> Path:
        """Download an object from the container to a specified path (async version).

        See `download_object_to_path` for details.
        """
        self.logger.info(
            "Downloading object from container %s to path %s",
            self.container_name,
            to_path,
        )
        full_container_path = self._get_path_relative_to_base_folder(from_path)
        async with self.credentials as credentials:
            async with credentials.get_blob_client(
                self.container_name, full_container_path
            ) as blob_client:
                try:
                    blob_obj = await blob_client.download_blob(**download_kwargs)

                    path = Path(to_path)

                    path.parent.mkdir(parents=True, exist_ok=True)

                    with path.open(mode="wb") as to_file:
                        await blob_obj.readinto(to_file)
                except ResourceNotFoundError as exc:
                    raise RuntimeError(
                        "An error occurred when attempting to download from container"
                        f" {self.container_name}: {exc.reason}"
                    ) from exc
                return path

    @async_dispatch(adownload_object_to_path)
    def download_object_to_path(
        self,
        from_path: str,
        to_path: Union[str, Path],
        **download_kwargs: Dict[str, Any],
    ) -> Path:
        """
        Downloads an object from a container to a specified path.

        Args:
            from_path: The path of the object in the container.
            to_path: The path where the object will be downloaded to.
            **download_kwargs (Dict[str, Any]): Additional keyword arguments
                for the download operation.

        Returns:
            The path where the object was downloaded to.

        Example:
            Download the object `object` from the container to the local path
                `file.txt`:

            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            block.download_object_to_path(
                from_path="object",
                to_path="file.txt"
            )
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.adownload_object_to_path,
                from_path,
                to_path,
                **download_kwargs,
            )
        ).result()

    async def aupload_from_file_object(
        self, from_file_object: BinaryIO, to_path: str, **upload_kwargs: Dict[str, Any]
    ) -> str:
        """Upload an object from a file object to the container (async version).

        See `upload_from_file_object` for details.
        """
        self.logger.info(
            "Uploading object to container %s with key %s", self.container_name, to_path
        )
        full_container_path = self._get_path_relative_to_base_folder(to_path)
        async with self.credentials as credentials:
            async with credentials.get_blob_client(
                self.container_name, full_container_path
            ) as blob_client:
                try:
                    await blob_client.upload_blob(from_file_object, **upload_kwargs)
                except ResourceNotFoundError as exc:
                    raise RuntimeError(
                        "An error occurred when attempting to upload from container"
                        f" {self.container_name}: {exc.reason}"
                    ) from exc

            return to_path

    @async_dispatch(aupload_from_file_object)
    def upload_from_file_object(
        self, from_file_object: BinaryIO, to_path: str, **upload_kwargs: Dict[str, Any]
    ) -> str:
        """
        Uploads an object from a file object to the specified path in the blob
            storage container.

        Args:
            from_file_object: The file object to upload.
            to_path: The path in the blob storage container to upload the
                object to.
            **upload_kwargs: Additional keyword arguments to pass to the
                upload_blob method.

        Returns:
            The path where the object was uploaded to.

        Example:
            Upload a file object to the container at the path `object`:

            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            with open("file.txt", "rb") as f:
                block.upload_from_file_object(
                    from_file_object=f,
                    to_path="object"
                )
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.aupload_from_file_object,
                from_file_object,
                to_path,
                **upload_kwargs,
            )
        ).result()

    async def aupload_from_path(
        self, from_path: Union[str, Path], to_path: str, **upload_kwargs: Dict[str, Any]
    ) -> str:
        """Upload an object from a local path to the container (async version).

        See `upload_from_path` for details.
        """
        self.logger.info(
            "Uploading object to container %s with key %s", self.container_name, to_path
        )
        full_container_path = self._get_path_relative_to_base_folder(to_path)
        async with self.credentials as credentials:
            async with credentials.get_blob_client(
                self.container_name, full_container_path
            ) as blob_client:
                try:
                    with open(from_path, "rb") as f:
                        await blob_client.upload_blob(f, **upload_kwargs)
                except ResourceNotFoundError as exc:
                    raise RuntimeError(
                        "An error occurred when attempting to upload to container"
                        f" {self.container_name}: {exc.reason}"
                    ) from exc

            return to_path

    @async_dispatch(aupload_from_path)
    def upload_from_path(
        self, from_path: Union[str, Path], to_path: str, **upload_kwargs: Dict[str, Any]
    ) -> str:
        """
        Uploads an object from a local path to the specified destination path in the
            blob storage container.

        Args:
            from_path: The local path of the object to upload.
            to_path: The destination path in the blob storage container.
            **upload_kwargs: Additional keyword arguments to pass to the
                `upload_blob` method.

        Returns:
            The destination path in the blob storage container.

        Example:
            Upload a file from the local path `file.txt` to the container
                at the path `object`:

            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            block.upload_from_path(
                from_path="file.txt",
                to_path="object"
            )
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.aupload_from_path,
                from_path,
                to_path,
                **upload_kwargs,
            )
        ).result()

    async def aupload_from_folder(
        self,
        from_folder: Union[str, Path],
        to_folder: str,
        **upload_kwargs: Dict[str, Any],
    ) -> str:
        """Upload files from a local folder to the container (async version).

        See `upload_from_folder` for details.
        """
        self.logger.info(
            "Uploading folder to container %s with key %s",
            self.container_name,
            to_folder,
        )
        full_container_path = self._get_path_relative_to_base_folder(to_folder)
        async with self.credentials as credentials:
            async with credentials.get_container_client(
                self.container_name
            ) as container_client:
                if not Path(from_folder).is_dir():
                    raise ValueError(f"{from_folder} is not a directory")
                for path in Path(from_folder).rglob("*"):
                    if path.is_file():
                        blob_path = Path(full_container_path) / path.relative_to(
                            from_folder
                        )
                        async with container_client.get_blob_client(
                            blob_path.as_posix()
                        ) as blob_client:
                            try:
                                await blob_client.upload_blob(
                                    path.read_bytes(), **upload_kwargs
                                )
                            except ResourceNotFoundError as exc:
                                raise RuntimeError(
                                    "An error occurred when attempting to upload to "
                                    f"container {self.container_name}: {exc.reason}"
                                ) from exc
            return full_container_path

    @async_dispatch(aupload_from_folder)
    def upload_from_folder(
        self,
        from_folder: Union[str, Path],
        to_folder: str,
        **upload_kwargs: Dict[str, Any],
    ) -> str:
        """
        Uploads files from a local folder to a specified folder in the Azure
            Blob Storage container.

        Args:
            from_folder: The path to the local folder containing the files to upload.
            to_folder: The destination folder in the Azure Blob Storage container.
            **upload_kwargs: Additional keyword arguments to pass to the
                `upload_blob` method.

        Returns:
            The full path of the destination folder in the container.

        Example:
            Upload the contents of the local folder `local_folder` to the container
                folder `folder`:

            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            block.upload_from_folder(
                from_folder="local_folder",
                to_folder="folder"
            )
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.aupload_from_folder,
                from_folder,
                to_folder,
                **upload_kwargs,
            )
        ).result()

    async def aget_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """Download the contents of a directory to a local path (async version).

        See `get_directory` for details.
        """
        await self.adownload_folder_to_path(from_path, local_path)

    @async_dispatch(aget_directory)
    def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """
        Downloads the contents of a directory from the blob storage to a local path.

        Used to enable flow code storage for deployments.

        Args:
            from_path: The path of the directory in the blob storage.
            local_path: The local path where the directory will be downloaded.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.aget_directory, from_path, local_path)
        ).result()

    async def aput_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> None:
        """Upload a directory to the blob storage (async version).

        See `put_directory` for details.
        """
        to_path = "" if to_path is None else to_path

        if local_path is None:
            local_path = "."

        included_files = None
        if ignore_file:
            with open(ignore_file, "r") as f:
                ignore_patterns = f.readlines()

            included_files = filter_files(local_path, ignore_patterns)

        for local_file_path in Path(local_path).expanduser().rglob("*"):
            if (
                included_files is not None
                and str(local_file_path.relative_to(local_path)) not in included_files
            ):
                continue
            elif not local_file_path.is_dir():
                remote_file_path = Path(to_path) / local_file_path.relative_to(
                    local_path
                )
                with open(local_file_path, "rb") as local_file:
                    local_file_content = local_file.read()

                await self.awrite_path(
                    remote_file_path.as_posix(), content=local_file_content
                )

    @async_dispatch(aput_directory)
    def put_directory(
        self,
        local_path: Optional[str] = None,
        to_path: Optional[str] = None,
        ignore_file: Optional[str] = None,
    ) -> None:
        """
        Uploads a directory to the blob storage.

        Used to enable flow code storage for deployments.

        Args:
            local_path: The local path of the directory to upload. Defaults to
                current directory.
            to_path: The destination path in the blob storage. Defaults to
                root directory.
            ignore_file: The path to a file containing patterns to ignore
                during upload.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.aput_directory, local_path, to_path, ignore_file)
        ).result()

    async def aread_path(self, path: str) -> bytes:
        """Read the contents of a file at the specified path (async version).

        See `read_path` for details.
        """
        file_obj = BytesIO()
        await self.adownload_object_to_file_object(path, file_obj)
        return file_obj.getvalue()

    @async_dispatch(aread_path)
    def read_path(self, path: str) -> bytes:
        """
        Reads the contents of a file at the specified path and returns it as bytes.

        Used to enable results storage.

        Args:
            path: The path of the file to read.

        Returns:
            The contents of the file as bytes.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.aread_path, path)
        ).result()

    async def awrite_path(self, path: str, content: bytes) -> None:
        """Write content to the specified path in the blob storage (async version).

        See `write_path` for details.
        """
        # `write_path` backs results storage, where re-writing an existing key
        # (e.g. when a task runs with `refresh_cache=True`) must replace the
        # existing blob rather than raise `ResourceExistsError`.
        await self.aupload_from_file_object(BytesIO(content), path, overwrite=True)

    @async_dispatch(awrite_path)
    def write_path(self, path: str, content: bytes) -> None:
        """
        Writes the content to the specified path in the blob storage.

        Used to enable results storage.

        Args:
            path: The path where the content will be written.
            content: The content to be written.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.awrite_path, path, content)
        ).result()

    async def alist_blobs(self) -> List[str]:
        """List blobs available within the specified Azure container (async version).

        See `list_blobs` for details.
        """
        self.logger.info(
            "Listing the blobs within container %s",
            self.container_name,
        )

        async with self.credentials as credentials:
            async with credentials.get_container_client(
                self.container_name
            ) as container_client:
                blobs = container_client.list_blobs()
                filenames = []
                async for blob in blobs:
                    filenames.append(blob.name)
            return filenames

    @async_dispatch(alist_blobs)
    def list_blobs(self) -> List[str]:
        """
        Lists blobs available within the specified Azure container.

        Used to introspect your containers.

        Returns:
            A list of the blobs within your container.

        Example:
            List the blobs associated with a container.
            ```python
            from prefect_azure import AzureBlobStorageCredentials
            from prefect_azure.blob_storage import AzureBlobStorageContainer

            credentials = AzureBlobStorageCredentials(
                connection_string="connection_string",
            )
            block = AzureBlobStorageContainer(
                container_name="container",
                credentials=credentials,
            )
            block.list_blobs()
            ```
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.alist_blobs)
        ).result()
