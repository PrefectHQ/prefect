from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TypedDict, cast

import typer

import prefect_azure.credentials

logger = logging.getLogger("prefect_azure.experimental.bundles.upload")


class UploadBundleToAzureBlobStorageOutput(TypedDict):
    container: str
    key: str


async def upload_bundle_to_azure_blob_storage(
    local_filepath: Path,
    container: str,
    key: str,
    azure_blob_storage_credentials_block_name: str,
) -> UploadBundleToAzureBlobStorageOutput:
    if not local_filepath.exists():
        raise ValueError(f"Bundle file not found: {local_filepath}")

    key = key or local_filepath.name

    if azure_blob_storage_credentials_block_name:
        logger.debug(
            "Loading Azure credentials from block %s",
            azure_blob_storage_credentials_block_name,
        )
        abs_credentials = cast(
            prefect_azure.credentials.AzureBlobStorageCredentials,
            await prefect_azure.credentials.AzureBlobStorageCredentials.load(
                azure_blob_storage_credentials_block_name,
                _sync=False,  # pyright: ignore[reportCallIssue] _sync is needed to prevent incidental async
            ),
        )
    else:
        logger.debug("Loading default Azure credentials")
        abs_credentials = prefect_azure.credentials.AzureBlobStorageCredentials()

    container_client = abs_credentials.get_container_client(container=container)

    try:
        logger.debug(
            "Uploading bundle from path %s to Azure Blob Storage container %s with key %s",
            local_filepath,
            container,
            key,
        )
        with open(local_filepath, "rb") as f:
            await container_client.upload_blob(key, f)  # pyright: ignore[reportUnknownMemberType] Incomplete type hints
    except Exception as e:
        raise RuntimeError(f"Failed to upload bundle to Azure Blob Storage: {e}")

    return {"container": container, "key": key}


def _cli_wrapper(
    local_filepath: Path = typer.Argument(
        ..., help="The path to the bundle file to upload."
    ),
    container: str = typer.Option(
        ...,
        help="The name of the Azure Blob Storage container to upload the bundle to.",
    ),
    key: str = typer.Option(
        ...,
        help="The key (path) to upload the bundle to in the Azure Blob Storage container.",
    ),
    azure_blob_storage_credentials_block_name: str = typer.Option(
        ...,
        help="The name of the Azure Blob Storage credentials block to use for authentication. If not provided, the default credentials will be used.",
    ),
) -> UploadBundleToAzureBlobStorageOutput:
    """
    Uploads a bundle file to an Azure Blob Storage container.
    """
    return asyncio.run(
        upload_bundle_to_azure_blob_storage(
            local_filepath, container, key, azure_blob_storage_credentials_block_name
        )
    )


if __name__ == "__main__":
    typer.run(_cli_wrapper)
