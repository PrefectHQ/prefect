from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import cast

import typer
from pydantic_core import from_json

import prefect.runner
import prefect_azure.credentials
from prefect._experimental.bundles.zip_extractor import ZipExtractor

logger = logging.getLogger("prefect_azure.experimental.bundles.execute")


async def execute_bundle_from_azure_blob_storage(
    container: str,
    key: str,
    azure_blob_storage_credentials_block_name: str,
):
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

    blob_client = abs_credentials.get_blob_client(container=container, blob=key)

    try:
        logger.debug(
            "Downloading bundle from Azure Blob Storage container %s with key %s",
            container,
            key,
        )
        blob_obj = await blob_client.download_blob()
        bundle = from_json(await blob_obj.content_as_bytes())

        # Extract included files if present
        files_key = bundle.get("files_key")
        if files_key:
            logger.info(f"Downloading included files from {files_key}")
            files_blob_client = abs_credentials.get_blob_client(
                container=container, blob=files_key
            )
            files_blob_obj = await files_blob_client.download_blob()
            files_content = await files_blob_obj.content_as_bytes()

            # Write to temp file and extract
            with tempfile.NamedTemporaryFile(
                suffix=".zip", delete=False, prefix="prefect-files-"
            ) as tmp_file:
                tmp_file.write(files_content)
                tmp_path = Path(tmp_file.name)

            extractor = ZipExtractor(tmp_path)
            try:
                extracted = extractor.extract()
                logger.info(f"Extracted {len(extracted)} files to working directory")
                extractor.cleanup()
            except Exception as e:
                # Clean up temp file on failure
                tmp_path.unlink(missing_ok=True)
                raise RuntimeError(f"Failed to extract included files: {e}") from e

        logger.debug("Executing bundle")
        await prefect.runner.Runner().execute_bundle(bundle)
    except Exception as e:
        raise RuntimeError(f"Failed to download bundle from Azure Blob Storage: {e}")


def _cli_wrapper(
    container: str = typer.Option(
        ...,
        help="The name of the Azure Blob Storage container to download the bundle from.",
    ),
    key: str = typer.Option(
        ...,
        help="The key (path) to download the bundle from in the Azure Blob Storage container.",
    ),
    azure_blob_storage_credentials_block_name: str = typer.Option(
        ...,
        help="The name of the Azure Blob Storage credentials block to use for authentication. If not provided, the default credentials will be used.",
    ),
) -> None:
    return asyncio.run(
        execute_bundle_from_azure_blob_storage(
            container, key, azure_blob_storage_credentials_block_name
        )
    )


if __name__ == "__main__":
    typer.run(_cli_wrapper)
