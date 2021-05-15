import uuid

import azure.storage.blob

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class BlobStorageDownload(Task):
    """
    Task for downloading data from an Blob Storage container and returning it as a string.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be an Azure connection string
        - container (str, optional): the name of the Azure Blob Storage to download from
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        azure_credentials_secret: str = "AZ_CONNECTION_STRING",
        container: str = None,
        **kwargs
    ) -> None:
        self.azure_credentials_secret = azure_credentials_secret
        self.container = container
        super().__init__(**kwargs)

    @defaults_from_attrs("azure_credentials_secret", "container")
    def run(
        self,
        blob_name: str,
        azure_credentials_secret: str = "AZ_CONNECTION_STRING",
        container: str = None,
    ) -> str:
        """
        Task run method.

        Args:
            - blob_name (str): the name of the blob within this container to retrieve
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be an Azure connection string
            - container (str, optional): the name of the Blob Storage container to download from

        Returns:
            - str: the contents of this blob_name / container, as a string
        """

        if container is None:
            raise ValueError("A container name must be provided.")

        # get Azure credentials
        azure_credentials = Secret(azure_credentials_secret).get()

        blob_service = azure.storage.blob.BlobServiceClient.from_connection_string(
            conn_str=azure_credentials
        )

        client = blob_service.get_blob_client(container=container, blob=blob_name)
        content_string = client.download_blob().content_as_text()

        return content_string


class BlobStorageUpload(Task):
    """
    Task for uploading string data (e.g., a JSON string) to an Azure Blob Storage container.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be an Azure connection string
        - container (str, optional): the name of the Azure Blob Storage to upload to
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        azure_credentials_secret: str = "AZ_CONNECTION_STRING",
        container: str = None,
        **kwargs
    ) -> None:
        self.azure_credentials_secret = azure_credentials_secret
        self.container = container
        super().__init__(**kwargs)

    @defaults_from_attrs("azure_credentials_secret", "container")
    def run(
        self,
        data: str,
        blob_name: str = None,
        azure_credentials_secret: str = "AZ_CONNECTION_STRING",
        container: str = None,
    ) -> str:
        """
        Task run method.

        Args:
            - data (str): the data payload to upload
            - blob_name (str, optional): the name to upload the data under; if not
                    provided, a random `uuid` will be created
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be an Azure connection string
            - container (str, optional): the name of the Blob Storage container to upload to

        Returns:
            - str: the name of the blob the data payload was uploaded to
        """

        if container is None:
            raise ValueError("A container name must be provided.")

        # get Azure credentials
        azure_credentials = Secret(azure_credentials_secret).get()

        blob_service = azure.storage.blob.BlobServiceClient.from_connection_string(
            conn_str=azure_credentials
        )

        # create key if not provided
        if blob_name is None:
            blob_name = str(uuid.uuid4())

        client = blob_service.get_blob_client(container=container, blob=blob_name)

        client.upload_blob(data)

        return blob_name
