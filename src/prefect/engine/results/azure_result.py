import json
import os
from typing import TYPE_CHECKING, Any

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
        - connection_string_secret (str, optional): the name of a Prefect Secret
            which stores your Azure connection tring
    """

    def __init__(
        self,
        container: str,
        connection_string: str = None,
        connection_string_secret: str = None,
        **kwargs: Any
    ) -> None:
        self.container = container
        self.connection_string = connection_string or os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self.connection_string_secret = connection_string_secret
        self._service = None
        super().__init__(**kwargs)

    def initialize_service(self) -> None:
        """
        Initialize a Blob service.
        """
        import azure.storage.blob

        connection_string = self.connection_string
        if not connection_string:
            connection_string = Secret(self.connection_string_secret).get()

        self._service = azure.storage.blob.BlobServiceClient.from_connection_string(
            conn_str=connection_string
        )

    @property
    def service(self) -> "azure.storage.blob.BlobServiceClient":
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
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: a new Result instance with the appropriately formatted Blob URI
        """
        new = self.format(**kwargs)
        new.value = value

        self.logger.debug("Starting to upload result to {}...".format(new.location))

        ## prepare data
        binary_data = new.serialize_to_bytes(new.value).decode()

        ## upload
        self.service.create_blob_from_text(
            container_name=self.container, blob_name=new.location, text=binary_data
        )

        self.logger.debug("Finished uploading result to {}.".format(new.location))
        return new

    def read(self, location: str) -> Result:
        """
        Given a uri, reads a result from Azure Blob storage, reads it and returns it

        Args:
            - uri (str): the Azure Blob URI

        Returns:
            - Result: the read result
        """
        new = self.copy()
        new.location = location

        try:
            self.logger.debug("Starting to download result from {}...".format(location))
            blob_result = self.service.get_blob_to_text(
                container_name=self.container, blob_name=new.location
            )
            content_string = blob_result.content
            try:
                new.value = new.deserialize_from_bytes(content_string)
            except EOFError:
                new.value = None
            self.logger.debug("Finished downloading result from {}.".format(location))
        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from result handler: {}".format(
                    repr(exc)
                )
            )
            raise exc
        return new

    def exists(self, location: str) -> bool:
        """
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - location (str): Location of the result in the specific result target.
                Will check whether the provided location exists

        Returns:
            - bool: whether or not the target result exists.
        """
        raise NotImplementedError()
