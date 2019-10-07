import base64
import json
import uuid
from typing import TYPE_CHECKING, Any

import cloudpickle
import pendulum

from prefect.client import Secret
from prefect.engine.result_handlers import ResultHandler

if TYPE_CHECKING:
    import azure.storage.blob


class AzureResultHandler(ResultHandler):
    """
    Result Handler for writing to and reading from an Azure Blob storage.

    Args:
        - container (str): the name of the container to write to / read from
        - azure_credentials_secret (str, optional): the name of the Prefect Secret
            which stores your Azure credentials; this Secret must be a JSON string
            with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN` 
            (if both are defined then`ACCOUNT_KEY` is used)

    Note that for this result handler to work properly, your Azure Credentials must
    be made available in the `"AZ_CREDENTIALS"` Prefect Secret.
    """

    def __init__(
        self, container: str = None, azure_credentials_secret: str = "AZ_CREDENTIALS"
    ) -> None:
        self.container = container
        self.azure_credentials_secret = azure_credentials_secret
        super().__init__()

    def initialize_service(self) -> None:
        """
        Initialize a Blob service.
        """
        import azure.storage.blob

        azure_credentials = Secret(self.azure_credentials_secret).get()
        if isinstance(azure_credentials, str):
            azure_credentials = json.loads(azure_credentials)

        az_account_name = azure_credentials["ACCOUNT_NAME"]
        az_account_key = azure_credentials.get("ACCOUNT_KEY")
        az_sas_token = azure_credentials.get("SAS_TOKEN")

        blob_service = azure.storage.blob.BlockBlobService(
            account_name=az_account_name,
            account_key=az_account_key,
            sas_token=az_sas_token,
        )
        self.service = blob_service

    @property
    def service(self) -> "azure.storage.blob.BlockBlobService":
        if not hasattr(self, "_service"):
            self.initialize_service()
        return self._service

    @service.setter
    def service(self, val: Any) -> None:
        self._service = val

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        if "_service" in state:
            del state["_service"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def write(self, result: Any) -> str:
        """
        Given a result, writes the result to a location in Azure Blob storage
        and returns the resulting URI.

        Args:
            - result (Any): the written result

        Returns:
            - str: the Blob URI
        """
        date = pendulum.now("utc").format("Y/M/D")
        uri = "{date}/{uuid}.prefect_result".format(date=date, uuid=uuid.uuid4())
        self.logger.debug("Starting to upload result to {}...".format(uri))

        ## prepare data
        binary_data = base64.b64encode(cloudpickle.dumps(result)).decode()

        ## upload
        self.service.create_blob_from_text(
            container_name=self.container, blob_name=uri, text=binary_data
        )

        self.logger.debug("Finished uploading result to {}.".format(uri))

        return uri

    def read(self, uri: str) -> Any:
        """
        Given a uri, reads a result from Azure Blob storage, reads it and returns it

        Args:
            - uri (str): the Azure Blob URI

        Returns:
            - Any: the read result
        """
        try:
            self.logger.debug("Starting to download result from {}...".format(uri))
            blob_result = self.service.get_blob_to_text(
                container_name=self.container, blob_name=uri
            )
            content_string = blob_result.content
            try:
                return_val = cloudpickle.loads(base64.b64decode(content_string))
            except EOFError:
                return_val = None
            self.logger.debug("Finished downloading result from {}.".format(uri))
        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from result handler: {}".format(
                    repr(exc)
                )
            )
            return_val = None
        return return_val
