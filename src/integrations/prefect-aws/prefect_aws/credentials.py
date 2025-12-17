"""Module handling AWS credentials"""

import datetime
from enum import Enum
from functools import lru_cache
from threading import Lock
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import urlparse

import boto3
import botocore.auth
import botocore.awsrequest
import botocore.compat
from pydantic import ConfigDict, Field, SecretStr

from prefect.blocks.abstract import CredentialsBlock
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
    CODECOMMIT = "codecommit"


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


class AwsCodeCommitCredentials(CredentialsBlock):
    """
    Block used to manage authentication with AWS CodeCommit for Git operations.
    Uses SigV4 signing to generate authenticated Git URLs.

    Attributes:
        aws_credentials: An AwsCredentials block containing AWS authentication details.

    Example:
        Load stored credentials:
        ```python
        from prefect_aws import AwsCodeCommitCredentials
        aws_codecommit_credentials = AwsCodeCommitCredentials.load("BLOCK_NAME")

        signed_url = aws_codecommit_credentials.format_git_credentials(
            "https://git-codecommit.us-east-1.amazonaws.com/v1/repos/my-repo"
        )
        ```

        Use as part of a Git clone step in a Prefect deployment:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://git-codecommit.us-east-1.amazonaws.com/v1/repos/my-repo
                credentials: "{{ prefect.blocks.aws-codecommit-credentials.my-codecommit-credentials-block }}"
        ```
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa
    _block_type_name = "AWS CodeCommit Credentials"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-aws"  # noqa

    aws_credentials: AwsCredentials = Field(
        default=...,
        description="AWS credentials block for authentication.",
        title="AWS Credentials",
    )

    @staticmethod
    def _get_parts_from_url(url: str) -> tuple[str, str, str]:
        """
        Extract region and repository name from the given CodeCommit URL.

        Args:
            url: Repository URL (e.g., "https://git-codecommit.us-east-1.amazonaws.com/v1/repos/my-repo.git")

        Returns:
            A tuple containing (region, domain name, path)
        """
        parsed = urlparse(url)

        hostname_parts = parsed.hostname.split(".")
        region = hostname_parts[1]

        return region, parsed.hostname, parsed.path

    @staticmethod
    def _sign_codecommit_request(
        hostname: str, path: str, region: str, credentials: Any
    ) -> str:
        """
        Generate a SigV4 signature for a CodeCommit Git request.

        Args:
            hostname: CodeCommit hostname (e.g., git-codecommit.us-east-1.amazonaws.com)
            path: Request path (e.g., /v1/repos/my-repo)
            region: AWS region
            credentials: Botocore credentials object

        Returns:
            Signature string in format: {timestamp}Z{signature}
        """
        request = botocore.awsrequest.AWSRequest(
            method="GIT", url=f"https://{hostname}{path}"
        )
        request.context["timestamp"] = datetime.datetime.now(
            datetime.timezone.utc
        ).strftime("%Y%m%dT%H%M%S")

        signer = botocore.auth.SigV4Auth(credentials, "codecommit", region)
        canonical_request = f"GIT\n{path}\n\nhost:{hostname}\n\nhost\n"
        string_to_sign = signer.string_to_sign(request, canonical_request)
        signature = signer.signature(string_to_sign, request)
        return f"{request.context['timestamp']}Z{signature}"

    def format_git_credentials(self, url: str) -> str:
        """
        Format and return the full Git URL with AWS CodeCommit credentials embedded
        using SigV4 signing.

        Args:
            url: Repository URL (e.g., "https://github.com/org/repo.git")

        Returns:
            Complete URL with credentials embedded in format:
            https://{username}:{signature}@git-codecommit.{region}.{domain}/v1/repos/{repository}

        Raises:
            ValueError: If credentials are not available
        """
        # Extract region from the URL
        region, hostname, path = self._get_parts_from_url(url)

        # Get credentials from the AWS credentials block
        session = self.aws_credentials.get_boto3_session()
        credentials = session.get_credentials()

        if not credentials:
            raise ValueError(
                "AWS credentials are not available. Please configure your "
                "AWS credentials in the AwsCredentials block."
            )

        # Generate the signature
        signature = self._sign_codecommit_request(hostname, path, region, credentials)

        # Format username: access_key + optional token (for temporary credentials)
        token = f"%{credentials.token}" if credentials.token else ""
        username = botocore.compat.quote(f"{credentials.access_key}{token}", safe="")

        # Construct the final URL
        return f"https://{username}:{signature}@{hostname}{path}"

    def get_client(self):
        """
        Gets an authenticated CodeCommit client.

        Returns:
            An authenticated CodeCommit client.
        """
        return self.aws_credentials.get_client(client_type=ClientType.CODECOMMIT)


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    region_name: Optional[str] = Field(
        default=None,
        description="The AWS Region where you want to create new connections.",
    )
    aws_client_parameters: AwsClientParameters = Field(
        default_factory=AwsClientParameters,
        description="Extra parameters to initialize the Client.",
    )

    def __hash__(self):
        return hash(
            (
                hash(self.minio_root_user),
                hash(self.minio_root_password),
                hash(self.region_name),
                hash(self.aws_client_parameters),
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
                service_name="s3",
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

    def get_s3_client(self) -> "S3Client":
        """
        Gets an authenticated S3 client.

        Returns:
            An authenticated S3 client.
        """
        return self.get_client(client_type=ClientType.S3)
