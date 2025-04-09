from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, TypedDict, cast

import typer

import prefect_gcp.credentials

logger = logging.getLogger("prefect_gcp.experimental.bundles.upload")


class UploadBundleToGcsOutput(TypedDict):
    """
    The output of the `upload_bundle_to_gcs` step.
    """

    bucket: str
    key: str


def upload_bundle_to_gcs(
    local_filepath: Path,
    bucket: str,
    key: str,
    gcp_credentials_block_name: str | None = None,
) -> UploadBundleToGcsOutput:
    """
    Uploads a bundle file to a GCS bucket.

    Args:
        local_filepath: The path to the bundle file to upload.
        bucket: The name of the GCS bucket to upload the bundle to.
        key: The key (path) to upload the bundle to in the GCS bucket.
        gcp_credentials_block_name: The name of the GCP credentials block to use.

    Returns:
        A dictionary containing the bucket and key of the uploaded bundle.
    """
    if not local_filepath.exists():
        raise ValueError(f"Bundle file not found: {local_filepath}")

    key = key or local_filepath.name

    if gcp_credentials_block_name:
        logger.debug(
            "Loading GCP credentials from block %s", gcp_credentials_block_name
        )
        gcp_credentials = cast(
            prefect_gcp.credentials.GcpCredentials,
            prefect_gcp.credentials.GcpCredentials.load(
                gcp_credentials_block_name,
                _sync=True,  # pyright: ignore[reportCallIssue] _sync is needed to prevent incidental async
            ),
        )
    else:
        logger.debug("Loading default GCP credentials")
        gcp_credentials = prefect_gcp.credentials.GcpCredentials()

    gcs_client = gcp_credentials.get_cloud_storage_client()

    try:
        logger.debug(
            "Uploading bundle from path %s to GCS bucket %s with key %s",
            local_filepath,
            bucket,
            key,
        )
        gcs_client.bucket(bucket).blob(key).upload_from_file(local_filepath)  # pyright: ignore[reportUnknownMemberType] Incomplete type hints
    except Exception as e:
        raise RuntimeError(f"Failed to upload bundle to GCS: {e}")

    return {"bucket": bucket, "key": key}


def _cli_wrapper(
    local_filepath: Path = typer.Argument(
        ..., help="The path to the bundle file to upload."
    ),
    bucket: str = typer.Option(
        ..., help="The name of the GCS bucket to upload the bundle to."
    ),
    key: str = typer.Option(
        ..., help="The key (path) to upload the bundle to in the GCS bucket."
    ),
    gcp_credentials_block_name: Optional[str] = typer.Option(
        None,
        help="The name of the GCP credentials block to use for authentication. If not provided, the default credentials will be used.",
    ),
) -> UploadBundleToGcsOutput:
    """
    Uploads a bundle file to a GCS bucket.
    """
    return upload_bundle_to_gcs(local_filepath, bucket, key, gcp_credentials_block_name)


if __name__ == "__main__":
    typer.run(_cli_wrapper)
