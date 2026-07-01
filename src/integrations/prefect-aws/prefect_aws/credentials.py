"""Module handling AWS credentials"""

import abc
import uuid
from enum import Enum
from functools import lru_cache
from threading import Lock
from typing import TYPE_CHECKING, Any, Optional, Union

import boto3
from pydantic import ConfigDict, Field, SecretStr

from prefect.blocks.abstract import CredentialsBlock
from prefect_aws.assume_role_parameters import AssumeRoleParameters
from prefect_aws.client_parameters import AwsClientParameters

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_secretsmanager import SecretsManagerClient

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

        params_override = ctx.aws_client_parameters.get_params_override()
        if ctx.region_name is not None:
            params_override["region_name"] = ctx.region_name
        client = ctx.get_boto3_session().client(
            service_name=client_type,
            **params_override,
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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa
    _block_type_name = "AWS Credentials"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-aws"  # noqa

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
    assume_role_arn: Optional[str] = Field(
        default=None,
        description="The ARN of the IAM role to assume.",
        title="Assume Role ARN",
    )
    assume_role_kwargs: AssumeRoleParameters = Field(
        default_factory=AssumeRoleParameters,
        description="Additional parameters for the assume_role call.",
        title="Assume Role Parameters",
    )

    def __hash__(self):
        field_hashes = (
            hash(self.aws_access_key_id),
            hash(self.aws_secret_access_key),
            hash(self.aws_session_token),
            hash(self.profile_name),
            hash(self.region_name),
            hash(self.aws_client_parameters),
            hash(self.assume_role_arn),
            hash(self.assume_role_kwargs),
        )
        return hash(field_hashes)

    def get_boto3_session(self) -> boto3.Session:
        """
        Returns an authenticated boto3 session that can be used to create clients
        for AWS services.

        If `assume_role_arn` is provided, this method will assume the specified IAM role
        and return a session with the temporary credentials from the assumed role.

        Example:
            Create an S3 client from an authorized boto3 session:
            ```python
            aws_credentials = AwsCredentials(
                aws_access_key_id = "access_key_id",
                aws_secret_access_key = "secret_access_key"
                )
            s3_client = aws_credentials.get_boto3_session().client("s3")
            ```

            Create a session with assume role:
            ```python
            aws_credentials = AwsCredentials(
                assume_role_arn="arn:aws:iam::123456789012:role/MyRole"
            )
            s3_client = aws_credentials.get_boto3_session().client("s3")
            ```

            Create a session with assume role and additional parameters:
            ```python
            aws_credentials = AwsCredentials(
                assume_role_arn="arn:aws:iam::123456789012:role/MyRole",
                assume_role_kwargs={
                    "RoleSessionName": "my-session",
                    "DurationSeconds": 3600,
                    "ExternalId": "unique-external-id"
                }
            )
            s3_client = aws_credentials.get_boto3_session().client("s3")
            ```
        """

        if self.aws_secret_access_key:
            aws_secret_access_key = self.aws_secret_access_key.get_secret_value()
        else:
            aws_secret_access_key = None

        base_session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            profile_name=self.profile_name,
            region_name=self.region_name,
        )

        # If assume_role_arn is provided, assume the role
        if self.assume_role_arn:
            sts_client = base_session.client("sts")

            # Prepare assume_role parameters
            assume_role_params = {
                "RoleArn": self.assume_role_arn,
            }

            # Get parameters from assume_role_kwargs
            kwargs_override = self.assume_role_kwargs.get_params_override()

            # Add RoleSessionName if provided, otherwise generate a default
            if "RoleSessionName" in kwargs_override:
                assume_role_params["RoleSessionName"] = kwargs_override[
                    "RoleSessionName"
                ]
            else:
                assume_role_params["RoleSessionName"] = (
                    f"prefect-session-{uuid.uuid4().hex[:8]}"
                )

            # Add all other assume_role_kwargs (excluding RoleSessionName if it was in kwargs_override)
            for key, value in kwargs_override.items():
                if key != "RoleSessionName":  # Already handled above
                    assume_role_params[key] = value

            # Assume the role
            response = sts_client.assume_role(**assume_role_params)
            credentials = response["Credentials"]

            # Create a new session with the assumed role credentials
            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=self.region_name,
            )

        return base_session

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

    def get_s3_client(self) -> "S3Client":
        """
        Gets an authenticated S3 client.

        Returns:
            An authenticated S3 client.
        """
        return self.get_client(client_type=ClientType.S3)

    def get_secrets_manager_client(self) -> "SecretsManagerClient":
        """
        Gets an authenticated Secrets Manager client.

        Returns:
            An authenticated Secrets Manager client.
        """
        return self.get_client(client_type=ClientType.SECRETS_MANAGER)


class S3CompatibleCredentials(CredentialsBlock, abc.ABC):
    """
    Base block for authentication against any S3-compatible object storage
    service (Backblaze B2, Cloudflare R2, MinIO, Wasabi, etc.).

    Subclasses provide vendor-named credential fields and implement
    `_access_key_id` / `_secret_access_key`; this base class handles the
    shared boto3 session and client plumbing.

    For the generic case, use `AwsCredentials` with
    `aws_client_parameters.endpoint_url` set to the provider's S3 endpoint.

    Attributes:
        region_name: Region or location of the bucket. Must match the region
            segment in `aws_client_parameters.endpoint_url` when the provider
            requires it.
        aws_client_parameters: Extra parameters used to initialize the boto3
            client; set `endpoint_url` here.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    region_name: Optional[str] = Field(
        default=None,
        description="Region or location of the bucket.",
    )
    aws_client_parameters: AwsClientParameters = Field(
        default_factory=AwsClientParameters,
        description="Extra parameters to initialize the Client.",
    )

    # Inheriting from `abc.ABC` opts this class out of Prefect's Block
    # registry (see `prefect.utilities.dispatch._register_subclass_of_base_type`),
    # so only concrete vendor subclasses appear in the Blocks UI and in the
    # block-standards test suite.

    @property
    @abc.abstractmethod
    def _access_key_id(self) -> str: ...

    @property
    @abc.abstractmethod
    def _secret_access_key(self) -> Optional[SecretStr]: ...

    def get_boto3_session(self) -> boto3.Session:
        """
        Returns an authenticated boto3 session that can be used to create
        clients and perform object operations on the S3-compatible service.
        """
        secret = (
            self._secret_access_key.get_secret_value()
            if self._secret_access_key
            else None
        )
        return boto3.Session(
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=secret,
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

    def get_s3_client(self) -> "S3Client":
        """
        Gets an authenticated S3 client.

        Returns:
            An authenticated S3 client.
        """
        return self.get_client(client_type=ClientType.S3)


class MinIOCredentials(S3CompatibleCredentials):
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
    _documentation_url = "https://docs.prefect.io/integrations/prefect-aws"  # noqa

    minio_root_user: str = Field(default=..., description="Admin or root user.")
    minio_root_password: SecretStr = Field(
        default=..., description="Admin or root password."
    )

    @property
    def _access_key_id(self) -> str:
        return self.minio_root_user

    @property
    def _secret_access_key(self) -> Optional[SecretStr]:
        return self.minio_root_password

    def __hash__(self):
        return hash(
            (
                hash(self.minio_root_user),
                hash(self.minio_root_password),
                hash(self.region_name),
                hash(self.aws_client_parameters),
            )
        )


class BackblazeB2Credentials(S3CompatibleCredentials):
    """
    Block used to manage authentication with Backblaze B2 via its
    [S3-compatible API](https://www.backblaze.com/docs/cloud-storage-s3-compatible-api).
    Create a bucket-scoped [Application Key](https://www.backblaze.com/docs/cloud-storage-application-keys)
    in the B2 console; the `keyID` becomes `application_key_id` and the
    `applicationKey` becomes `application_key`.

    Attributes:
        application_key_id: B2 application key ID (the "keyID" in the B2
            console).
        application_key: B2 application key (the "applicationKey" in the B2
            console).
        region_name: B2 region, e.g. "us-west-004". Must match the region
            segment in `aws_client_parameters.endpoint_url`.

    Example:
        Load stored Backblaze B2 credentials:
        ```python
        from prefect_aws import BackblazeB2Credentials

        b2_credentials_block = BackblazeB2Credentials.load("BLOCK_NAME")
        ```
    """  # noqa E501

    _logo_url = "https://cdn.prod.website-files.com/63d32de856f6323a43a277f2/64b1ab4daf31e414a481b056_Webclip.png"  # noqa
    _block_type_name = "Backblaze B2 Credentials"
    _description = (
        "Block used to manage authentication with Backblaze B2 via its "
        "S3-compatible API. See "
        "https://www.backblaze.com/docs/cloud-storage-s3-compatible-api"
    )
    _documentation_url = "https://docs.prefect.io/integrations/prefect-aws"  # noqa

    application_key_id: str = Field(
        default=...,
        description='B2 application key ID (the "keyID" in the B2 console).',
    )
    application_key: SecretStr = Field(
        default=...,
        description='B2 application key (the "applicationKey" in the B2 console).',
    )

    @property
    def _access_key_id(self) -> str:
        return self.application_key_id

    @property
    def _secret_access_key(self) -> Optional[SecretStr]:
        return self.application_key

    def __hash__(self):
        return hash(
            (
                hash(self.application_key_id),
                hash(self.application_key),
                hash(self.region_name),
                hash(self.aws_client_parameters),
            )
        )
