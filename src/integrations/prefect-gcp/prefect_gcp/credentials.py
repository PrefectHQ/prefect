"""Module handling GCP credentials."""

import functools
import json
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Union

import google.auth
import google.auth.transport.requests
from google.oauth2.service_account import Credentials
from pydantic import Field, field_validator, model_validator

from prefect.blocks.abstract import CredentialsBlock
from prefect.types import SecretDict

try:
    from google.cloud.bigquery import Client as BigQueryClient
except ModuleNotFoundError:
    pass  # will be raised in get_client

try:
    from google.cloud.secretmanager import SecretManagerServiceClient
except ModuleNotFoundError:
    pass

try:
    from google.cloud.storage import Client as StorageClient
except ModuleNotFoundError:
    pass

try:
    from google.cloud.aiplatform.gapic import JobServiceAsyncClient, JobServiceClient
except ModuleNotFoundError:
    pass

try:
    from google.api_core.client_options import ClientOptions, from_dict
except ModuleNotFoundError:
    pass

_LOCK = Lock()


def _raise_help_msg(key: str):
    """
    Raises a helpful error message.

    Args:
        key: the key to access HELP_URLS
    """

    def outer(func):
        """
        Used for decorator.
        """

        @functools.wraps(func)
        def inner(*args, **kwargs):
            """
            Used for decorator.
            """
            try:
                return func(*args, **kwargs)
            except NameError as exc:
                raise ImportError(
                    f"To use prefect_gcp.{key}, install prefect-gcp with the "
                    f"'{key}' extra: `pip install 'prefect_gcp[{key}]'`"
                ) from exc

        return inner

    return outer


class ClientType(Enum):
    CLOUD_STORAGE = "cloud_storage"
    BIGQUERY = "bigquery"
    SECRET_MANAGER = "secret_manager"
    AIPLATFORM = "job_service"  # vertex ai


@functools.lru_cache(maxsize=8, typed=True)
def _get_job_service_async_client_cached(
    ctx, client_options: tuple
) -> "JobServiceAsyncClient":
    """
    Gets an authenticated Job Service async client for Vertex AI.

    Returns:
        An authenticated Job Service async client.
    """
    with _LOCK:
        client_options = dict(client_options)
        credentials = ctx.get_credentials_from_service_account()
        job_service_client = JobServiceAsyncClient(
            credentials=credentials, client_options=client_options
        )
    return job_service_client


class GcpCredentials(CredentialsBlock):
    """
    Block used to manage authentication with GCP. Google authentication is
    handled via the `google.oauth2` module or through the CLI.
    Specify either one of service `account_file` or `service_account_info`; if both
    are not specified, the client will try to detect the credentials following Google's
    [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).
    See Google's [Authentication documentation](https://cloud.google.com/docs/authentication#service-accounts)
    for details on inference and recommended authentication patterns.

    Attributes:
        service_account_file: Path to the service account JSON keyfile.
        service_account_info: The contents of the keyfile as a dict.

    Example:
        Load GCP credentials stored in a `GCP Credentials` Block:
        ```python
        from prefect_gcp import GcpCredentials
        gcp_credentials_block = GcpCredentials.load("BLOCK_NAME")
        ```
    """  # noqa

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/10424e311932e31c477ac2b9ef3d53cefbaad708-250x250.png"  # noqa
    _block_type_name = "GCP Credentials"
    _documentation_url = "https://prefecthq.github.io/prefect-gcp/credentials/#prefect_gcp.credentials.GcpCredentials"  # noqa: E501

    service_account_file: Optional[Path] = Field(
        default=None, description="Path to the service account JSON keyfile."
    )
    service_account_info: Optional[SecretDict] = Field(
        default=None, description="The contents of the keyfile as a dict."
    )
    project: Optional[str] = Field(
        default=None, description="The GCP project to use for the client."
    )

    _service_account_email: Optional[str] = None

    def __hash__(self):
        return hash(
            (
                hash(self.service_account_file),
                hash(frozenset(self.service_account_info.get_secret_value().items()))
                if self.service_account_info
                else None,
                hash(self.project),
                hash(self._service_account_email),
            )
        )

    @model_validator(mode="after")
    def _provide_one_service_account_source(self):
        """
        Ensure that only a service account file or service account info ias provided.
        """
        if self.service_account_info and self.service_account_file:
            raise ValueError(
                "Only one of service_account_info or service_account_file "
                "can be specified at once"
            )
        return self

    @field_validator("service_account_file")
    @classmethod
    def _check_service_account_file(cls, file):
        """Get full path of provided file and make sure that it exists."""
        if not file:
            return file

        service_account_file = Path(file).expanduser()
        if not service_account_file.exists():
            raise ValueError("The provided path to the service account is invalid")
        return service_account_file

    @field_validator("service_account_info", mode="before")
    @classmethod
    def _convert_json_string_json_service_account_info(cls, value):
        """
        Converts service account info provided as a json formatted string
        to a dictionary
        """
        if isinstance(value, str):
            try:
                service_account_info = json.loads(value)
                return service_account_info
            except Exception:
                raise ValueError("Unable to decode service_account_info")
        else:
            return value

    def block_initialization(self):
        credentials = self.get_credentials_from_service_account()
        if self.project is None:
            if self.service_account_info or self.service_account_file:
                credentials_project = credentials.project_id
            # google.auth.default using gcloud auth application-default login
            elif credentials.quota_project_id:
                credentials_project = credentials.quota_project_id
            # compute-assigned service account via GCP metadata server
            else:
                _, credentials_project = google.auth.default()
            self.project = credentials_project

        if hasattr(credentials, "service_account_email"):
            self._service_account_email = credentials.service_account_email

    def get_credentials_from_service_account(self) -> Credentials:
        """
        Helper method to serialize credentials by using either
        service_account_file or service_account_info.
        """
        if self.service_account_info:
            credentials = Credentials.from_service_account_info(
                self.service_account_info.get_secret_value(),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        elif self.service_account_file:
            credentials = Credentials.from_service_account_file(
                self.service_account_file,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            credentials, _ = google.auth.default()
        return credentials

    def get_access_token(self):
        """
        See: https://stackoverflow.com/a/69107745
        Also: https://www.jhanley.com/google-cloud-creating-oauth-access-tokens-for-rest-api-calls/
        """  # noqa
        request = google.auth.transport.requests.Request()
        credentials = self.get_credentials_from_service_account()
        credentials.refresh(request)
        return credentials.token

    def get_client(
        self,
        client_type: Union[str, ClientType],
        **get_client_kwargs: Dict[str, Any],
    ) -> Any:
        """
        Helper method to dynamically get a client type.

        Args:
            client_type: The name of the client to get.
            **get_client_kwargs: Additional keyword arguments to pass to the
                `get_*_client` method.

        Returns:
            An authenticated client.

        Raises:
            ValueError: if the client is not supported.
        """
        if isinstance(client_type, str):
            client_type = ClientType(client_type)
        client_type = client_type.value
        get_client_method = getattr(self, f"get_{client_type}_client")
        return get_client_method(**get_client_kwargs)

    @_raise_help_msg("cloud_storage")
    def get_cloud_storage_client(
        self, project: Optional[str] = None
    ) -> "StorageClient":
        """
        Gets an authenticated Cloud Storage client.

        Args:
            project: Name of the project to use; overrides the base
                class's project if provided.

        Returns:
            An authenticated Cloud Storage client.

        Examples:
            Gets a GCP Cloud Storage client from a path.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_file = "~/.secrets/prefect-service-account.json"
                client = GcpCredentials(
                    service_account_file=service_account_file
                ).get_cloud_storage_client()
            example_get_client_flow()
            ```

            Gets a GCP Cloud Storage client from a dictionary.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_info = {
                    "type": "service_account",
                    "project_id": "project_id",
                    "private_key_id": "private_key_id",
                    "private_key": "private_key",
                    "client_email": "client_email",
                    "client_id": "client_id",
                    "auth_uri": "auth_uri",
                    "token_uri": "token_uri",
                    "auth_provider_x509_cert_url": "auth_provider_x509_cert_url",
                    "client_x509_cert_url": "client_x509_cert_url"
                }
                client = GcpCredentials(
                    service_account_info=service_account_info
                ).get_cloud_storage_client()
            example_get_client_flow()
            ```
        """
        credentials = self.get_credentials_from_service_account()

        # override class project if method project is provided
        project = project or self.project
        storage_client = StorageClient(credentials=credentials, project=project)
        return storage_client

    @_raise_help_msg("bigquery")
    def get_bigquery_client(
        self, project: Optional[str] = None, location: Optional[str] = None
    ) -> "BigQueryClient":
        """
        Gets an authenticated BigQuery client.

        Args:
            project: Name of the project to use; overrides the base
                class's project if provided.
            location: Location to use.

        Returns:
            An authenticated BigQuery client.

        Examples:
            Gets a GCP BigQuery client from a path.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_file = "~/.secrets/prefect-service-account.json"
                client = GcpCredentials(
                    service_account_file=service_account_file
                ).get_bigquery_client()
            example_get_client_flow()
            ```

            Gets a GCP BigQuery client from a dictionary.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_info = {
                    "type": "service_account",
                    "project_id": "project_id",
                    "private_key_id": "private_key_id",
                    "private_key": "private_key",
                    "client_email": "client_email",
                    "client_id": "client_id",
                    "auth_uri": "auth_uri",
                    "token_uri": "token_uri",
                    "auth_provider_x509_cert_url": "auth_provider_x509_cert_url",
                    "client_x509_cert_url": "client_x509_cert_url"
                }
                client = GcpCredentials(
                    service_account_info=service_account_info
                ).get_bigquery_client()

            example_get_client_flow()
            ```
        """
        credentials = self.get_credentials_from_service_account()

        # override class project if method project is provided
        project = project or self.project
        big_query_client = BigQueryClient(
            credentials=credentials, project=project, location=location
        )
        return big_query_client

    @_raise_help_msg("secret_manager")
    def get_secret_manager_client(self) -> "SecretManagerServiceClient":
        """
        Gets an authenticated Secret Manager Service client.

        Returns:
            An authenticated Secret Manager Service client.

        Examples:
            Gets a GCP Secret Manager client from a path.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_file = "~/.secrets/prefect-service-account.json"
                client = GcpCredentials(
                    service_account_file=service_account_file
                ).get_secret_manager_client()
            example_get_client_flow()
            ```

            Gets a GCP Cloud Storage client from a dictionary.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_info = {
                    "type": "service_account",
                    "project_id": "project_id",
                    "private_key_id": "private_key_id",
                    "private_key": "private_key",
                    "client_email": "client_email",
                    "client_id": "client_id",
                    "auth_uri": "auth_uri",
                    "token_uri": "token_uri",
                    "auth_provider_x509_cert_url": "auth_provider_x509_cert_url",
                    "client_x509_cert_url": "client_x509_cert_url"
                }
                client = GcpCredentials(
                    service_account_info=service_account_info
                ).get_secret_manager_client()
            example_get_client_flow()
            ```
        """
        credentials = self.get_credentials_from_service_account()

        # doesn't accept project; must pass in project in tasks
        secret_manager_client = SecretManagerServiceClient(credentials=credentials)
        return secret_manager_client

    @_raise_help_msg("aiplatform")
    def get_job_service_client(
        self, client_options: Union[Dict[str, Any], ClientOptions] = None
    ) -> "JobServiceClient":
        """
        Gets an authenticated Job Service client for Vertex AI.

        Returns:
            An authenticated Job Service client.

        Examples:
            Gets a GCP Job Service client from a path.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_file = "~/.secrets/prefect-service-account.json"
                client = GcpCredentials(
                    service_account_file=service_account_file
                ).get_job_service_client()

            example_get_client_flow()
            ```

            Gets a GCP Cloud Storage client from a dictionary.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_info = {
                    "type": "service_account",
                    "project_id": "project_id",
                    "private_key_id": "private_key_id",
                    "private_key": "private_key",
                    "client_email": "client_email",
                    "client_id": "client_id",
                    "auth_uri": "auth_uri",
                    "token_uri": "token_uri",
                    "auth_provider_x509_cert_url": "auth_provider_x509_cert_url",
                    "client_x509_cert_url": "client_x509_cert_url"
                }
                client = GcpCredentials(
                    service_account_info=service_account_info
                ).get_job_service_client()

            example_get_client_flow()
            ```
        """
        if isinstance(client_options, dict):
            client_options = from_dict(client_options)

        credentials = self.get_credentials_from_service_account()
        return JobServiceClient(credentials=credentials, client_options=client_options)

    @_raise_help_msg("aiplatform")
    def get_job_service_async_client(
        self, client_options: Union[Dict[str, Any], ClientOptions] = None
    ) -> "JobServiceAsyncClient":
        """
        Gets an authenticated Job Service async client for Vertex AI.

        Returns:
            An authenticated Job Service async client.

        Examples:
            Gets a GCP Job Service client from a path.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_file = "~/.secrets/prefect-service-account.json"
                client = GcpCredentials(
                    service_account_file=service_account_file
                ).get_job_service_async_client()

            example_get_client_flow()
            ```

            Gets a GCP Cloud Storage client from a dictionary.
            ```python
            from prefect import flow
            from prefect_gcp.credentials import GcpCredentials

            @flow()
            def example_get_client_flow():
                service_account_info = {
                    "type": "service_account",
                    "project_id": "project_id",
                    "private_key_id": "private_key_id",
                    "private_key": "private_key",
                    "client_email": "client_email",
                    "client_id": "client_id",
                    "auth_uri": "auth_uri",
                    "token_uri": "token_uri",
                    "auth_provider_x509_cert_url": "auth_provider_x509_cert_url",
                    "client_x509_cert_url": "client_x509_cert_url"
                }
                client = GcpCredentials(
                    service_account_info=service_account_info
                ).get_job_service_async_client()

            example_get_client_flow()
            ```
        """
        if isinstance(client_options, dict):
            client_options = from_dict(client_options)

        return _get_job_service_async_client_cached(
            self, tuple(client_options.__dict__.items())
        )
