import uuid
from unittest.mock import Mock, patch

import pytest
from prefect_snowflake import SnowflakeCredentials
from prefect_snowflake.experimental.workers.spcs import (
    SPCSServiceTemplateVariables,
    SPCSWorker,
    SPCSWorkerConfiguration,
)
from pydantic import SecretStr

from prefect.client.schemas import FlowRun
from prefect.server.schemas.core import Flow
from prefect.testing.utilities import AsyncMock
from prefect.utilities.dockerutils import get_prefect_image_name

# Import exceptions that might be used in tests
try:
    from snowflake.core.exceptions import NotFoundError
except ImportError:
    # Create a mock NotFoundError if the actual one isn't available
    class NotFoundError(Exception):
        pass


# Mock classes for timeout behavior testing
class MockComputePool:
    """Mock compute pool for testing timeout behavior."""

    def __init__(self, states=None):
        self.states = states or ["IDLE", "ACTIVE"]
        self.call_count = 0

    def fetch(self):
        mock_result = Mock()
        if self.call_count < len(self.states):
            mock_result.state = self.states[self.call_count]
        else:
            mock_result.state = self.states[-1]
        self.call_count += 1
        return mock_result


class MockService:
    """Mock service for testing timeout behavior."""

    def __init__(self, container_states=None):
        self.container_states = container_states or ["RUNNING"]
        self.call_count = 0

    def get_containers(self):
        container = Mock()
        if self.call_count < len(self.container_states):
            container.service_status = self.container_states[self.call_count]
        else:
            container.service_status = self.container_states[-1]
        self.call_count += 1
        return [container]


# Helper functions
async def create_job_configuration(
    snowflake_credentials, worker_flow_run, overrides=None, run_prep=True
):
    """
    Returns a basic initialized SPCS infrastructure block suitable for use in a variety of tests.
    """
    if overrides is None:
        overrides = {}

    values = {
        "command": "test",
        "env": {},
        "snowflake_credentials": snowflake_credentials,
        "compute_pool": "common.compute.test_pool",
        "name": None,
        "service_watch_poll_interval": 1,
        "stream_output": False,
    }

    for k, v in overrides.items():
        values = {**values, k: v}

    job_service_variables = SPCSServiceTemplateVariables(**values)

    json_config = {
        "job_configuration": SPCSWorkerConfiguration.json_template(),
        "variables": job_service_variables.model_dump(),
    }

    job_service_configuration = await SPCSWorkerConfiguration.from_template_and_values(
        json_config, values
    )

    if run_prep:
        job_service_configuration.prepare_for_flow_run(worker_flow_run)

    return job_service_configuration


# Fixtures
@pytest.fixture
def snowflake_credentials():
    account = "test_account"
    user = "test_user"
    password = "test_password"

    return SnowflakeCredentials(account=account, user=user, password=password)


@pytest.fixture
def mock_prefect_client(worker_flow):
    """
    A fixture that provides a mock Prefect client
    """
    mock_client = Mock()
    mock_client.read_flow = AsyncMock()
    mock_client.read_flow.return_value = worker_flow

    return mock_client


@pytest.fixture
def worker_flow():
    return Flow(id=uuid.uuid4(), name="test-flow")


@pytest.fixture
def worker_flow_run(worker_flow):
    return FlowRun(id=uuid.uuid4(), flow_id=worker_flow.id, name="test-flow-run")


# Tests
async def test_worker_valid_command_validation(snowflake_credentials, worker_flow_run):
    # ensure the validator allows valid commands to pass through
    command = "command arg1 arg2"

    spcs_job_config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"command": command}
    )

    assert spcs_job_config.command == command


def test_worker_invalid_command_validation(snowflake_credentials):
    # ensure invalid commands cause a validation error
    with pytest.raises(ValueError):
        SPCSWorkerConfiguration(
            command=["invalid_command", "arg1", "arg2"],
            subscription_id=SecretStr("test"),
            resource_group_name="test",
            snowflake_credentials=snowflake_credentials,
        )


async def test_job_configuration_creation(snowflake_credentials, worker_flow_run):
    config = {
        "snowflake_credentials": snowflake_credentials,
        "image": "my-image",
        "image_registry": "my_image_registry",
        "compute_pool": "common.compute.test_pool",
        "external_access_integrations": ["test_integration"],
        "cpu_request": "1",
        "memory_request": "1G",
        "env": {"TEST": "VALUE"},
    }

    spcs_job_config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, config
    )

    assert spcs_job_config.image == "my-image"
    assert spcs_job_config.image_registry == "my_image_registry"
    assert spcs_job_config.cpu_request == "1"
    assert spcs_job_config.memory_request == "1G"
    assert spcs_job_config.env.get("TEST") == "VALUE"
    assert spcs_job_config.compute_pool == "common.compute.test_pool"
    assert spcs_job_config.external_access_integrations == ["test_integration"]
    assert (
        spcs_job_config.snowflake_credentials.account == snowflake_credentials.account
    )
    assert spcs_job_config.snowflake_credentials.user == snowflake_credentials.user
    assert (
        spcs_job_config.snowflake_credentials.password == snowflake_credentials.password
    )


async def test_image_populated_in_template_when_not_provided(
    worker_flow_run, snowflake_credentials
):
    config = await SPCSWorkerConfiguration.from_template_and_values(
        base_job_template=SPCSWorker.get_default_base_job_template(),
        values=SPCSServiceTemplateVariables(
            snowflake_credentials=snowflake_credentials,
            compute_pool="common.compute.test_pool",
        ).model_dump(exclude_unset=True),
    )
    config.prepare_for_flow_run(worker_flow_run)

    assert config.image == get_prefect_image_name()
    assert (
        config.job_manifest["spec"]["containers"][0]["image"]
        == get_prefect_image_name()
    )


@pytest.mark.parametrize(
    "flow_name",
    [
        "Short Flow",
        "Another Notification",
        "Extremely Long Flow Name That Exceeds The Maximum Length Allowed",
    ],
)
async def test_consistent_service_job_naming(
    mock_prefect_client: mock_prefect_client,
    worker_flow_run,
    flow_name,
):
    max_length = 63

    flow = Flow(id=worker_flow_run.flow_id, name=flow_name)
    mock_prefect_client.read_flow.return_value = flow

    flow_run = FlowRun(flow_id=flow.id, name=f"{flow_name} run")

    service_job_name = SPCSWorker._slugify_service_name(
        service_name=flow_name, flow_run_id=flow_run.id
    )

    assert " " not in service_job_name
    assert all(c.isalnum() or c in ("-", "_") for c in service_job_name)
    assert service_job_name.endswith(str(flow_run.id).replace("-", "_"))

    name_without_id = service_job_name[:-37]

    assert name_without_id.replace("_", " ").lower() in flow_name.lower()

    assert len(service_job_name) <= max_length, (
        f"Length: {len(service_job_name)}, Max: {max_length}"
    )


async def test_timeout_configuration_defaults(snowflake_credentials, worker_flow_run):
    """Test that timeout configurations have expected default values."""
    spcs_job_config = await create_job_configuration(
        snowflake_credentials, worker_flow_run
    )

    # Test default timeout values
    assert spcs_job_config.pool_start_timeout_seconds == 600
    assert spcs_job_config.service_start_timeout_seconds == 300


async def test_timeout_configuration_custom_values(
    snowflake_credentials, worker_flow_run
):
    """Test that custom timeout values are properly set."""
    config_overrides = {
        "pool_start_timeout_seconds": 120,
        "service_start_timeout_seconds": 60,
    }

    spcs_job_config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, config_overrides
    )

    assert spcs_job_config.pool_start_timeout_seconds == 120
    assert spcs_job_config.service_start_timeout_seconds == 60


@pytest.mark.parametrize(
    "timeout_seconds,expected_valid",
    [
        (0, True),  # Zero timeout means no timeout
        (1, True),  # Minimum positive timeout
        (3600, True),  # One hour timeout
        (-1, False),  # Negative timeouts should be invalid
    ],
)
def test_timeout_validation(snowflake_credentials, timeout_seconds, expected_valid):
    """Test validation of timeout values."""
    if expected_valid:
        # Should not raise an exception
        config = SPCSWorkerConfiguration(
            snowflake_credentials=snowflake_credentials,
            compute_pool="common.compute.test_pool",
            pool_start_timeout_seconds=timeout_seconds,
            service_start_timeout_seconds=timeout_seconds,
        )
        assert config.pool_start_timeout_seconds == timeout_seconds
        assert config.service_start_timeout_seconds == timeout_seconds
    else:
        # Should raise a validation error
        with pytest.raises(ValueError):
            SPCSWorkerConfiguration(
                snowflake_credentials=snowflake_credentials,
                compute_pool="common.compute.test_pool",
                pool_start_timeout_seconds=timeout_seconds,
                service_start_timeout_seconds=timeout_seconds,
            )


@pytest.mark.asyncio
async def test_pool_start_timeout_behavior(snowflake_credentials, worker_flow_run):
    """Test that pool start timeout properly raises RuntimeError when exceeded."""
    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"pool_start_timeout_seconds": 1},  # Very short timeout for testing
    )

    worker = SPCSWorker()

    # Mock the root and compute pool to simulate a pool that never becomes ACTIVE
    mock_root = Mock()
    mock_compute_pool = MockComputePool(
        states=["IDLE", "RESIZING", "IDLE"]
    )  # Never becomes ACTIVE
    mock_root.compute_pools = {"test_pool": mock_compute_pool}

    with patch("time.sleep"):
        with patch("time.time") as mock_time:
            # Simulate time progressing to exceed timeout
            mock_time.side_effect = [0, 0.5, 1.1, 1.5]  # Time progression

            with pytest.raises(
                RuntimeError, match="Timed out.*while waiting for compute pool start"
            ):
                worker._watch_service("test_service", mock_root, config)


@pytest.mark.asyncio
async def test_service_start_timeout_behavior(snowflake_credentials, worker_flow_run):
    """Test that service start timeout properly raises RuntimeError when exceeded."""
    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"service_start_timeout_seconds": 1},  # Very short timeout for testing
    )

    worker = SPCSWorker()

    # Mock the root, compute pool (becomes active quickly), and service
    mock_root = Mock()
    mock_compute_pool = MockComputePool(
        states=["ACTIVE"]
    )  # Pool becomes active immediately
    mock_root.compute_pools = {"test_pool": mock_compute_pool}

    # Mock service that raises NotFoundError (service not ready)
    mock_service = Mock()
    mock_service.get_containers.side_effect = NotFoundError("Service not found")

    mock_root.databases = {
        "common": Mock(
            **{
                "schemas": {
                    "compute": Mock(**{"services": {"test_service": mock_service}})
                }
            }
        )
    }

    with patch("time.sleep"):
        with patch("time.time") as mock_time:
            # Simulate time progressing: pool check passes, then service timeout
            mock_time.side_effect = [0, 0.1, 0.2, 0.5, 1.1, 1.5]  # Time progression

            with pytest.raises(
                RuntimeError, match="Timed out.*while waiting for service start"
            ):
                worker._watch_service("test_service", mock_root, config)


@pytest.mark.asyncio
async def test_zero_timeout_disables_timeout_check(
    snowflake_credentials, worker_flow_run
):
    """Test that zero timeout values disable timeout checking."""
    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {
            "pool_start_timeout_seconds": 0,
            "service_start_timeout_seconds": 0,
        },
    )

    worker = SPCSWorker()

    # Mock the root and compute pool to simulate extended delays
    mock_root = Mock()
    mock_compute_pool = Mock()
    # Simulate a pool that takes a while but eventually becomes active
    mock_compute_pool.fetch.side_effect = [
        Mock(state="IDLE"),
        Mock(state="IDLE"),
        Mock(state="ACTIVE"),
    ]
    mock_root.compute_pools = {"test_pool": mock_compute_pool}

    # Mock service that becomes ready
    mock_service = Mock()
    mock_container = Mock()
    mock_container.service_status = "DONE"  # Completes successfully
    mock_service.get_containers.return_value = [mock_container]

    mock_root.databases = {
        "common": Mock(
            **{
                "schemas": {
                    "compute": Mock(**{"services": {"test_service": mock_service}})
                }
            }
        )
    }

    with patch("time.sleep"):
        with patch("time.time") as mock_time:
            # Simulate long time progression - with zero timeouts, this should not raise
            mock_time.side_effect = [0, 100, 200, 300, 400, 500]  # Very long delays

            # Should not raise timeout error
            result = worker._watch_service("test_service", mock_root, config)
            assert result == 0  # Successful completion
