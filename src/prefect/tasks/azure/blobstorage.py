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
            that stores your Azure credentials; this Secret must be a JSON string
            with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN` (if both are defined then`ACCOUNT_KEY` is used)
        - container (str, optional): the name of the Azure Blob Storage to download from
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
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
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        container: str = None,
    ) -> str:
        """
        Task run method.

        Args:
            - blob_name (str): the name of the blob within this container to retrieve
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
                that stores your Azure credentials; this Secret must be a JSON string
                with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN`
            - container (str, optional): the name of the Blob Storage container to download from

        Returns:
            - str: the contents of this blob_name / container, as a string
        """

        if container is None:
            raise ValueError("A container name must be provided.")

        # get Azure credentials
        azure_credentials = Secret(azure_credentials_secret).get()
        az_account_name = azure_credentials["ACCOUNT_NAME"]
        az_account_key = azure_credentials.get("ACCOUNT_KEY")
        az_sas_token = azure_credentials.get("SAS_TOKEN")

        blob_service = azure.storage.blob.BlockBlobService(
            account_name=az_account_name,
            account_key=az_account_key,
            sas_token=az_sas_token,
        )

        blob_result = blob_service.get_blob_to_text(
            container_name=container, blob_name=blob_name
        )
        content_string = blob_result.content

        return content_string


class BlobStorageUpload(Task):
    """
    Task for uploading string data (e.g., a JSON string) to an Azure Blob Storage container.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be a JSON string
            with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN`
        - container (str, optional): the name of the Azure Blob Storage to upload to
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
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
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        container: str = None,
    ) -> str:
        """
        Task run method.

        Args:
            - data (str): the data payload to upload
            - blob_name (str, optional): the name to upload the data under; if not
                    provided, a random `uuid` will be created
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
                that stores your Azure credentials; this Secret must be a JSON string
                with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN`
            - container (str, optional): the name of the Blob Storage container to upload to

        Returns:
            - str: the name of the blob the data payload was uploaded to
        """

        if container is None:
            raise ValueError("A container name must be provided.")

        ## get Azure credentials
        azure_credentials = Secret(azure_credentials_secret).get()
        az_account_name = azure_credentials["ACCOUNT_NAME"]
        az_account_key = azure_credentials.get("ACCOUNT_KEY")
        az_sas_token = azure_credentials.get("SAS_TOKEN")

        blob_service = azure.storage.blob.BlockBlobService(
            account_name=az_account_name,
            account_key=az_account_key,
            sas_token=az_sas_token,
        )

        ## create key if not provided
        if blob_name is None:
            blob_name = str(uuid.uuid4())

        blob_service.create_blob_from_text(
            container_name=container, blob_name=blob_name, text=data
        )

        return blob_name
