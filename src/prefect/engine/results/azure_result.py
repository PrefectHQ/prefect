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
    set your Azure connection string as a Prefect Secret.  Using an environment
    variable is the recommended approach.

    Args:
        - container (str): the name of the container to write to / read from
        - connection_string (str, optional): an Azure connection string for communicating with
            Blob storage. If not provided the value set in the environment as
            `AZURE_STORAGE_CONNECTION_STRING` will be used
        - connection_string_secret (str, optional): the name of a Prefect Secret
            which stores your Azure connection tring
        - **kwargs (Any, optional): any additional `Result` initialization options
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
        super().__init__(**kwargs)

    def initialize_service(self) -> None:
        """
        Initialize a Blob service.
        """
        import azure.storage.blob

        connection_string = self.connection_string
        if not connection_string and self.connection_string_secret:
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

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Writes the result value to a blob storage in Azure.

        Args:
            - value_ (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: a new Result instance with the appropriately formatted location
        """
        new = self.format(**kwargs)
        new.value = value_

        self.logger.debug("Starting to upload result to {}...".format(new.location))

        # prepare data
        binary_data = new.serializer.serialize(new.value)

        # initialize client and upload
        client = self.service.get_blob_client(
            container=self.container, blob=new.location
        )
        client.upload_blob(binary_data)

        self.logger.debug("Finished uploading result to {}.".format(new.location))

        return new

    def read(self, location: str) -> Result:
        """
        Reads a result from an Azure Blob container and returns a corresponding `Result` instance.

        Args:
            - location (str): the Azure blob location to read from

        Returns:
            - Result: the read result
        """
        new = self.copy()
        new.location = location

        try:
            self.logger.debug("Starting to download result from {}...".format(location))

            # initialize client and download
            client = self.service.get_blob_client(
                container=self.container, blob=location
            )
            content_bytes = client.download_blob().content_as_bytes()

            try:
                new.value = new.serializer.deserialize(content_bytes)
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

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - location (str): Location of the result in the specific result target.
                Will check whether the provided location exists
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether or not the target result exists.
        """
        from azure.core.exceptions import ResourceNotFoundError

        # initialize client and download
        client = self.service.get_blob_client(
            container=self.container, blob=location.format(**kwargs)
        )

        # Catch exception because Azure python bindings do not yet have an exists method
        # https://github.com/Azure/azure-sdk-for-python/issues/9507
        try:
            client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
