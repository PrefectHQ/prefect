"""
Prefect deployment steps for code storage in and retrieval from Google Cloud Storage.
"""
from pathlib import Path, PurePosixPath
from typing import Dict, Optional

import google.auth
from google.cloud.storage import Client as StorageClient
from google.oauth2.service_account import Credentials
from typing_extensions import TypedDict

from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect.utilities.filesystem import filter_files, relative_path_to_current_platform


class PushToGcsOutput(TypedDict):
    """
    The output of the `push_to_gcs` step.
    """

    bucket: str
    folder: str


@deprecated_callable(start_date="Jun 2023", help="Use `PushToGcsOutput` instead.")
class PushProjectToGcsOutput(PushToGcsOutput):
    """Deprecated. Use `PushToGcsOutput` instead."""


class PullFromGcsOutput(TypedDict):
    """
    The output of the `pull_from_gcs` step.
    """

    bucket: str
    folder: str
    directory: str


@deprecated_callable(start_date="Jun 2023", help="Use `PullFromGcsOutput` instead.")
class PullProjectFromGcsOutput(PullFromGcsOutput):
    """Deprecated. Use `PullFromGcsOutput` instead."""


def push_to_gcs(
    bucket: str,
    folder: str,
    project: Optional[str] = None,
    credentials: Optional[Dict] = None,
    ignore_file=".prefectignore",
) -> PushToGcsOutput:
    """
    Pushes the contents of the current working directory to a GCS bucket,
    excluding files and folders specified in the ignore_file.

    Args:
        bucket: The name of the GCS bucket where files will be uploaded.
        folder: The folder in the GCS bucket where files will be uploaded.
        project: The GCP project the bucket belongs to. If not provided, the project
            will be inferred from the credentials or the local environment.
        credentials: A dictionary containing the service account information and project
            used for authentication. If not provided, the application default
            credentials will be used.
        ignore_file: The name of the file containing ignore patterns.

    Returns:
        A dictionary containing the bucket and folder where files were uploaded.

    Examples:
        Push to a GCS bucket:
        ```yaml
        build:
            - prefect_gcp.deployments.steps.push_to_gcs:
                requires: prefect-gcp
                bucket: my-bucket
                folder: my-project
        ```

        Push  to a GCS bucket using credentials stored in a block:
        ```yaml
        build:
            - prefect_gcp.deployments.steps.push_to_gcs:
                requires: prefect-gcp
                bucket: my-bucket
                folder: my-folder
                credentials: "{{ prefect.blocks.gcp-credentials.dev-credentials }}"
        ```

        Push to a GCS bucket using credentials stored in a service account
        file:
        ```yaml
        build:
            - prefect_gcp.deployments.steps.push_to_gcs:
                requires: prefect-gcp
                bucket: my-bucket
                folder: my-folder
                credentials:
                    project: my-project
                    service_account_file: /path/to/service_account.json
        ```

    """
    project = credentials.get("project") if credentials else None

    gcp_creds = None
    if credentials is not None:
        if credentials.get("service_account_info") is not None:
            gcp_creds = Credentials.from_service_account_info(
                credentials.get("service_account_info"),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        elif credentials.get("service_account_file") is not None:
            gcp_creds = Credentials.from_service_account_file(
                credentials.get("service_account_file"),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

    gcp_creds = gcp_creds or google.auth.default()[0]

    storage_client = StorageClient(credentials=gcp_creds, project=project)
    bucket_resource = storage_client.bucket(bucket)

    local_path = Path.cwd()

    included_files = None
    if ignore_file and Path(ignore_file).exists():
        with open(ignore_file, "r") as f:
            ignore_patterns = f.readlines()
        included_files = filter_files(str(local_path), ignore_patterns)

    for local_file_path in local_path.expanduser().rglob("*"):
        relative_local_file_path = local_file_path.relative_to(local_path)
        if (
            included_files is not None
            and str(relative_local_file_path) not in included_files
        ):
            continue
        elif not local_file_path.is_dir():
            remote_file_path = (folder / relative_local_file_path).as_posix()

            blob_resource = bucket_resource.blob(remote_file_path)
            blob_resource.upload_from_filename(local_file_path)

    return {
        "bucket": bucket,
        "folder": folder,
    }


@deprecated_callable(start_date="Jun 2023", help="Use `push_to_gcs` instead.")
def push_project_to_gcs(*args, **kwargs) -> PushToGcsOutput:
    """
    Deprecated. Use `push_to_gcs` instead.
    """
    return push_to_gcs(*args, **kwargs)


def pull_from_gcs(
    bucket: str,
    folder: str,
    project: Optional[str] = None,
    credentials: Optional[Dict] = None,
) -> PullProjectFromGcsOutput:
    """
    Pulls the contents of a project from an GCS bucket to the current working directory.

    Args:
        bucket: The name of the GCS bucket where files are stored.
        folder: The folder in the GCS bucket where files are stored.
        project: The GCP project the bucket belongs to. If not provided, the project will be
            inferred from the credentials or the local environment.
        credentials: A dictionary containing the service account information and project
            used for authentication. If not provided, the application default
            credentials will be used.

    Returns:
        A dictionary containing the bucket, folder, and local directory where files were downloaded.

    Examples:
        Pull from GCS using the default environment credentials:
        ```yaml
        build:
            - prefect_gcp.deployments.steps.pull_from_gcs:
                requires: prefect-gcp
                bucket: my-bucket
                folder: my-folder
        ```

        Pull from GCS using credentials stored in a block:
        ```yaml
        build:
            - prefect_gcp.deployments.steps.pull_from_gcs:
                requires: prefect-gcp
                bucket: my-bucket
                folder: my-folder
                credentials: "{{ prefect.blocks.gcp-credentials.dev-credentials }}"
        ```

        Pull from to an GCS bucket using credentials stored in a service account file:
        ```yaml
        build:
            - prefect_gcp.deployments.steps.pull_from_gcs:
                requires: prefect-gcp
                bucket: my-bucket
                folder: my-folder
                credentials:
                    project: my-project
                    service_account_file: /path/to/service_account.json
        ```

    """  # noqa
    local_path = Path.cwd()
    project = credentials.get("project") if credentials else None

    gcp_creds = None
    if credentials is not None:
        if credentials.get("service_account_info") is not None:
            gcp_creds = Credentials.from_service_account_info(
                credentials.get("service_account_info"),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        elif credentials.get("service_account_file") is not None:
            gcp_creds = Credentials.from_service_account_file(
                credentials.get("service_account_file"),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

    gcp_creds = gcp_creds or google.auth.default()[0]

    storage_client = StorageClient(credentials=gcp_creds, project=project)

    blobs = storage_client.list_blobs(bucket, prefix=folder)

    for blob in blobs:
        if blob.name.endswith("/"):
            # object is a folder and will be created if it contains any objects
            continue
        local_blob_download_path = PurePosixPath(
            local_path
            / relative_path_to_current_platform(blob.name).relative_to(folder)
        )
        Path.mkdir(Path(local_blob_download_path.parent), parents=True, exist_ok=True)

        blob.download_to_filename(local_blob_download_path)

    return {
        "bucket": bucket,
        "folder": folder,
        "directory": str(local_path),
    }


@deprecated_callable(start_date="Jun 2023", help="Use `pull_from_gcs` instead.")
def pull_project_from_gcs(*args, **kwargs) -> PullProjectFromGcsOutput:
    """
    Deprecated. Use `pull_from_gcs` instead.
    """
    return pull_from_gcs(*args, **kwargs)
