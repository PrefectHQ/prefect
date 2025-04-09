import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, cast

import typer
from pydantic_core import from_json

import prefect.runner
import prefect_gcp.credentials
from prefect.utilities.asyncutils import run_coro_as_sync

logger = logging.getLogger("prefect_gcp.experimental.bundles.execute")


def execute_bundle_from_gcs(
    bucket: str,
    key: str,
    gcp_credentials_block_name: Optional[str] = None,
) -> None:
    if isinstance(gcp_credentials_block_name, str):
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

    with tempfile.TemporaryDirectory(prefix="prefect-bundle-") as tmp_dir:
        local_path = Path(tmp_dir) / os.path.basename(key)

        try:
            logger.debug(
                "Downloading bundle from GCS bucket %s with key %s to local path %s",
                bucket,
                key,
                local_path,
            )
            gcs_client.bucket(bucket).blob(key).download_to_file(str(local_path))  # pyright: ignore[reportUnknownMemberType] Incomplete type hints
            bundle = from_json(local_path.read_bytes())

            logger.debug("Executing bundle")
            run_coro_as_sync(prefect.runner.Runner().execute_bundle(bundle))
        except Exception as e:
            raise RuntimeError(f"Failed to download bundle from GCS: {e}")


def _cli_wrapper(
    bucket: str = typer.Option(...),
    key: str = typer.Option(...),
    gcp_credentials_block_name: Optional[str] = typer.Option(None),
) -> None:
    execute_bundle_from_gcs(bucket, key, gcp_credentials_block_name)


if __name__ == "__main__":
    typer.run(_cli_wrapper)
