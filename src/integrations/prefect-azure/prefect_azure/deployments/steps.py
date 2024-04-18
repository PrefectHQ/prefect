"""
Prefect deployment steps for code storage and retrieval in Azure Blob Storage.

These steps can be used in a `prefect.yaml` file to define the default 
push and pull steps for a group of deployments, or they can be used to 
define the push and pull steps for a specific deployment.

!!! example
    Sample `prefect.yaml` file that is configured to push and pull to and 
    from an Azure Blob Storage container:

    ```yaml
    prefect_version: ...
    name: ...

    push:
        - prefect_azure.deployments.steps.push_to_azure_blob_storage:
            requires: prefect-azure[blob_storage]
            container: my-container
            folder: my-folder
            credentials: "{{ prefect.blocks.azure-blob-storage-credentials.dev-credentials }}"

    pull:
        - prefect_azure.deployments.steps.pull_from_azure_blob_storage:
            requires: prefect-azure[blob_storage]
            container: "{{ container }}"
            folder: "{{ folder }}"
            credentials: "{{ prefect.blocks.azure-blob-storage-credentials.dev-credentials }}"
    ```

!!! note
    Azure Storage account needs to have Hierarchical Namespace disabled.

For more information about using deployment steps, check out out the Prefect [docs](https://docs.prefect.io/latest/concepts/projects/#the-prefect-yaml-file).
"""  # noqa
from pathlib import Path, PurePosixPath
from typing import Dict, Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient

from prefect.utilities.filesystem import filter_files, relative_path_to_current_platform


def push_to_azure_blob_storage(
    container: str,
    folder: str,
    credentials: Dict[str, str],
    ignore_file: Optional[str] = ".prefectignore",
):
    """
    Pushes to an Azure Blob Storage container.

    Args:
        container: The name of the container to push files to
        folder: The folder within the container to push to
        credentials: A dictionary of credentials with keys `connection_string` or
            `account_url` and values of the corresponding connection string or
            account url. If both are provided, `connection_string` will be used.
        ignore_file: The path to a file containing patterns of files to ignore when
            pushing to Azure Blob Storage. If not provided, the default `.prefectignore`
            file will be used.

    Example:
        Push to an Azure Blob Storage container using credentials stored in a
        block:
        ```yaml
        push:
            - prefect_azure.deployments.steps.push_to_azure_blob_storage:
                requires: prefect-azure[blob_storage]
                container: my-container
                folder: my-folder
                credentials: "{{ prefect.blocks.azure-blob-storage-credentials.dev-credentials }}"
        ```

        Push to an Azure Blob Storage container using an account URL and
        default credentials:
        ```yaml
        push:
            - prefect_azure.deployments.steps.push_to_azure_blob_storage:
                requires: prefect-azure[blob_storage]
                container: my-container
                folder: my-folder
                credentials:
                    account_url: https://myaccount.blob.core.windows.net/
        ```
    """  # noqa
    local_path = Path.cwd()
    if credentials.get("connection_string") is not None:
        container_client = ContainerClient.from_connection_string(
            credentials["connection_string"], container_name=container
        )
    elif credentials.get("account_url") is not None:
        container_client = ContainerClient(
            account_url=credentials["account_url"],
            container_name=container,
            credential=DefaultAzureCredential(),
        )
    else:
        raise ValueError(
            "Credentials must contain either connection_string or account_url"
        )

    included_files = None
    if ignore_file and Path(ignore_file).exists():
        with open(ignore_file, "r") as f:
            ignore_patterns = f.readlines()

        included_files = filter_files(str(local_path), ignore_patterns)

    with container_client as client:
        for local_file_path in local_path.expanduser().rglob("*"):
            if (
                included_files is not None
                and str(local_file_path.relative_to(local_path)) not in included_files
            ):
                continue
            elif not local_file_path.is_dir():
                remote_file_path = Path(folder) / local_file_path.relative_to(
                    local_path
                )
                with open(local_file_path, "rb") as f:
                    client.upload_blob(str(remote_file_path), f, overwrite=True)

    return {
        "container": container,
        "folder": folder,
    }


def pull_from_azure_blob_storage(
    container: str,
    folder: str,
    credentials: Dict[str, str],
):
    """
    Pulls from an Azure Blob Storage container.

    Args:
        container: The name of the container to pull files from
        folder: The folder within the container to pull from
        credentials: A dictionary of credentials with keys `connection_string` or
            `account_url` and values of the corresponding connection string or
            account url. If both are provided, `connection_string` will be used.

    Note:
        Azure Storage account needs to have Hierarchical Namespace disabled.

    Example:
        Pull from an Azure Blob Storage container using credentials stored in
        a block:
        ```yaml
        pull:
            - prefect_azure.deployments.steps.pull_from_azure_blob_storage:
                requires: prefect-azure[blob_storage]
                container: my-container
                folder: my-folder
                credentials: "{{ prefect.blocks.azure-blob-storage-credentials.dev-credentials }}"
        ```

        Pull from an Azure Blob Storage container using an account URL and
        default credentials:
        ```yaml
        pull:
            - prefect_azure.deployments.steps.pull_from_azure_blob_storage:
                requires: prefect-azure[blob_storage]
                container: my-container
                folder: my-folder
                credentials:
                    account_url: https://myaccount.blob.core.windows.net/
        ```
    """  # noqa
    local_path = Path.cwd()
    if credentials.get("connection_string") is not None:
        container_client = ContainerClient.from_connection_string(
            credentials["connection_string"], container_name=container
        )
    elif credentials.get("account_url") is not None:
        container_client = ContainerClient(
            account_url=credentials["account_url"],
            container_name=container,
            credential=DefaultAzureCredential(),
        )
    else:
        raise ValueError(
            "Credentials must contain either connection_string or account_url"
        )

    with container_client as client:
        for blob in client.list_blobs(name_starts_with=folder):
            target = PurePosixPath(
                local_path
                / relative_path_to_current_platform(blob.name).relative_to(folder)
            )
            Path.mkdir(Path(target.parent), parents=True, exist_ok=True)
            with open(target, "wb") as f:
                client.download_blob(blob).readinto(f)

    return {
        "container": container,
        "folder": folder,
        "directory": local_path,
    }
