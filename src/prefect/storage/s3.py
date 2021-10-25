import io
from contextlib import closing
from typing import TYPE_CHECKING, Any

import pendulum
from slugify import slugify

import prefect
from prefect.engine.results import S3Result
from prefect.storage import Storage
from prefect.utilities.storage import (
    extract_flow_from_file,
    flow_from_bytes_pickle,
    flow_to_bytes_pickle,
)

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
        - bucket (str): the name of the S3 Bucket to store Flows
        - key (str, optional): a unique key to use for uploading a Flow to S3. This
            is only useful when storing a single Flow using this storage object.
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `False`
        - local_script_path (str, optional): the path to a local script to upload when `stored_as_script`
            is set to `True`. If not set then the value of `local_script_path` from `prefect.context` is
            used. If neither are set then script will not be uploaded and users should manually place the
            script file in the desired `key` location in an S3 bucket.
        - client_options (dict, optional): Additional options for the `boto3` client.
        - upload_options (dict, optional): Additional options s3 client upload_file()
            and upload_fileobj() functions 'ExtraArgs' argument.
        - **kwargs (Any, optional): any additional `Storage` initialization options
    """

    def __init__(
        self,
        bucket: str,
        key: str = None,
        stored_as_script: bool = False,
        local_script_path: str = None,
        client_options: dict = None,
        upload_options: dict = None,
        **kwargs: Any,
    ) -> None:
        self.bucket = bucket
        self.key = key
        self.upload_options = upload_options
        self.local_script_path = local_script_path or prefect.context.get(
            "local_script_path", None
        )

        self.client_options = client_options

        result = S3Result(bucket=bucket, boto3_kwargs=client_options)
        super().__init__(
            result=result,
            stored_as_script=stored_as_script,
            **kwargs,
        )

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
        key = self.flows[flow_name]

        self.logger.info(f"Downloading flow from s3://{self.bucket}/{key}")

        try:
            obj = self._boto3_client.get_object(Bucket=self.bucket, Key=key)
            body = obj["Body"]
            with closing(body):
                output = body.read()
        except Exception as err:
            self.logger.error("Error downloading Flow from S3: {}".format(err))
            raise

        self.logger.info(
            "Flow successfully downloaded. ETag: %s, LastModified: %s, VersionId: %s",
            obj["ETag"],
            obj["LastModified"].isoformat(),
            obj.get("VersionId"),
        )

        if self.stored_as_script:
            return extract_flow_from_file(file_contents=output, flow_name=flow_name)  # type: ignore

        return flow_from_bytes_pickle(output)

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

        # Append .py extension when storing as script
        # if self.stored_as_script and not key.endswith(".py"):
        #     key = key + ".py"

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

        from botocore.exceptions import ClientError

        if self.stored_as_script:
            if self.local_script_path:
                for flow_name, flow in self._flows.items():
                    self.logger.info(
                        "Uploading script {} to {} in {}".format(
                            self.local_script_path, self.flows[flow.name], self.bucket
                        )
                    )

                    try:
                        self._boto3_client.upload_file(
                            self.local_script_path,
                            self.bucket,
                            self.flows[flow_name],
                            ExtraArgs=self.upload_options,
                        )
                    except ClientError as err:
                        self.logger.error(
                            "Error uploading Flow script to S3 bucket {}: {}".format(
                                self.bucket, err
                            )
                        )
                        raise err
            else:
                if not self.key:
                    raise ValueError(
                        "A `key` must be provided to show where flow `.py` file is stored in S3 or "
                        "provide a `local_script_path` pointing to a local script that contains the "
                        "flow."
                    )
            return self

        for flow_name, flow in self._flows.items():
            # Pickle Flow
            data = flow_to_bytes_pickle(flow)

            # Write pickled Flow to stream
            stream = io.BytesIO(data)

            self.logger.info(
                "Uploading {} to {}".format(self.flows[flow_name], self.bucket)
            )

            try:
                self._boto3_client.upload_fileobj(
                    stream,
                    Bucket=self.bucket,
                    Key=self.flows[flow_name],
                    ExtraArgs=self.upload_options,
                )
            except ClientError as err:
                self.logger.error(
                    "Error uploading Flow to S3 bucket {}: {}".format(self.bucket, err)
                )
                raise err

        return self

    @property
    def _boto3_client(self):  # type: ignore
        from prefect.utilities.aws import get_boto_client

        kwargs = self.client_options or {}
        return get_boto_client(resource="s3", credentials=None, **kwargs)
