from typing import TYPE_CHECKING, Any, Dict, List

import cloudpickle
import pendulum
from slugify import slugify

from prefect.engine.results import GCSResult
from prefect.environments.storage import Storage
from prefect.utilities.exceptions import StorageError

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class GCS(Storage):
    """
    GoogleCloudStorage storage class.  This class represents the Storage interface for Flows stored as
    bytes in an GCS bucket.  To authenticate with Google Cloud, you need to ensure that your Prefect
    Agent has the proper credentials available (see https://cloud.google.com/docs/authentication/production
    for all the authentication options).

    This storage class optionally takes a `key` which will be the name of the Flow object
    when stored in GCS. If this key is not provided the Flow upload name will take the form
    `slugified-flow-name/slugified-current-timestamp`.

    **Note**: Flows registered with this Storage option will automatically be
     labeled with `gcs-flow-storage`.

    Args:
        - bucket (str, optional): the name of the GCS Bucket to store the Flow
        - key (str, optional): a unique key to use for uploading this Flow to GCS. This
            is only useful when storing a single Flow using this storage object.
        - project (str, optional): the google project where any GCS API requests are billed to;
            if not provided, the project will be inferred from your Google Cloud credentials.
        - secrets (List[str], optional): a list of Prefect Secrets which will be used to populate `prefect.context`
            for each flow run.  Used primarily for providing authentication credentials.
    """

    def __init__(
        self,
        bucket: str,
        key: str = None,
        project: str = None,
        secrets: List[str] = None,
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]

        self.bucket = bucket
        self.key = key
        self.project = project

        result = GCSResult(bucket=bucket)
        super().__init__(result=result, secrets=secrets)

    @property
    def labels(self) -> List[str]:
        return ["gcs-flow-storage"]

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

        bucket = self._gcs_client.get_bucket(self.bucket)

        self.logger.info("Downloading {} from {}".format(flow_location, self.bucket))

        blob = bucket.get_blob(flow_location)
        if not blob:
            raise StorageError(
                "Flow not found in bucket: flow={} bucket={}".format(
                    flow_location, self.bucket
                )
            )
        content = blob.download_as_string()
        return cloudpickle.loads(content)

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
        key = self.key or "{}/{}".format(
            slugify(flow.name), slugify(pendulum.now("utc").isoformat())
        )

        self.flows[flow.name] = key
        self._flows[flow.name] = flow
        return key

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
        self.run_basic_healthchecks()

        for flow_name, flow in self._flows.items():
            content = cloudpickle.dumps(flow)

            bucket = self._gcs_client.get_bucket(self.bucket)

            blob = bucket.blob(blob_name=self.flows[flow_name])

            self.logger.info(
                "Uploading {} to {}".format(self.flows[flow_name], self.bucket)
            )

            blob.upload_from_string(content)

        return self

    @property
    def _gcs_client(self):  # type: ignore
        from prefect.utilities.gcp import get_storage_client

        client = get_storage_client(project=self.project)
        return client
