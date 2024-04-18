"""Tasks for interacting with Azure ML Datastore"""

import os
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Union

from anyio import to_thread
from azureml.core.datastore import Datastore

from prefect import get_run_logger, task

if TYPE_CHECKING:
    from azureml.data.azure_storage_datastore import AzureBlobDatastore
    from azureml.data.data_reference import DataReference

    from prefect_azure.credentials import (
        AzureBlobStorageCredentials,
        AzureMlCredentials,
    )


@task
def ml_list_datastores(ml_credentials: "AzureMlCredentials") -> Dict:
    """
    Lists the Datastores in the Workspace.

    Args:
        ml_credentials: Credentials to use for authentication with Azure.

    Example:
        List Datastore objects
        ```python
        from prefect import flow
        from prefect_azure import AzureMlCredentials
        from prefect_azure.ml_datastore import ml_list_datastores

        @flow
        def example_ml_list_datastores_flow():
            ml_credentials = AzureMlCredentials(
                tenant_id="tenant_id",
                service_principal_id="service_principal_id",
                service_principal_password="service_principal_password",
                subscription_id="subscription_id",
                resource_group="resource_group",
                workspace_name="workspace_name",
            )
            results = ml_list_datastores(ml_credentials)
            return results
        ```
    """
    logger = get_run_logger()
    logger.info("Listing datastores")

    workspace = ml_credentials.get_workspace()
    results = workspace.datastores
    return results


async def _get_datastore(
    ml_credentials: "AzureMlCredentials", datastore_name: str = None
):
    """
    Helper method for get datastore to prevent Task calling another Task.
    """
    workspace = ml_credentials.get_workspace()

    if datastore_name is None:
        partial_get = partial(Datastore.get_default, workspace)
    else:
        partial_get = partial(Datastore.get, workspace, datastore_name=datastore_name)

    result = await to_thread.run_sync(partial_get)
    return result


@task
async def ml_get_datastore(
    ml_credentials: "AzureMlCredentials", datastore_name: str = None
) -> Datastore:
    """
    Gets the Datastore within the Workspace.

    Args:
        ml_credentials: Credentials to use for authentication with Azure.
        datastore_name: The name of the Datastore. If `None`, then the
            default Datastore of the Workspace is returned.

    Example:
        Get Datastore object
        ```python
        from prefect import flow
        from prefect_azure import AzureMlCredentials
        from prefect_azure.ml_datastore import ml_get_datastore

        @flow
        def example_ml_get_datastore_flow():
            ml_credentials = AzureMlCredentials(
                tenant_id="tenant_id",
                service_principal_id="service_principal_id",
                service_principal_password="service_principal_password",
                subscription_id="subscription_id",
                resource_group="resource_group",
                workspace_name="workspace_name",
            )
            results = ml_get_datastore(ml_credentials, datastore_name="datastore_name")
            return results
        ```
    """
    logger = get_run_logger()
    logger.info("Getting datastore %s", datastore_name)

    result = await _get_datastore(ml_credentials, datastore_name)
    return result


@task
async def ml_upload_datastore(
    path: Union[str, Path, List[Union[str, Path]]],
    ml_credentials: "AzureMlCredentials",
    target_path: Union[str, Path] = None,
    relative_root: Union[str, Path] = None,
    datastore_name: str = None,
    overwrite: bool = False,
) -> "DataReference":
    """
    Uploads local files to a Datastore.

    Args:
        path: The path to a single file, single directory,
            or a list of path to files to be uploaded.
        ml_credentials: Credentials to use for authentication with Azure.
        target_path: The location in the blob container to upload to. If
            None, then upload to root.
        relative_root: The root from which is used to determine the path of
            the files in the blob. For example, if we upload /path/to/file.txt,
            and we define base path to be /path, when file.txt is uploaded
            to the blob storage, it will have the path of /to/file.txt.
        datastore_name: The name of the Datastore. If `None`, then the
            default Datastore of the Workspace is returned.
        overwrite: Overwrite existing file(s).

    Example:
        Upload Datastore object
        ```python
        from prefect import flow
        from prefect_azure import AzureMlCredentials
        from prefect_azure.ml_datastore import ml_upload_datastore

        @flow
        def example_ml_upload_datastore_flow():
            ml_credentials = AzureMlCredentials(
                tenant_id="tenant_id",
                service_principal_id="service_principal_id",
                service_principal_password="service_principal_password",
                subscription_id="subscription_id",
                resource_group="resource_group",
                workspace_name="workspace_name",
            )
            result = ml_upload_datastore(
                "path/to/dir/or/file",
                ml_credentials,
                datastore_name="datastore_name"
            )
            return result
        ```
    """
    logger = get_run_logger()
    logger.info("Uploading %s into %s datastore", path, datastore_name)

    datastore = await _get_datastore(ml_credentials, datastore_name)

    if isinstance(path, Path):
        path = str(path)
    elif isinstance(path, list) and isinstance(path[0], Path):
        path = [str(p) for p in path]

    if isinstance(target_path, Path):
        target_path = str(target_path)

    if isinstance(relative_root, Path):
        relative_root = str(relative_root)

    if isinstance(path, str) and os.path.isdir(path):
        partial_upload = partial(
            datastore.upload,
            src_dir=path,
            target_path=target_path,
            overwrite=overwrite,
            show_progress=False,
        )
    else:
        partial_upload = partial(
            datastore.upload_files,
            files=path if isinstance(path, list) else [path],
            relative_root=relative_root,
            target_path=target_path,
            overwrite=overwrite,
            show_progress=False,
        )

    result = await to_thread.run_sync(partial_upload)
    return result


@task
async def ml_register_datastore_blob_container(
    container_name: str,
    ml_credentials: "AzureMlCredentials",
    blob_storage_credentials: "AzureBlobStorageCredentials",
    datastore_name: str = None,
    create_container_if_not_exists: bool = False,
    overwrite: bool = False,
    set_as_default: bool = False,
) -> "AzureBlobDatastore":
    """
    Registers a Azure Blob Storage container as a
    Datastore in a Azure ML service Workspace.

    Args:
        container_name: The name of the container.
        ml_credentials: Credentials to use for authentication with Azure ML.
        blob_storage_credentials: Credentials to use for authentication
            with Azure Blob Storage.
        datastore_name: The name of the datastore. If not defined, the
            container name will be used.
        create_container_if_not_exists: Create a container, if one does not
            exist with the given name.
        overwrite: Overwrite an existing datastore. If
            the datastore does not exist, it will be created.
        set_as_default: Set the created Datastore as the default datastore
            for the Workspace.

    Example:
        Upload Datastore object
        ```python
        from prefect import flow
        from prefect_azure import AzureMlCredentials
        from prefect_azure.ml_datastore import ml_register_datastore_blob_container

        @flow
        def example_ml_register_datastore_blob_container_flow():
            ml_credentials = AzureMlCredentials(
                tenant_id="tenant_id",
                service_principal_id="service_principal_id",
                service_principal_password="service_principal_password",
                subscription_id="subscription_id",
                resource_group="resource_group",
                workspace_name="workspace_name",
            )
            blob_storage_credentials = AzureBlobStorageCredentials("connection_string")
            result = ml_register_datastore_blob_container(
                "container",
                ml_credentials,
                blob_storage_credentials,
                datastore_name="datastore_name"
            )
            return result
        ```
    """
    logger = get_run_logger()

    if datastore_name is None:
        datastore_name = container_name

    logger.info(
        "Registering %s container into %s datastore", container_name, datastore_name
    )

    workspace = ml_credentials.get_workspace()
    async with blob_storage_credentials.get_client() as blob_service_client:
        credential = blob_service_client.credential
        account_name = credential.account_name
        account_key = credential.account_key

    partial_register = partial(
        Datastore.register_azure_blob_container,
        workspace=workspace,
        datastore_name=datastore_name,
        container_name=container_name,
        account_name=account_name,
        account_key=account_key,
        overwrite=overwrite,
        create_if_not_exists=create_container_if_not_exists,
    )
    result = await to_thread.run_sync(partial_register)

    if set_as_default:
        result.set_as_default()

    return result
