import os
import io
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Union

import uuid

import cloudpickle
import pendulum
from slugify import slugify

import prefect
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

    Args:
        - aws_access_key_id (str, optional): AWS access key id for connecting to S3.
            Defaults to the value set in the environment variable
            `AWS_ACCESS_KEY_ID` or `None`
        - aws_secret_access_key (str, optional): AWS secret access key for connecting to S3.
            Defaults to the value set in the environment variable
            `AWS_SECRET_ACCESS_KEY` or `None`
        - aws_session_token (str, optional): AWS session key for connecting to S3
            Defaults to the value set in the environment variable
            `AWS_SESSION_TOKEN` or `None`
        - bucket (str, optional): the name of the S3 Bucket to store the Flow
        - key (str, optional): a unique key to use for uploading this Flow to S3
    """

    def __init__(
        self,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        bucket: str = None,
        key: str = None,
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self.bucket = bucket or ""
        self.key = key

        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token

        super().__init__()

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

        stream = io.BytesIO()

        ## Download stream from S3
        self._boto3_client.download_fileobj(
            Bucket=self.bucket, Key=flow_location, Fileobj=stream
        )

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

        # Pickle Flow
        data = cloudpickle.dumps(flow)

        # Write pickled Flow to stream
        try:
            stream = io.BytesIO(data)
        except TypeError:
            stream = io.BytesIO(data.encode())

        # Create key for Flow that uniquely identifies Flow object in S3
        key = self.key or "{}/{}".format(
            slugify(flow.name), slugify(pendulum.now("utc").isoformat())
        )

        # Upload stream to S3
        self._boto3_client.upload_fileobj(stream, Bucket=self.bucket, Key=key)

        self.flows[flow.name] = key
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
        Build the Storage object.

        Returns:
            - Storage: a Storage object that contains information about how and where
                each flow is stored
        """
        return self

    @property
    def _boto3_client(self):  # type: ignore
        from boto3 import client as boto3_client

        return boto3_client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
        )
