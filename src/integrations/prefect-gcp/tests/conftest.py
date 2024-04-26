import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound as ApiCoreNotFound
from google.cloud.aiplatform_v1.types.job_state import JobState
from google.cloud.exceptions import NotFound
from prefect_gcp.credentials import GcpCredentials

from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    with prefect_test_harness():
        yield


@pytest.fixture(scope="session", autouse=True)
def disable_logging():
    with temporary_settings({PREFECT_LOGGING_TO_API_ENABLED: False}):
        yield


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield


@pytest.fixture
def google_auth(monkeypatch):
    google_auth_mock = MagicMock()
    default_credentials_mock = MagicMock(
        client_id="my_client_id", quota_project_id="my_project"
    )
    google_auth_mock.default.side_effect = lambda *args, **kwargs: (
        default_credentials_mock,
        None,
    )
    monkeypatch.setattr("google.auth", google_auth_mock)
    return google_auth_mock


@pytest.fixture
def google_auth_no_quota_project(monkeypatch):
    google_auth_mock = MagicMock()
    default_credentials_mock = MagicMock(
        client_id="my_client_id", quota_project_id=None
    )
    google_auth_mock.default.side_effect = lambda *args, **kwargs: (
        default_credentials_mock,
        "my_project",
    )
    monkeypatch.setattr("google.auth", google_auth_mock)
    return google_auth_mock


@pytest.fixture
def oauth2_credentials(monkeypatch):
    CredentialsMock = MagicMock()
    CredentialsMock.from_service_account_info.side_effect = (
        lambda json, scopes: MagicMock(scopes=scopes, **json)
    )
    CredentialsMock.from_service_account_file.side_effect = lambda file, scopes: file
    monkeypatch.setattr("prefect_gcp.credentials.Credentials", CredentialsMock)


class Blob:
    def __init__(self, name):
        self.name = name

    def download_to_filename(self, filename, **kwargs):
        Path(filename).write_text("abcdef")


class CloudStorageClient:
    def __init__(self, credentials=None, project=None):
        self.credentials = credentials
        self.project = project

    def create_bucket(self, bucket, location=None, **create_kwargs):
        bucket_obj = MagicMock(bucket=bucket)
        bucket_obj.name = "my-bucket"
        bucket_obj.location = location
        for key, value in create_kwargs.items():
            setattr(bucket_obj, key, value)
        return bucket_obj

    def get_bucket(self, bucket):
        blob_obj = MagicMock()
        blob_obj.download_as_bytes.return_value = b"bytes"
        blob_obj.download_to_file.side_effect = (
            lambda file_obj, **kwargs: file_obj.write(b"abcdef")
        )
        blob_obj.download_to_filename.side_effect = lambda filename, **kwargs: Path(
            filename
        ).write_text("abcdef")
        bucket_obj = MagicMock(bucket=bucket)
        bucket_obj.name = "my-bucket"
        bucket_obj.blob.side_effect = lambda blob, **kwds: blob_obj
        return bucket_obj

    def list_blobs(self, bucket, prefix=None):
        blob_obj = Blob(name="blob.txt")
        blob_directory = Blob(name="directory/")
        nested_blob_obj = Blob(name="base_folder/nested_blob.txt")
        double_nested_blob_obj = Blob(name="base_folder/sub_folder/nested_blob.txt")
        dotted_folder_blob_obj = Blob(name="dotted.folder/nested_blob.txt")
        blobs = [
            blob_obj,
            blob_directory,
            nested_blob_obj,
            double_nested_blob_obj,
            dotted_folder_blob_obj,
        ]
        if prefix:
            blobs = [blob for blob in blobs if blob.name.startswith(prefix)]
        return blobs


@pytest.fixture
def storage_client(monkeypatch):
    monkeypatch.setattr("prefect_gcp.credentials.StorageClient", CloudStorageClient)


class LoadJob:
    def __init__(self, output, *args, **kwargs):
        self.output = output
        self._client = "client"
        self._completion_lock = "completion_lock"


class BigQueryClient(MagicMock):
    def __init__(self, credentials=None, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credentials = credentials
        self.project = project

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def query(self, query, **kwargs):
        response = MagicMock()
        result = MagicMock()
        result.__iter__.return_value = [query]
        result.to_dataframe.return_value = f"dataframe_{query}"
        result.kwargs = kwargs
        response.result.return_value = result
        response.total_bytes_processed = 10
        return response

    def dataset(self, dataset):
        return MagicMock()

    def table(self, table):
        return MagicMock()

    def get_dataset(self, dataset):
        dataset_obj = MagicMock(table=MagicMock())
        return dataset_obj

    def create_dataset(self, dataset):
        return self.get_dataset(dataset)

    def get_table(self, table):
        raise NotFound("testing")

    def create_table(self, table):
        return table

    def insert_rows_json(self, table, json_rows):
        return json_rows

    def load_table_from_uri(self, uri, *args, **kwargs):
        output = MagicMock()
        output.result.return_value = LoadJob(uri)
        return output

    def load_table_from_file(self, *args, **kwargs):
        output = MagicMock()
        output.result.return_value = LoadJob("file")
        return output


class SecretManagerClient:
    def __init__(self, credentials=None, project=None):
        self.credentials = credentials
        self.project = project
        self._secrets = {}

    def create_secret(self, request=None, parent=None, secret_id=None, **kwds):
        response = MagicMock()
        if request:
            parent = request.parent
            secret_id = request.secret_id
        name = f"{parent}/secrets/{secret_id}"
        response.name = name
        self._secrets[name] = None
        return response

    def add_secret_version(self, request=None, parent=None, payload=None, **kwds):
        response = MagicMock()
        if request:
            parent = request.parent

        if parent not in self._secrets:
            raise ApiCoreNotFound(f"{parent!r} does not exist.")

        response.name = parent
        return response

    def access_secret_version(self, request=None, name=None, **kwds):
        response = MagicMock()
        payload = MagicMock()
        payload.data = "secret_data".encode("utf-8")
        response.payload = payload
        return response

    def delete_secret(self, request=None, name=None, **kwds):
        return name

    def destroy_secret_version(self, name, **kwds):
        return name


@pytest.fixture
def mock_credentials(monkeypatch):
    mock_credentials = MagicMock(name="MockGoogleCredentials")
    mock_authenticated_credentials = MagicMock(token="my-token")
    mock_credentials.from_service_account_info = mock_authenticated_credentials
    mock_credentials.from_service_account_file = mock_authenticated_credentials
    monkeypatch.setattr(
        "prefect_gcp.credentials.Credentials",  # noqa
        mock_credentials,
    )
    mock_auth = MagicMock()
    mock_auth.default.return_value = (mock_authenticated_credentials, "project")
    monkeypatch.setattr(
        "prefect_gcp.credentials.google.auth",  # noqa
        mock_auth,
    )
    return mock_credentials


@pytest.fixture
def job_service_client():
    job_service_client_mock = MagicMock()
    custom_run = MagicMock(name="mock_name")
    job_service_client_mock.create_custom_job.return_value = custom_run

    error = MagicMock(message="")
    custom_run_final = MagicMock(
        name="mock_name",
        state=JobState.JOB_STATE_SUCCEEDED,
        error=error,
        display_name="mock_display_name",
    )
    job_service_client_mock.get_custom_job.return_value = custom_run_final
    return job_service_client_mock


@pytest.fixture
def gcp_credentials(monkeypatch, google_auth, mock_credentials, job_service_client):
    gcp_credentials_mock = GcpCredentials(project="gcp_credentials_project")
    gcp_credentials_mock._service_account_email = "my_service_account_email"

    gcp_credentials_mock.cloud_storage_client = CloudStorageClient()
    gcp_credentials_mock.secret_manager_client = SecretManagerClient()
    gcp_credentials_mock.job_service_client = job_service_client
    gcp_credentials_mock.job_service_client.__enter__.return_value = job_service_client

    gcp_credentials_mock.get_cloud_storage_client = (
        lambda *args, **kwargs: gcp_credentials_mock.cloud_storage_client
    )
    gcp_credentials_mock.get_bigquery_client = lambda *args, **kwargs: BigQueryClient()
    gcp_credentials_mock.get_secret_manager_client = (
        lambda *args, **kwargs: gcp_credentials_mock.secret_manager_client
    )
    gcp_credentials_mock.get_job_service_client = (
        lambda *args, **kwargs: gcp_credentials_mock.job_service_client
    )
    return gcp_credentials_mock


@pytest.fixture()
def service_account_info(monkeypatch):
    monkeypatch.setattr(
        "google.auth.crypt._cryptography_rsa.serialization.load_pem_private_key",
        lambda *args, **kwargs: args[0],
    )
    _service_account_info = {
        "project_id": "my_project",
        "token_uri": "my-token-uri",
        "client_email": "my-client-email",
        "private_key": "my-private-key",
    }
    return _service_account_info


@pytest.fixture()
def service_account_info_json(monkeypatch):
    monkeypatch.setattr(
        "google.auth.crypt._cryptography_rsa.serialization.load_pem_private_key",
        lambda *args, **kwargs: args[0],
    )
    _service_account_info = json.dumps(
        {
            "project_id": "my_project",
            "token_uri": "my-token-uri",
            "client_email": "my-client-email",
            "private_key": "my-private-key",
        }
    )
    return _service_account_info
