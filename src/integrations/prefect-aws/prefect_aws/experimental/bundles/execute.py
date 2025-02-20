from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional, TypedDict

import typer
from botocore.exceptions import ClientError
from pydantic_core import from_json

from prefect.runner import Runner
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect_aws.credentials import AwsCredentials

from .types import AwsCredentialsBlockName, S3Bucket, S3Key


class DownloadResult(TypedDict):
    """Result of downloading a bundle from S3."""

    local_path: str
    """Local path where the bundle was downloaded."""


def download_bundle_from_s3(
    bucket: S3Bucket,
    key: S3Key,
    output_dir: str | None = None,
    aws_credentials_block_name: Optional[AwsCredentialsBlockName] = None,
) -> DownloadResult:
    """
    Downloads a bundle from an S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        output_dir: Local directory to save the bundle (if None, uses a temp directory)
        aws_credentials_block_name: Name of the AWS credentials block to use. If None,
            credentials will be inferred from the environment using boto3's standard
            credential resolution.

    Returns:
        A dictionary containing:
            - local_path: Path where the bundle was downloaded
    """

    if aws_credentials_block_name:
        aws_credentials = AwsCredentials.load(aws_credentials_block_name)
    else:
        aws_credentials = AwsCredentials()

    s3 = aws_credentials.get_s3_client()

    output_dir = output_dir or tempfile.mkdtemp(prefix="prefect-bundle-")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    local_path = Path(output_dir) / os.path.basename(key)

    try:
        s3.download_file(bucket, key, str(local_path))
        return {"local_path": str(local_path)}
    except ClientError as e:
        raise RuntimeError(f"Failed to download bundle from S3: {e}")


def execute_bundle_from_s3(
    bucket: S3Bucket,
    key: S3Key,
    aws_credentials_block_name: Optional[AwsCredentialsBlockName] = None,
) -> None:
    """
    Downloads a bundle from S3 and executes it.

    This step:
    1. Downloads the bundle from S3
    2. Extracts and deserializes the bundle
    3. Executes the flow in a subprocess

    Args:
        bucket: S3 bucket name
        key: S3 object key
        aws_credentials_block_name: Name of the AWS credentials block to use. If None,
            credentials will be inferred from the environment using boto3's standard
            credential resolution.
    """
    download_result = download_bundle_from_s3(
        bucket=bucket,
        key=key,
        aws_credentials_block_name=aws_credentials_block_name,
    )

    bundle_data = from_json(Path(download_result["local_path"]).read_bytes())

    run_coro_as_sync(Runner().execute_bundle(bundle_data))


if __name__ == "__main__":
    typer.run(execute_bundle_from_s3)
