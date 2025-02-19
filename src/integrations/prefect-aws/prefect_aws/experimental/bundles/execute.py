from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

import typer
from botocore.exceptions import ClientError
from pydantic_core import from_json

from prefect.runner import Runner
from prefect_aws.credentials import AwsCredentials

from .types import AwsCredentialsBlockName, S3Bucket, S3Key


async def download_bundle_from_s3(
    bucket: S3Bucket,
    key: S3Key,
    output_dir: str | None = None,
    aws_credentials_block_name: AwsCredentialsBlockName | None = None,
) -> dict[str, Any]:
    """
    Downloads a bundle from an S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        output_dir: Local directory to save the bundle (if None, uses a temp directory)
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        aws_session_token: AWS session token
        region_name: AWS region name

    Returns:
        Dictionary containing the local path to the downloaded bundle

    Example:
        ```yaml
        pull:
            - prefect_aws.deployments.steps.download_bundle_from_s3:
                requires: prefect-aws
                bucket: my-prefect-bundles
                key: bundles/my-flow-bundle.json
                output_dir: /tmp/prefect-bundles
        ```
    """

    # Set up S3 client with credentials if provided
    if aws_credentials_block_name:
        aws_credentials = AwsCredentials.load(aws_credentials_block_name)
    else:
        aws_credentials = AwsCredentials()

    s3 = aws_credentials.get_s3_client()

    # Determine local path
    output_dir = output_dir or tempfile.mkdtemp(prefix="prefect-bundle-")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    local_path = Path(output_dir) / os.path.basename(key)

    try:
        # Download the file
        s3.download_file(bucket, key, local_path)
        return {"local_path": local_path}
    except ClientError as e:
        raise RuntimeError(f"Failed to download bundle from S3: {e}")


def execute_bundle_from_s3(
    bucket: S3Bucket,
    key: S3Key,
    aws_credentials_block_name: AwsCredentialsBlockName | None = None,
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
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        aws_session_token: AWS session token
        region_name: AWS region name
        env: Additional environment variables for execution

    Returns:
        Dictionary containing execution details

    Example:
        ```yaml
        pull:
            - prefect_aws.deployments.steps.execute_bundle_from_s3:
                requires: prefect-aws
                bucket: my-prefect-bundles
                key: bundles/my-flow-bundle.json
        ```
    """
    # Import functions from the existing bundle utils

    # Download the bundle
    download_result = asyncio.run(
        download_bundle_from_s3(
            bucket=bucket,
            key=key,
            aws_credentials_block_name=aws_credentials_block_name,
        )
    )

    bundle_data = from_json(Path(download_result["local_path"]).read_bytes())

    asyncio.run(Runner().execute_bundle(bundle_data))


if __name__ == "__main__":
    typer.run(execute_bundle_from_s3)
