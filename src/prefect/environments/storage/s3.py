import io
from typing import TYPE_CHECKING, Any, Dict, List

import cloudpickle
import pendulum
from slugify import slugify

from prefect.engine.results import S3Result
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class S3(Storage):
    """
    S3 storage class.  This class represents the Storage interface for Flows stored as
    bytes in an S3 bucket.

    This storage class optionally takes a `key` which will be the name of the Flow object
    when stored in S3. If this key is not provided the Flow upload name will take the form
    `slugified-flow-name/slugified-current-timestamp`.

     **Note**: Flows registered with this Storage option will automatically be
     labeled with `s3-flow-storage`.

    Args:
        - bucket (str): the name of the S3 Bucket to store Flows
        - key (str, optional): a unique key to use for uploading a Flow to S3. This
            is only useful when storing a single Flow using this storage object.
        - client_options (dict, optional): Additional options for the `boto3` client.
        - secrets (List[str], optional): a list of Prefect Secrets which will be used to populate `prefect.context`
            for each flow run.  Used primarily for providing authentication credentials.
    """

    def __init__(
        self,
        bucket: str,
        client_options: dict = None,
        key: str = None,
        secrets: List[str] = None,
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]
        self.bucket = bucket
        self.key = key

        self.client_options = client_options

        result = S3Result(bucket=bucket)
        super().__init__(result=result, secrets=secrets)

    @property
    def labels(self) -> List[str]:
        return ["s3-flow-storage"]

    def get_flow(self, flow_location: str) -> "Flow":
        """
        Given a flow_location within this Storage object, returns the underlying Flow (if possible).
        If the Flow is not found an error will be logged and `None` will be returned.

        Args:
            - flow_location (str): the location of a flow within this Storage; in this case,
                a file path where a Flow has been serialized to

        Returns:
            - Flow: the requested Flow

        Raises:
            - ValueError: if the Flow is not contained in this storage
            - botocore.ClientError: if there is an issue downloading the Flow from S3
        """
        if not flow_location in self.flows.values():
            raise ValueError("Flow is not contained in this Storage")

        stream = io.BytesIO()

        self.logger.info("Downloading {} from {}".format(flow_location, self.bucket))

        # Download stream from S3
        from botocore.exceptions import ClientError

        try:
            self._boto3_client.download_fileobj(
                Bucket=self.bucket, Key=flow_location, Fileobj=stream
            )
        except ClientError as err:
            self.logger.error("Error downloading Flow from S3: {}".format(err))
            raise err

        ## prepare data and return
        stream.seek(0)
        output = stream.read()

        return cloudpickle.loads(output)

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for storing a new flow as bytes in the local filesytem.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object

        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """
        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )

        # Create key for Flow that uniquely identifies Flow object in S3
        key = self.key or "{}/{}".format(
            slugify(flow.name), slugify(pendulum.now("utc").isoformat())
        )

        self.flows[flow.name] = key
        self._flows[flow.name] = flow
        return key

    def build(self) -> "Storage":
        """
        Build the S3 storage object by uploading Flows to an S3 bucket. This will upload
        all of the flows found in `storage.flows`. If there is an issue uploading to the
        S3 bucket an error will be logged.

        Returns:
            - Storage: an S3 object that contains information about how and where
                each flow is stored

        Raises:
            - botocore.ClientError: if there is an issue uploading a Flow to S3
        """
        self.run_basic_healthchecks()

        for flow_name, flow in self._flows.items():
            # Pickle Flow
            data = cloudpickle.dumps(flow)

            # Write pickled Flow to stream
            try:
                stream = io.BytesIO(data)
            except TypeError:
                stream = io.BytesIO(data.encode())

            self.logger.info(
                "Uploading {} to {}".format(self.flows[flow_name], self.bucket)
            )

            # Upload stream to S3
            from botocore.exceptions import ClientError

            try:
                self._boto3_client.upload_fileobj(
                    stream, Bucket=self.bucket, Key=self.flows[flow_name]
                )
            except ClientError as err:
                self.logger.error(
                    "Error uploading Flow to S3 bucket {}: {}".format(self.bucket, err)
                )
                raise err

        return self

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    @property
    def _boto3_client(self):  # type: ignore
        from prefect.utilities.aws import get_boto_client

        kwargs = self.client_options or {}
        return get_boto_client(
            resource="s3", credentials=None, use_session=False, **kwargs
        )
