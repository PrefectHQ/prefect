from typing import TYPE_CHECKING, Any

import pendulum
from slugify import slugify

import prefect
from prefect.engine.results import GCSResult
from prefect.storage import Storage
from prefect.exceptions import FlowStorageError
from prefect.utilities.storage import (
    extract_flow_from_file,
    flow_from_bytes_pickle,
    flow_to_bytes_pickle,
)

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class GCS(Storage):
    """
    GoogleCloudStorage storage class.  This class represents the Storage interface for Flows
    stored as bytes in an GCS bucket.  To authenticate with Google Cloud, you need to ensure
    that your Prefect Agent has the proper credentials available (see
    https://cloud.google.com/docs/authentication/production for all the authentication
    options).

    This storage class optionally takes a `key` which will be the name of the Flow object
    when stored in GCS. If this key is not provided the Flow upload name will take the form
    `slugified-flow-name/slugified-current-timestamp`.

    Args:
        - bucket (str, optional): the name of the GCS Bucket to store the Flow
        - key (str, optional): a unique key to use for uploading this Flow to GCS. This
            is only useful when storing a single Flow using this storage object.
        - project (str, optional): the google project where any GCS API requests are billed to;
            if not provided, the project will be inferred from your Google Cloud credentials.
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `False`
        - local_script_path (str, optional): the path to a local script to upload when `stored_as_script`
            is set to `True`. If not set then the value of `local_script_path` from `prefect.context` is
            used. If neither are set then script will not be uploaded and users should manually place the
            script file in the desired `key` location in a GCS bucket.
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        bucket: str,
        key: str = None,
        project: str = None,
        stored_as_script: bool = False,
        local_script_path: str = None,
        **kwargs: Any
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.project = project
        self.local_script_path = local_script_path or prefect.context.get(
            "local_script_path", None
        )

        result = GCSResult(bucket=bucket)
        super().__init__(result=result, stored_as_script=stored_as_script, **kwargs)

    def get_flow(self, flow_name: str) -> "Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """
        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        flow_location = self.flows[flow_name]

        bucket = self._gcs_client.get_bucket(self.bucket)

        self.logger.info("Downloading {} from {}".format(flow_location, self.bucket))

        blob = bucket.get_blob(flow_location)
        if not blob:
            raise FlowStorageError(
                "Flow not found in bucket: flow={} bucket={}".format(
                    flow_location, self.bucket
                )
            )
        # Support GCS < 1.31
        content = (
            blob.download_as_bytes()
            if hasattr(blob, "download_as_bytes")
            else blob.download_as_string()
        )

        if self.stored_as_script:
            return extract_flow_from_file(file_contents=content, flow_name=flow_name)

        return flow_from_bytes_pickle(content)

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

    def build(self) -> "Storage":
        """
        Build the GCS storage object by uploading Flows to an GCS bucket. This will upload
        all of the flows found in `storage.flows`.

        Returns:
            - Storage: an GCS object that contains information about how and where
                each flow is stored
        """
        self.run_basic_healthchecks()

        if self.stored_as_script:
            if self.local_script_path:
                for flow_name, flow in self._flows.items():
                    self.logger.info(
                        "Uploading script {} to {} in {}".format(
                            self.local_script_path, self.flows[flow.name], self.bucket
                        )
                    )

                    bucket = self._gcs_client.get_bucket(self.bucket)
                    blob = bucket.blob(blob_name=self.flows[flow_name])
                    with open(self.local_script_path) as file_obj:
                        blob.upload_from_file(file_obj)
            else:
                if not self.key:
                    raise ValueError(
                        "A `key` must be provided to show where flow `.py` file is stored in GCS or "
                        "provide a `local_script_path` pointing to a local script that contains the "
                        "flow."
                    )
            return self

        for flow_name, flow in self._flows.items():
            content = flow_to_bytes_pickle(flow)

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
