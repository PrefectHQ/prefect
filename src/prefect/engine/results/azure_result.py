import json
import os
import uuid
from typing import TYPE_CHECKING, Any

import cloudpickle
import pendulum

from prefect.client import Secret
from prefect.engine.result import Result

if TYPE_CHECKING:
    import azure.storage.blob


class AzureResult(Result):
    """
    Result for writing to and reading from an Azure Blob storage.

    Note that your flow's runtime environment must be able to authenticate with
    Azure; there are currently two supported options: provide a connection string
    either at initialization or at runtime through an environment variable, or
    set your Azure credentials as a Prefect Secret.  Using an environment variable is the recommended
    approach.

    Args:
        - container (str): the name of the container to write to / read from
        - connection_string (str, optional): an Azure connection string for communicating with
            Blob storage. If not provided the value set in the environment as `AZURE_STORAGE_CONNECTION_STRING`
            will be used
        - azure_credentials_secret (str, optional): the name of a Prefect Secret
            which stores your Azure credentials; this Secret must be a JSON payload
            with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN`
            (if both are defined then`ACCOUNT_KEY` is used)
    """

    def __init__(
        self,
        container: str,
        connection_string: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        **kwargs: Any
    ) -> None:
        self.container = container
        self.connection_string = connection_string or os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self.azure_credentials_secret = azure_credentials_secret
        super().__init__(**kwargs)

    def initialize_service(self) -> None:
        """
        Initialize a Blob service.
        """
        import azure.storage.blob

        kwargs = dict()
        if self.azure_credentials_secret:
            azure_credentials = Secret(self.azure_credentials_secret).get()
            if isinstance(azure_credentials, str):
                azure_credentials = json.loads(azure_credentials)

            kwargs["account_name"] = azure_credentials["ACCOUNT_NAME"]
            kwargs["account_key"] = azure_credentials.get("ACCOUNT_KEY")
            kwargs["sas_token"] = azure_credentials.get("SAS_TOKEN")
        else:
            kwargs["connection_string"] = self.connection_string

        blob_service = azure.storage.blob.BlockBlobService(**kwargs)
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

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        Given a value, writes to a location in Azure Blob storage
        and returns the resulting URI.

        Args:
            - result (Any): the written result
            - **kwargs (optional): if provided, will be used to format the filepath template
                to determine the location to write to

        Returns:
            - Result: a new Result instance with the appropriately formatted Blob URI
        """
        new = self.format(**kwargs)
        new.value = value

        self.logger.debug("Starting to upload result to {}...".format(new.filepath))

        ## prepare data
        binary_data = new.serialize_to_bytes(new.value).decode()

        ## upload
        self.service.create_blob_from_text(
            container_name=self.container, blob_name=new.filepath, text=binary_data
        )

        self.logger.debug("Finished uploading result to {}.".format(new.filepath))
        return new

    def read(self, filepath: str) -> Result:
        """
        Given a uri, reads a result from Azure Blob storage, reads it and returns it

        Args:
            - uri (str): the Azure Blob URI

        Returns:
            - Result: the read result
        """
        new = self.copy()
        new.filepath = filepath

        try:
            self.logger.debug("Starting to download result from {}...".format(filepath))
            blob_result = self.service.get_blob_to_text(
                container_name=self.container, blob_name=new.filepath
            )
            content_string = blob_result.content
            try:
                new.value = new.deserialize_from_bytes(content_string)
            except EOFError:
                new.value = None
            self.logger.debug("Finished downloading result from {}.".format(filepath))
        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from result handler: {}".format(
                    repr(exc)
                )
            )
            raise exc
        return new

    def exists(self, filepath: str) -> bool:
        """
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - filepath (str): Location of the result in the specific result target.
                Will check whether the provided filepath exists

        Returns:
            - bool: whether or not the target result exists.
        """
        raise NotImplementedError()
