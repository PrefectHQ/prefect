import io
from typing import TYPE_CHECKING, Any, Dict, List

import cloudpickle
import pendulum
from slugify import slugify

import prefect
from prefect.environments.storage import Storage
from prefect.utilities.exceptions import StorageError

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Azure(Storage):
    """
    GoogleCloudStorage storage class.  This class represents the Storage interface for Flows stored as
    bytes in an GCS bucket.

    This storage class optionally takes a `key` which will be the name of the Flow object
    when stored in GCS. If this key is not provided the Flow upload name will take the form
    `slugified-flow-name/slugified-current-timestamp`.

    **Note**: Flows registered with this Storage option will automatically be
     labeled with `gcs-flow-storage`.

    Args:
        - bucket (str, optional): the name of the GCS Bucket to store the Flow
        - key (str, optional): a unique key to use for uploading this Flow to GCS. This
            is only useful when storing a single Flow using this storage object.
        - project (str, optional): the google project where any GCS API requests are billed to
    """

    def __init__(
        self,
        container: str,
        # account_name: str = None,
        # account_key: str = None,
        # sas_token: str = None,
        connection_string: str = None,
        blob_name: str = None,
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "prefect.core.flow.Flow"]

        self.connection_string = connection_string
        # self.account_name = account_name
        # self.account_key = account_key
        # self.sas_token = sas_token

        self.container = container
        self.blob_name = blob_name

        super().__init__()

    @property
    def labels(self) -> List[str]:
        return ["azure-flow-storage"]

    def get_flow(self, flow_location: str) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).

        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a file path where a Flow has been serialized to

        Returns:
            - Flow: the requested flow

        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        if not flow_location in self.flows.values():
            raise ValueError("Flow is not contained in this Storage")

        client = self._azure_block_blob_service.get_blob_client(
            container=self.container, blob=flow_location
        )

        self.logger.info("Downloading {} from {}".format(flow_location, self.container))

        content = client.download_blob()
        return cloudpickle.loads(content.content_as_bytes())

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for storing a new flow as bytes in a GCS bucket.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the key of the newly added flow in the GCS bucket

        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """

        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )

        # create key for Flow that uniquely identifies Flow object in GCS
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
        Build the GCS storage object by uploading Flows to an GCS bucket. This will upload
        all of the flows found in `storage.flows`.

        Returns:
            - Storage: an GCS object that contains information about how and where
                each flow is stored
        """
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
