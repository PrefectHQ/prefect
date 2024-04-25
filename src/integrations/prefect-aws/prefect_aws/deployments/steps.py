"""
Prefect deployment steps for code storage and retrieval in S3 and S3
compatible services.
"""
from pathlib import Path, PurePosixPath
from typing import Dict, Optional

import boto3
from botocore.client import Config
from typing_extensions import TypedDict

from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect.utilities.filesystem import filter_files, relative_path_to_current_platform


class PushToS3Output(TypedDict):
    """
    The output of the `push_to_s3` step.
    """

    bucket: str
    folder: str


@deprecated_callable(start_date="Jun 2023", help="Use `PushToS3Output` instead.")
class PushProjectToS3Output(PushToS3Output):
    """Deprecated. Use `PushToS3Output` instead."""


class PullFromS3Output(TypedDict):
    """
    The output of the `pull_from_s3` step.
    """

    bucket: str
    folder: str
    directory: str


@deprecated_callable(start_date="Jun 2023", help="Use `PullFromS3Output` instead.")
class PullProjectFromS3Output(PullFromS3Output):
    """Deprecated. Use `PullFromS3Output` instead.."""


@deprecated_callable(start_date="Jun 2023", help="Use `push_to_s3` instead.")
def push_project_to_s3(*args, **kwargs):
    """Deprecated. Use `push_to_s3` instead."""
    push_to_s3(*args, **kwargs)


def push_to_s3(
    bucket: str,
    folder: str,
    credentials: Optional[Dict] = None,
    client_parameters: Optional[Dict] = None,
    ignore_file: Optional[str] = ".prefectignore",
) -> PushToS3Output:
    """
    Pushes the contents of the current working directory to an S3 bucket,
    excluding files and folders specified in the ignore_file.

    Args:
        bucket: The name of the S3 bucket where files will be uploaded.
        folder: The folder in the S3 bucket where files will be uploaded.
        credentials: A dictionary of AWS credentials (aws_access_key_id,
            aws_secret_access_key, aws_session_token) or MinIO credentials
            (minio_root_user, minio_root_password).
        client_parameters: A dictionary of additional parameters to pass to the boto3
            client.
        ignore_file: The name of the file containing ignore patterns.

    Returns:
        A dictionary containing the bucket and folder where files were uploaded.

    Examples:
        Push files to an S3 bucket:
        ```yaml
        push:
            - prefect_aws.deployments.steps.push_to_s3:
                requires: prefect-aws
                bucket: my-bucket
                folder: my-project
        ```

        Push files to an S3 bucket using credentials stored in a block:
        ```yaml
        push:
            - prefect_aws.deployments.steps.push_to_s3:
                requires: prefect-aws
                bucket: my-bucket
                folder: my-project
                credentials: "{{ prefect.blocks.aws-credentials.dev-credentials }}"
        ```

    """
    s3 = get_s3_client(credentials=credentials, client_parameters=client_parameters)

    local_path = Path.cwd()

    included_files = None
    if ignore_file and Path(ignore_file).exists():
        with open(ignore_file, "r") as f:
            ignore_patterns = f.readlines()

        included_files = filter_files(str(local_path), ignore_patterns)

    for local_file_path in local_path.expanduser().rglob("*"):
        if (
            included_files is not None
            and str(local_file_path.relative_to(local_path)) not in included_files
        ):
            continue
        elif not local_file_path.is_dir():
            remote_file_path = Path(folder) / local_file_path.relative_to(local_path)
            s3.upload_file(
                str(local_file_path), bucket, str(remote_file_path.as_posix())
            )

    return {
        "bucket": bucket,
        "folder": folder,
    }


@deprecated_callable(start_date="Jun 2023", help="Use `pull_from_s3` instead.")
def pull_project_from_s3(*args, **kwargs):
    """Deprecated. Use `pull_from_s3` instead."""
    pull_from_s3(*args, **kwargs)


def pull_from_s3(
    bucket: str,
    folder: str,
    credentials: Optional[Dict] = None,
    client_parameters: Optional[Dict] = None,
) -> PullFromS3Output:
    """
    Pulls the contents of an S3 bucket folder to the current working directory.

    Args:
        bucket: The name of the S3 bucket where files are stored.
        folder: The folder in the S3 bucket where files are stored.
        credentials: A dictionary of AWS credentials (aws_access_key_id,
            aws_secret_access_key, aws_session_token) or MinIO credentials
            (minio_root_user, minio_root_password).
        client_parameters: A dictionary of additional parameters to pass to the
            boto3 client.

    Returns:
        A dictionary containing the bucket, folder, and local directory where
            files were downloaded.

    Examples:
        Pull files from S3 using the default credentials and client parameters:
        ```yaml
        pull:
            - prefect_aws.deployments.steps.pull_from_s3:
                requires: prefect-aws
                bucket: my-bucket
                folder: my-project
        ```

        Pull files from S3 using credentials stored in a block:
        ```yaml
        pull:
            - prefect_aws.deployments.steps.pull_from_s3:
                requires: prefect-aws
                bucket: my-bucket
                folder: my-project
                credentials: "{{ prefect.blocks.aws-credentials.dev-credentials }}"
        ```
    """
    s3 = get_s3_client(credentials=credentials, client_parameters=client_parameters)

    local_path = Path.cwd()

    paginator = s3.get_paginator("list_objects_v2")
    for result in paginator.paginate(Bucket=bucket, Prefix=folder):
        for obj in result.get("Contents", []):
            remote_key = obj["Key"]

            if remote_key[-1] == "/":
                # object is a folder and will be created if it contains any objects
                continue

            target = PurePosixPath(
                local_path
                / relative_path_to_current_platform(remote_key).relative_to(folder)
            )
            Path.mkdir(Path(target.parent), parents=True, exist_ok=True)
            s3.download_file(bucket, remote_key, str(target))

    return {
        "bucket": bucket,
        "folder": folder,
        "directory": str(local_path),
    }


def get_s3_client(
    credentials: Optional[Dict] = None,
    client_parameters: Optional[Dict] = None,
) -> dict:
    if credentials is None:
        credentials = {}
    if client_parameters is None:
        client_parameters = {}

    # Get credentials from credentials (regardless if block or not)
    aws_access_key_id = credentials.get(
        "aws_access_key_id", credentials.get("minio_root_user", None)
    )
    aws_secret_access_key = credentials.get(
        "aws_secret_access_key", credentials.get("minio_root_password", None)
    )
    aws_session_token = credentials.get("aws_session_token", None)

    # Get remaining session info from credentials, or client_parameters
    profile_name = credentials.get(
        "profile_name", client_parameters.get("profile_name", None)
    )
    region_name = credentials.get(
        "region_name", client_parameters.get("region_name", None)
    )

    # Get additional info from client_parameters, otherwise credentials input (if block)
    aws_client_parameters = credentials.get("aws_client_parameters", client_parameters)
    api_version = aws_client_parameters.get("api_version", None)
    endpoint_url = aws_client_parameters.get("endpoint_url", None)
    use_ssl = aws_client_parameters.get("use_ssl", True)
    verify = aws_client_parameters.get("verify", None)
    config_params = aws_client_parameters.get("config", {})
    config = Config(**config_params)

    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        profile_name=profile_name,
        region_name=region_name,
    )
    return session.client(
        "s3",
        api_version=api_version,
        endpoint_url=endpoint_url,
        use_ssl=use_ssl,
        verify=verify,
        config=config,
    )
