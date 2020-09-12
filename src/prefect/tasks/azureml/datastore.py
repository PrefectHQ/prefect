import os
from typing import Dict, List, Union

import azureml.core.datastore
from azureml.core.workspace import Workspace
from azureml.data.azure_storage_datastore import (
    AbstractAzureStorageDatastore,
    AzureBlobDatastore,
)
from azureml.data.data_reference import DataReference

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class DatastoreRegisterBlobContainer(Task):
    """
    Task for registering Azure Blob Storage container as a Datastore in a Azure ML service
    Workspace.

    Args:
        - workspace (azureml.core.workspace.Workspace): The Workspace to which the Datastore is
            to be registered.
        - container_name (str, optional): The name of the container.
        - datastore_name (str, optional): The name of the datastore. If not defined, the
            container name will be used.
        - create_container_if_not_exists (bool, optional): Create a container, if one does not
            exist with the given name.
        - overwrite_existing_datastore (bool, optional): Overwrite an existing datastore. If
            the datastore does not exist, it will be created.
        - azure_credentials_secret (str, optinonal): The name of the Prefect Secret that stores
            your Azure credentials; this Secret must be a JSON string with two keys:
            `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN` (if both are defined
            then`ACCOUNT_KEY` is used).
        - set_as_default (bool optional): Set the created Datastore as the default datastore
            for the Workspace.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        workspace: Workspace,
        container_name: str = None,
        datastore_name: str = None,
        create_container_if_not_exists: bool = False,
        overwrite_existing_datastore: bool = False,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        set_as_default: bool = False,
        **kwargs
    ) -> None:
        self.workspace = workspace
        self.container_name = container_name
        self.datastore_name = datastore_name
        self.create_container_if_not_exists = create_container_if_not_exists
        self.overwrite_existing_datastore = overwrite_existing_datastore
        self.azure_credentials_secret = azure_credentials_secret
        self.set_as_default = set_as_default

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "container_name",
        "datastore_name",
        "create_container_if_not_exists",
        "overwrite_existing_datastore",
        "azure_credentials_secret",
        "set_as_default",
    )
    def run(
        self,
        container_name: str = None,
        datastore_name: str = None,
        create_container_if_not_exists: bool = False,
        overwrite_existing_datastore: bool = False,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        set_as_default: bool = False,
    ) -> AzureBlobDatastore:
        """
        Task run method.

        Args:
            - container_name (str, optional): The name of the container.
            - datastore_name (str, optional): The name of the datastore. If not defined, the
                container name will be used.
            - create_container_if_not_exists (bool, optional): Create a container, if one does
                not exist with the given name.
            - overwrite_existing_datastore (bool, optional): Overwrite an existing datastore.
                If the datastore does not exist, it will be created.
            - azure_credentials_secret (str, optinonal): The name of the Prefect Secret that
                stores your Azure credentials; this Secret must be a JSON string with two keys:
                `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN` (if both are defined
                then`ACCOUNT_KEY` is used)
            - set_as_default (bool optional): Set the created Datastore as the default
                datastore for the Workspace.

        Return:
            - (azureml.data.azure_storage_datastore.AzureBlobDatastore): The registered Datastore.

        """
        if container_name is None:
            raise ValueError("A container name must be provided.")

        if datastore_name is None:
            datastore_name = container_name

        # get Azure credentials
        azure_credentials = Secret(azure_credentials_secret).get()
        az_account_name = azure_credentials["ACCOUNT_NAME"]
        az_account_key = azure_credentials.get("ACCOUNT_KEY")
        az_sas_token = azure_credentials.get("SAS_TOKEN")

        datastore = azureml.core.datastore.Datastore.register_azure_blob_container(
            workspace=self.workspace,
            datastore_name=datastore_name,
            container_name=container_name,
            account_name=az_account_name,
            account_key=az_account_key,
            sas_token=az_sas_token,
            overwrite=overwrite_existing_datastore,
            create_if_not_exists=create_container_if_not_exists,
        )

        if set_as_default:
            datastore.set_as_default()

        return datastore


class DatastoreList(Task):
    """
    Task for listing the Datastores in a Workspace.

    Args:
        - workspace (azureml.core.workspace.Workspace): The Workspace which Datastores are to
            be listed.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor"""

    def __init__(self, workspace: Workspace, **kwargs) -> None:
        self.workspace = workspace

        super().__init__(**kwargs)

    def run(self) -> Dict[str, azureml.core.datastore.Datastore]:
        """
        Task run method.

        Returns:
            -  Dict[str, Datastore]: a dictionary with the datastore names as keys and
                 Datastore objects as items.
        """

        return self.workspace.datastores


class DatastoreGet(Task):
    """
    Task for getting a Datastore registered to a given Workspace.

    Args:
        - workspace (azureml.core.workspace.Workspace): The Workspace which Datastore is retrieved.
        - datastore_name (str, optional): The name of the Datastore. If `None`, then the
            default Datastore of the Workspace is returned.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self, workspace: Workspace, datastore_name: str = None, **kwargs
    ) -> None:
        self.workspace = workspace
        self.datastore_name = datastore_name

        super().__init__(**kwargs)

    @defaults_from_attrs("datastore_name")
    def run(self, datastore_name: str = None) -> azureml.core.datastore.Datastore:
        """
        Task run method.

        Args:
            - datastore_name (str, optional): The name of the Datastore. If `None`, then the
                default Datastore of the Workspace is returned.

        Returns:
            - (azureml.core.datastore.Datastore): The Datastore.

        """
        if datastore_name is None:
            return azureml.core.datastore.Datastore.get_default(self.workspace)
        return azureml.core.datastore.Datastore.get(
            self.workspace, datastore_name=datastore_name
        )


class DatastoreUpload(Task):
    """
    Task for uploading local files to a Datastore.

    Args:
        - datastore (azureml.data.azure_storage_datastore.AbstractAzureStorageDatastore, optional):
            The datastore to upload the files to.
        - relative_root (str, optional): The root from which is used to determine the path of
            the files in the blob. For example, if we upload /path/to/file.txt, and we define
            base path to be /path, when file.txt is uploaded to the blob storage, it will have
            the path of /to/file.txt.
        - path (Union[str, List[str]], optional): The path to a single file, single directory,
            or a list of path to files to eb uploaded.
        - target_path (str, optional): The location in the blob container to upload to. If
            None, then upload to root.
        - overwrite (bool, optional): Overwrite existing file(s).
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor

    """

    def __init__(
        self,
        datastore: AbstractAzureStorageDatastore = None,
        relative_root: str = None,
        path: Union[str, List[str]] = None,
        target_path: str = None,
        overwrite: bool = False,
        **kwargs
    ) -> None:
        self.datastore = datastore
        self.path = path
        self.relative_root = relative_root
        self.target_path = target_path
        self.overwrite = overwrite

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "datastore", "path", "relative_root", "target_path", "overwrite"
    )
    def run(
        self,
        datastore: azureml.core.datastore.Datastore = None,
        path: Union[str, List[str]] = None,
        relative_root: str = None,
        target_path: str = None,
        overwrite: bool = False,
    ) -> DataReference:
        """
        Task run method.

        Args:
            - datastore (azureml.data.azure_storage_datastore.AbstractAzureStorageDatastore, optional):
                The datastore to upload the files to.
            - relative_root (str, optional): The root from which is used to determine the path
                of the files in the blob. For example, if we upload `/path/to/file.txt`, and we
                define base path to be `/path`, when `file.txt` is uploaded to the blob
                storage, it will have the path of `/to/file.txt`.
            - path (Union[str, List[str]], optional): The path to a single file, single
                directory, or a list of path to files to eb uploaded.
            - target_path (str, optional): The location in the blob container to upload to. If
                None, then upload to root.
            - overwrite (bool, optional): Overwrite existing file(s).

        Returns:
            - (azureml.data.data_reference.DataReference): The DataReference instance for the
              target path uploaded
        """

        if datastore is None:
            raise ValueError("A datastore must be provided.")

        if path is None:
            raise ValueError("A path must be provided.")

        if isinstance(path, str) and os.path.isdir(path):
            data_reference = datastore.upload(
                src_dir=path,
                target_path=target_path,
                overwrite=overwrite,
                show_progress=False,
            )
            return data_reference

        if isinstance(path, str):
            path = [path]

        data_reference = datastore.upload_files(
            files=path,
            relative_root=relative_root,
            target_path=target_path,
            overwrite=overwrite,
            show_progress=False,
        )

        return data_reference
