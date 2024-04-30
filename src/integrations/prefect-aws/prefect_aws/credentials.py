"""Module handling AWS credentials"""

from enum import Enum
from functools import lru_cache
from threading import Lock
from typing import Any, Optional, Union

import boto3
from mypy_boto3_s3 import S3Client
from mypy_boto3_secretsmanager import SecretsManagerClient
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.abstract import CredentialsBlock

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretStr
else:
    from pydantic import Field, SecretStr

from prefect_aws.client_parameters import AwsClientParameters

_LOCK = Lock()


class ClientType(Enum):
    """The supported boto3 clients."""

    S3 = "s3"
    ECS = "ecs"
    BATCH = "batch"
    SECRETS_MANAGER = "secretsmanager"


@lru_cache(maxsize=8, typed=True)
def _get_client_cached(ctx, client_type: Union[str, ClientType]) -> Any:
    """
    Helper method to cache and dynamically get a client type.

    Args:
        client_type: The client's service name.

    Returns:
        An authenticated client.

    Raises:
        ValueError: if the client is not supported.
    """
    with _LOCK:
        if isinstance(client_type, ClientType):
            client_type = client_type.value

        client = ctx.get_boto3_session().client(
            service_name=client_type,
            **ctx.aws_client_parameters.get_params_override(),
        )
    return client


class AwsCredentials(CredentialsBlock):
    """
    Block used to manage authentication with AWS. AWS authentication is
    handled via the `boto3` module. Refer to the
    [boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
    for more info about the possible credential configurations.

    Example:
        Load stored AWS credentials:
        ```python
        from prefect_aws import AwsCredentials

        aws_credentials_block = AwsCredentials.load("BLOCK_NAME")
        ```
    """  # noqa E501

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa
    _block_type_name = "AWS Credentials"
    _documentation_url = "https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.AwsCredentials"  # noqa

    aws_access_key_id: Optional[str] = Field(
        default=None,
        description="A specific AWS access key ID.",
        title="AWS Access Key ID",
    )
    aws_secret_access_key: Optional[SecretStr] = Field(
        default=None,
        description="A specific AWS secret access key.",
        title="AWS Access Key Secret",
    )
    aws_session_token: Optional[str] = Field(
        default=None,
        description=(
            "The session key for your AWS account. "
            "This is only needed when you are using temporary credentials."
        ),
        title="AWS Session Token",
    )
    profile_name: Optional[str] = Field(
        default=None, description="The profile to use when creating your session."
    )
    region_name: Optional[str] = Field(
        default=None,
        description="The AWS Region where you want to create new connections.",
    )
    aws_client_parameters: AwsClientParameters = Field(
        default_factory=AwsClientParameters,
        description="Extra parameters to initialize the Client.",
        title="AWS Client Parameters",
    )

    class Config:
        """Config class for pydantic model."""

        arbitrary_types_allowed = True

    def __hash__(self):
        field_hashes = (
            hash(self.aws_access_key_id),
            hash(self.aws_secret_access_key),
            hash(self.aws_session_token),
            hash(self.profile_name),
            hash(self.region_name),
            hash(self.aws_client_parameters),
        )
        return hash(field_hashes)

    def get_boto3_session(self) -> boto3.Session:
        """
        Returns an authenticated boto3 session that can be used to create clients
        for AWS services

        Example:
            Create an S3 client from an authorized boto3 session:
            ```python
            aws_credentials = AwsCredentials(
                aws_access_key_id = "access_key_id",
                aws_secret_access_key = "secret_access_key"
                )
            s3_client = aws_credentials.get_boto3_session().client("s3")
            ```
        """

        if self.aws_secret_access_key:
            aws_secret_access_key = self.aws_secret_access_key.get_secret_value()
        else:
            aws_secret_access_key = None

        return boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            profile_name=self.profile_name,
            region_name=self.region_name,
        )

    def get_client(self, client_type: Union[str, ClientType]):
        """
        Helper method to dynamically get a client type.

        Args:
            client_type: The client's service name.

        Returns:
            An authenticated client.

        Raises:
            ValueError: if the client is not supported.
        """
        if isinstance(client_type, ClientType):
            client_type = client_type.value

        return _get_client_cached(ctx=self, client_type=client_type)

    def get_s3_client(self) -> S3Client:
        """
        Gets an authenticated S3 client.

        Returns:
            An authenticated S3 client.
        """
        return self.get_client(client_type=ClientType.S3)

    def get_secrets_manager_client(self) -> SecretsManagerClient:
        """
        Gets an authenticated Secrets Manager client.

        Returns:
            An authenticated Secrets Manager client.
        """
        return self.get_client(client_type=ClientType.SECRETS_MANAGER)


class MinIOCredentials(CredentialsBlock):
    """
    Block used to manage authentication with MinIO. Refer to the
    [MinIO docs](https://docs.min.io/docs/minio-server-configuration-guide.html)
    for more info about the possible credential configurations.

    Attributes:
        minio_root_user: Admin or root user.
        minio_root_password: Admin or root password.
        region_name: Location of server, e.g. "us-east-1".

    Example:
        Load stored MinIO credentials:
        ```python
        from prefect_aws import MinIOCredentials

        minio_credentials_block = MinIOCredentials.load("BLOCK_NAME")
        ```
    """  # noqa E501

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/676cb17bcbdff601f97e0a02ff8bcb480e91ff40-250x250.png"  # noqa
    _block_type_name = "MinIO Credentials"
    _description = (
        "Block used to manage authentication with MinIO. Refer to the MinIO "
        "docs: https://docs.min.io/docs/minio-server-configuration-guide.html "
        "for more info about the possible credential configurations."
    )
    _documentation_url = "https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.MinIOCredentials"  # noqa

    minio_root_user: str = Field(default=..., description="Admin or root user.")
    minio_root_password: SecretStr = Field(
        default=..., description="Admin or root password."
    )
    region_name: Optional[str] = Field(
        default=None,
        description="The AWS Region where you want to create new connections.",
    )
    aws_client_parameters: AwsClientParameters = Field(
        default_factory=AwsClientParameters,
        description="Extra parameters to initialize the Client.",
    )

    class Config:
        """Config class for pydantic model."""

        arbitrary_types_allowed = True

    def __hash__(self):
        return hash(
            (
                hash(self.minio_root_user),
                hash(self.minio_root_password),
                hash(self.region_name),
                hash(frozenset(self.aws_client_parameters.dict().items())),
            )
        )

    def get_boto3_session(self) -> boto3.Session:
        """
        Returns an authenticated boto3 session that can be used to create clients
        and perform object operations on MinIO server.

        Example:
            Create an S3 client from an authorized boto3 session

            ```python
            minio_credentials = MinIOCredentials(
                minio_root_user = "minio_root_user",
                minio_root_password = "minio_root_password"
            )
            s3_client = minio_credentials.get_boto3_session().client(
                service="s3",
                endpoint_url="http://localhost:9000"
            )
            ```
        """

        minio_root_password = (
            self.minio_root_password.get_secret_value()
            if self.minio_root_password
            else None
        )

        return boto3.Session(
            aws_access_key_id=self.minio_root_user,
            aws_secret_access_key=minio_root_password,
            region_name=self.region_name,
        )

    def get_client(self, client_type: Union[str, ClientType]):
        """
        Helper method to dynamically get a client type.

        Args:
            client_type: The client's service name.

        Returns:
            An authenticated client.

        Raises:
            ValueError: if the client is not supported.
        """
        if isinstance(client_type, ClientType):
            client_type = client_type.value

        return _get_client_cached(ctx=self, client_type=client_type)

    def get_s3_client(self) -> S3Client:
        """
        Gets an authenticated S3 client.

        Returns:
            An authenticated S3 client.
        """
        return self.get_client(client_type=ClientType.S3)
