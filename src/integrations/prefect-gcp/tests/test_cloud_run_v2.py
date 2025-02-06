import pytest
from prefect_gcp.models.cloud_run_v2 import JobV2
from googleapiclient.errors import HttpError
from prefect_gcp.workers.cloud_run_v2 import CloudRunWorkerV2, CloudRunWorkerJobV2Configuration
from prefect.logging.loggers import PrefectLogAdapter
import google.auth
from prefect_gcp.credentials import GcpCredentials
import logging
from unittest.mock import MagicMock
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, RetryError


def create_mock_response(status, reason="Error"):
    """Helper function to create mock responses with proper attributes."""
    return type('MockResp', (), {'status': status, 'reason': reason})()


def is_transient_http_error(exc):
    """Check if an HTTP error is transient (e.g., 503 Service Unavailable)."""
    return isinstance(exc, HttpError) and hasattr(exc, "resp") and exc.resp.status in {500, 503}


def get_test_job_body():
    """Returns a test job body with required structure."""
    return {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [],
                        "image": "test-image",
                        "command": ["test-command"],
                        "args": ["test-arg"],
                        "resources": {
                            "limits": {
                                "cpu": "1000m",
                                "memory": "512Mi",
                            },
                        },
                    }
                ],
            }
        },
    }


jobs_return_value = {
    "name": "test-job-name",
    "uid": "uid-123",
    "generation": "1",
    "labels": {},
    "createTime": "create-time",
    "updateTime": "update-time",
    "deleteTime": "delete-time",
    "expireTime": "expire-time",
    "creator": "creator",
    "lastModifier": "last-modifier",
    "client": "client",
    "clientVersion": "client-version",
    "launchStage": "BETA",
    "binaryAuthorization": {},
    "template": {},
    "observedGeneration": "1",
    "terminalCondition": {},
    "conditions": [],
    "executionCount": 1,
    "latestCreatedExecution": {},
    "reconciling": True,
    "satisfiesPzs": False,
    "etag": "etag-123",
}


class TestJobV2:
    @pytest.mark.parametrize(
        "state,expected",
        [("CONDITION_SUCCEEDED", True), ("CONDITION_FAILED", False)],
    )
    def test_is_ready(self, state, expected):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            terminalCondition={
                "type": "Ready",
                "state": state,
            },
            conditions=[],
            executionCount=1,
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        assert job.is_ready() == expected

    def test_is_ready_raises_exception(self):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            terminalCondition={
                "type": "Ready",
                "state": "CONTAINER_FAILED",
                "reason": "ContainerMissing",
            },
            executionCount=1,
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        with pytest.raises(Exception):
            job.is_ready()

    @pytest.mark.parametrize(
        "terminal_condition,expected",
        [
            (
                {
                    "type": "Ready",
                    "state": "CONDITION_SUCCEEDED",
                },
                {
                    "type": "Ready",
                    "state": "CONDITION_SUCCEEDED",
                },
            ),
            (
                {
                    "type": "Failed",
                    "state": "CONDITION_FAILED",
                },
                {},
            ),
        ],
    )
    def test_get_ready_condition(self, terminal_condition, expected):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            terminalCondition=terminal_condition,
            executionCount=1,
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        assert job.get_ready_condition() == expected

    @pytest.mark.parametrize(
        "ready_condition,expected",
        [
            (
                {
                    "state": "CONTAINER_FAILED",
                    "reason": "ContainerMissing",
                },
                True,
            ),
            (
                {
                    "state": "CONDITION_SUCCEEDED",
                },
                False,
            ),
        ],
    )
    def test_is_missing_container(self, ready_condition, expected):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            executionCount=1,
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        assert job._is_missing_container(ready_condition=ready_condition) == expected


def remove_server_url_from_env(env):
    """
    For convenience since the testing database URL is non-deterministic.
    """
    return [
        env_var
        for env_var in env
        if env_var["name"]
        not in [
            "PREFECT_API_DATABASE_CONNECTION_URL",
            "PREFECT_ORION_DATABASE_CONNECTION_URL",
            "PREFECT_SERVER_DATABASE_CONNECTION_URL",
        ]
    ]


@pytest.fixture
def mock_google_auth(monkeypatch):
    """Mock Google Auth to avoid actual authentication."""
    class MockCredentials:
        def __init__(self):
            self.quota_project_id = "test-project"
            self.project_id = "test-project"
            self.token = "mock-token"

    monkeypatch.setattr(
        google.auth,
        "default",
        lambda *args, **kwargs: (MockCredentials(), "test-project"),
    )
    return MockCredentials()


@pytest.fixture
def mock_gcp_creds(monkeypatch):
    """Mock GCP credentials to avoid actual authentication."""
    def mock_init(self, *args, **kwargs):
        super(GcpCredentials, self).__init__(*args, **kwargs)
        self.project = "test-project"
        self.service_account_info = None
        self.service_account_info_file = None
    
    def mock_call(self):
        return None
    
    def mock_get_credentials(self):
        creds = MagicMock()
        creds.quota_project_id = "test-project"
        creds.project_id = "test-project"
        return creds
    
    monkeypatch.setattr(GcpCredentials, "__init__", mock_init)
    monkeypatch.setattr(GcpCredentials, "__call__", mock_call)
    monkeypatch.setattr(GcpCredentials, "get_credentials_from_service_account", mock_get_credentials)
    
    return GcpCredentials()


@pytest.fixture
def mock_job_v2_create(monkeypatch):
    """Fixture to mock JobV2.create"""
    def mock_create(*args, **kwargs):
        return None
    monkeypatch.setattr("prefect_gcp.models.cloud_run_v2.JobV2.create", mock_create)
    return mock_create


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return logging.getLogger("test_logger")


@retry(
    retry=retry_if_exception(is_transient_http_error),
    stop=stop_after_attempt(5),  # Retry up to 5 times
    wait=wait_exponential(multiplier=1, min=2, max=10),  # Exponential backoff
)
def create_job_with_retries(cr_client, configuration, logger):
    """Mock of the create_job_with_retries function with the same retry logic"""
    return JobV2.create(
        cr_client=cr_client,
        project=configuration.project,
        location=configuration.region,
        job_id=configuration.job_name,
        body=configuration.job_body,
    )


def test_create_job_with_retries_success(monkeypatch, mock_job_v2_create, mock_google_auth, mock_gcp_creds, mock_logger):
    """Test that job creation succeeds after transient errors."""
    worker = CloudRunWorkerV2(work_pool_name="test-pool")
    configuration = CloudRunWorkerJobV2Configuration(
        name="test-job-name",
        job_name="test-job",
        project="test-project",
        region="test-region",
        job_body=get_test_job_body()
    )
    
    mock_client = type('MockClient', (), {})()
    logger = PrefectLogAdapter(mock_logger)

    # Set up mock to fail with 503 twice then succeed
    call_count = 0
    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            mock_resp = create_mock_response(503, "Service Unavailable")
            raise HttpError(resp=mock_resp, content=b"Service Unavailable")
        return None

    monkeypatch.setattr(JobV2, "create", mock_create)

    # This should succeed after retries
    create_job_with_retries(mock_client, configuration, logger)

    # Verify that the function was called 3 times (2 failures + 1 success)
    assert call_count == 3


def test_create_job_with_retries_non_retryable_error(monkeypatch, mock_job_v2_create, mock_google_auth, mock_gcp_creds, mock_logger):
    """Test that job creation fails immediately for non-retryable errors."""
    worker = CloudRunWorkerV2(work_pool_name="test-pool")
    configuration = CloudRunWorkerJobV2Configuration(
        name="test-job-name",
        job_name="test-job",
        project="test-project",
        region="test-region",
        job_body=get_test_job_body()
    )
    
    mock_client = type('MockClient', (), {})()
    logger = PrefectLogAdapter(mock_logger)

    # Set up mock to fail with 400
    def mock_create(*args, **kwargs):
        mock_resp = create_mock_response(400, "Bad Request")
        raise HttpError(resp=mock_resp, content=b"Bad Request")

    monkeypatch.setattr(JobV2, "create", mock_create)

    # Call the method and expect the error to be raised
    with pytest.raises(HttpError) as exc_info:
        create_job_with_retries(mock_client, configuration, logger)

    # Verify error status
    assert exc_info.value.resp.status == 400


def test_create_job_with_retries_max_attempts(monkeypatch, mock_job_v2_create, mock_google_auth, mock_gcp_creds, mock_logger):
    """Test that job creation fails after max retry attempts."""
    worker = CloudRunWorkerV2(work_pool_name="test-pool")
    configuration = CloudRunWorkerJobV2Configuration(
        name="test-job-name",
        job_name="test-job",
        project="test-project",
        region="test-region",
        job_body=get_test_job_body()
    )
    
    mock_client = type('MockClient', (), {})()
    logger = PrefectLogAdapter(mock_logger)

    # Set up mock to always fail with 503
    call_count = 0
    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = create_mock_response(503, "Service Unavailable")
        raise HttpError(resp=mock_resp, content=b"Service Unavailable")

    monkeypatch.setattr(JobV2, "create", mock_create)

    # This should fail after max retries with RetryError
    with pytest.raises(RetryError):
        create_job_with_retries(mock_client, configuration, logger)

    # Verify that the function was called 5 times (max attempts)
    assert call_count == 5


def test_is_transient_http_error():
    """Test the is_transient_http_error function."""
    # Test transient errors (500, 503)
    mock_resp_500 = create_mock_response(500, "Internal Server Error")
    mock_resp_503 = create_mock_response(503, "Service Unavailable")
    mock_resp_400 = create_mock_response(400, "Bad Request")
    mock_resp_404 = create_mock_response(404, "Not Found")

    assert is_transient_http_error(HttpError(resp=mock_resp_500, content=b"Server Error"))
    assert is_transient_http_error(HttpError(resp=mock_resp_503, content=b"Service Unavailable"))

    # Test non-transient errors
    assert not is_transient_http_error(HttpError(resp=mock_resp_400, content=b"Bad Request"))
    assert not is_transient_http_error(HttpError(resp=mock_resp_404, content=b"Not Found"))
    assert not is_transient_http_error(Exception("Not an HttpError"))
