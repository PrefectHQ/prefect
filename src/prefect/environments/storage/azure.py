import os
from typing import TYPE_CHECKING, Any, Dict, List

import cloudpickle
import pendulum
from slugify import slugify

from prefect.engine.results import AzureResult
from prefect.environments.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Azure(Storage):
    """
    Azure Blob storage class.  This class represents the Storage interface for Flows stored as
    bytes in an Azure container.

    This storage class optionally takes a `blob_name` which will be the name of the Flow object
    when stored in Azure. If this key is not provided the Flow upload name will take the form
    `slugified-flow-name/slugified-current-timestamp`.

    **Note**: Flows registered with this Storage option will automatically be
     labeled with `azure-flow-storage`.

    Args:
        - container (str): the name of the Azure Blob Container to store the Flow
        - connection_string (str, optional): an Azure connection string for communicating with
            Blob storage. If not provided the value set in the environment as
            `AZURE_STORAGE_CONNECTION_STRING` will be used
        - blob_name (str, optional): a unique key to use for uploading this Flow to Azure. This
            is only useful when storing a single Flow using this storage object.
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `False`
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        container: str,
        connection_string: str = None,
        blob_name: str = None,
        stored_as_script: bool = False,
        **kwargs: Any
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]

        self.connection_string = connection_string or os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )

        self.container = container
        self.blob_name = blob_name

        result = AzureResult(
            connection_string=self.connection_string, container=container
        )
        super().__init__(result=result, stored_as_script=stored_as_script, **kwargs)

    @property
    def default_labels(self) -> List[str]:
        return ["azure-flow-storage"]

    def get_flow(self, flow_location: str = None) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).

        Args:
            - flow_location (str, optional): the location of a flow within this Storage; in this case,
                a file path where a Flow has been serialized to. Will use `blob_name` if not provided.

        Returns:
            - Flow: the requested flow

        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        if flow_location:
            if flow_location not in self.flows.values():
                raise ValueError("Flow is not contained in this Storage")
        elif self.blob_name:
            flow_location = self.blob_name
        else:
            raise ValueError("No flow location provided")

        client = self._azure_block_blob_service.get_blob_client(
            container=self.container, blob=flow_location
        )

        self.logger.info("Downloading {} from {}".format(flow_location, self.container))

        content = client.download_blob().content_as_bytes()

        if self.stored_as_script:
            return extract_flow_from_file(file_contents=content)  # type: ignore

        return cloudpickle.loads(content)

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for storing a new flow as bytes in an Azure Blob container.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the key of the newly added Flow in the container

        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """

        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )

        # create key for Flow that uniquely identifies Flow object in Azure
        blob_name = self.blob_name or "{}/{}".format(
            slugify(flow.name), slugify(pendulum.now("utc").isoformat())
        )

        self.flows[flow.name] = blob_name
        self._flows[flow.name] = flow
        return blob_name

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    def build(self) -> "Storage":
        """
        Build the Azure storage object by uploading Flows to an Azure Blob container.
        This will upload all of the flows found in `storage.flows`.

        Returns:
            - Storage: an Azure object that contains information about how and where
                each flow is stored
        """
        self.run_basic_healthchecks()

        if self.stored_as_script:
            if not self.blob_name:
                raise ValueError(
                    "A `blob_name` must be provided to show where flow `.py` file is stored in Azure."
                )
            return self

        for flow_name, flow in self._flows.items():
            data = cloudpickle.dumps(flow)

            client = self._azure_block_blob_service.get_blob_client(
                container=self.container, blob=self.flows[flow_name]
            )

            self.logger.info(
                "Uploading {} to {}".format(self.flows[flow_name], self.container)
            )

            client.upload_blob(data)

        return self

    @property
    def _azure_block_blob_service(self):  # type: ignore
        import azure.storage.blob

        return azure.storage.blob.BlobServiceClient.from_connection_string(
            conn_str=self.connection_string
        )
