"""
S3 bundle steps for Prefect.
These steps allow uploading and downloading flow/task bundles to and from S3.
"""

from __future__ import annotations

from pathlib import Path

import typer
from botocore.exceptions import ClientError

from prefect_aws.bundles.types import (
    AwsCredentialsBlockName,
    LocalFilepath,
    S3Bucket,
    S3Key,
)
from prefect_aws.credentials import AwsCredentials


def upload_bundle_to_s3(
    local_filepath: LocalFilepath,
    bucket: S3Bucket,
    key: S3Key,
    aws_credentials_block_name: AwsCredentialsBlockName | None = None,
) -> dict[str, str]:
    """
    Uploads a bundle file to an S3 bucket.

    Args:
        local_filepath: Local path to the bundle file
        bucket: S3 bucket name
        key: S3 object key (if None, uses the bundle filename)
        aws_credentials_block_name: Name of the AWS credentials block to use

    Returns:
        Dictionary containing the bucket, key, and S3 URL of the uploaded bundle
    """
    filepath = Path(local_filepath)
    if not filepath.exists():
        raise ValueError(f"Bundle file not found: {filepath}")

    key = key or filepath.name

    # Set up S3 client with credentials if provided
    if aws_credentials_block_name:
        aws_credentials = AwsCredentials.load(aws_credentials_block_name)
    else:
        aws_credentials = AwsCredentials()

    s3 = aws_credentials.get_s3_client()

    try:
        s3.upload_file(str(filepath), bucket, key)
        return {"bucket": bucket, "key": key, "url": f"s3://{bucket}/{key}"}
    except ClientError as e:
        raise RuntimeError(f"Failed to upload bundle to S3: {e}")


if __name__ == "__main__":
    typer.run(upload_bundle_to_s3)
