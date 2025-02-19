"""
S3 bundle steps for Prefect.
These steps allow uploading and downloading flow/task bundles to and from S3.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic_core import from_json

from prefect._experimental.bundles import execute_bundle_in_subprocess


async def upload_bundle_to_s3(
    local_filepath: str,
    bucket: str,
    key: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    region_name: str | None = None,
) -> dict[str, str]:
    """
    Uploads a bundle file to an S3 bucket.

    Args:
        local_filepath: Local path to the bundle file
        bucket: S3 bucket name
        key: S3 object key (if None, uses the bundle filename)
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        aws_session_token: AWS session token
        region_name: AWS region name

    Returns:
        Dictionary containing the bucket, key, and S3 URL of the uploaded bundle

    Example:
        ```yaml
        build:
            - prefect_aws.deployments.steps.upload_bundle_to_s3:
                requires: prefect-aws
                local_filepath: "{{ create-bundle.stdout }}"
                bucket: my-prefect-bundles
                key: bundles/my-flow-bundle.json
                region_name: us-west-2
        ```
    """
    filepath = Path(local_filepath)
    if not filepath.exists():
        raise ValueError(f"Bundle file not found: {filepath}")

    key = key or filepath.name

    # Set up S3 client with credentials if provided
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        region_name=region_name,
    )
    s3_client = session.client("s3")

    try:
        s3_client.upload_file(str(filepath), bucket, key)
        return {"bucket": bucket, "key": key, "url": f"s3://{bucket}/{key}"}
    except ClientError as e:
        raise RuntimeError(f"Failed to upload bundle to S3: {e}")


async def download_bundle_from_s3(
    bucket: str,
    key: str,
    output_dir: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    region_name: str | None = None,
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
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        region_name=region_name,
    )
    s3_client = session.client("s3")

    # Determine local path
    output_dir = output_dir or tempfile.mkdtemp(prefix="prefect-bundle-")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    local_path = Path(output_dir) / os.path.basename(key)

    try:
        # Download the file
        s3_client.download_file(bucket, key, local_path)
        return {"local_path": local_path}
    except ClientError as e:
        raise RuntimeError(f"Failed to download bundle from S3: {e}")


async def execute_bundle_from_s3(
    bucket: str,
    key: str,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    region_name: str | None = None,
) -> dict[str, Any]:
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
    download_result = await download_bundle_from_s3(
        bucket=bucket,
        key=key,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        region_name=region_name,
    )

    bundle_data = from_json(Path(download_result["local_path"]).read_bytes())
    spwan_process = execute_bundle_in_subprocess(bundle_data)

    spwan_process.join()
    return {
        "execution_success": spwan_process.exitcode == 0,
        "return_code": spwan_process.exitcode,
        "bundle_path": download_result["local_path"],
    }
