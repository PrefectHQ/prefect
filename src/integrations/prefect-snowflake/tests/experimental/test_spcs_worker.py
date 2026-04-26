import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import snowflake.connector
from prefect_snowflake import SnowflakeCredentials
from prefect_snowflake.experimental.workers.spcs import (
    SPCSServiceTemplateVariables,
    SPCSWorker,
    SPCSWorkerConfiguration,
    SPCSWorkerResult,
    _is_transient_error,
)

from prefect.client.schemas import FlowRun
from prefect.server.schemas.core import Flow
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.workers.base import BaseWorker


def create_mock_snowflake_connection():
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.__enter__ = Mock(return_value=mock_connection)
    mock_connection.__exit__ = Mock(return_value=None)

    mock_connection.host = "test-account.snowflakecomputing.com"
    mock_connection.port = 443
    mock_connection.account = "test-account"
    mock_connection.user = "test-user"
    mock_connection.database = "test_database"
    mock_connection.schema = "test_schema"
    mock_connection.warehouse = "test_warehouse"
    mock_connection.role = "test_role"

    mock_connect = Mock(return_value=mock_connection)

    return mock_connect, mock_connection, mock_cursor


def create_mock_compute_pool(state: str = "ACTIVE"):
    mock_pool = MagicMock()
    mock_pool_state = MagicMock()
    mock_pool_state.state = state
    mock_pool.fetch.return_value = mock_pool_state

    return mock_pool


def create_mock_service_container(service_status: str = "RUNNING", exit_code: int = 0):
    mock_container = MagicMock()
    mock_container.service_status = service_status
    mock_container.instance_id = "test-instance-id"
    mock_container.container_name = "test-container"

    return mock_container


def create_mock_service():
    mock_service = MagicMock()

    # Return a fresh iterator each time get_containers is called
    # Default to DONE so tests don't hang in infinite loops
    mock_service.get_containers.side_effect = lambda: iter(
        [create_mock_service_container("DONE", exit_code=0)]
    )
    mock_service.get_service_logs.return_value = ""

    return mock_service


def create_mock_root(compute_pool_state: str = "ACTIVE", service_status: str = "DONE"):
    mock_root = MagicMock()
    mock_pool = create_mock_compute_pool(compute_pool_state)

    mock_root.compute_pools = {"test_pool": mock_pool}

    mock_service = create_mock_service()

    mock_service.get_containers.side_effect = lambda: iter(
        [create_mock_service_container(service_status)]
    )

    # Setup nested structure for databases.schemas.services and compute pools.
    # Use a defaultdict-like approach so any service name lookup returns the mock service.
    mock_services = MagicMock()
    mock_services.__getitem__ = MagicMock(return_value=mock_service)

    mock_compute_pools = MagicMock()
    mock_compute_pools.__getitem__ = MagicMock(return_value=mock_pool)

    mock_schema = MagicMock()
    mock_schema.services = mock_services
    mock_schema.compute_pools = mock_compute_pools

    mock_schemas = MagicMock()
    mock_schemas.__getitem__ = MagicMock(return_value=mock_schema)

    mock_db = MagicMock()
    mock_db.schemas = mock_schemas

    mock_databases = MagicMock()
    mock_databases.__getitem__ = MagicMock(return_value=mock_db)

    mock_root.databases = mock_databases

    return mock_root


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
        "image_registry": "common.compute.test_registry",
        "snowflake_credentials": snowflake_credentials,
        "compute_pool": "common.compute.test_pool",
        "name": None,
        "service_watch_poll_interval": 1,
        "stream_output": False,
        "pool_start_timeout_seconds": 600,
        "service_start_timeout_seconds": 300,
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
    mock_client = Mock()
    mock_client.read_flow = AsyncMock()
    mock_client.read_flow.return_value = worker_flow

    return mock_client


@pytest.fixture(autouse=True)
def mock_snowflake_connection(monkeypatch):
    mock_connect, mock_connection, mock_cursor = create_mock_snowflake_connection()
    monkeypatch.setattr("snowflake.connector.connect", mock_connect)
    return mock_connect, mock_connection, mock_cursor


@pytest.fixture(autouse=True)
def mock_snowflake_root(monkeypatch):
    mock_root = create_mock_root()

    class MockRoot:
        def __init__(self, connection):
            # Don't call the real __init__
            pass

        def __new__(cls, connection):
            # Return our pre-configured mock instead of creating a new instance.
            return mock_root

    # Patch both where it's imported from and where it's used.
    monkeypatch.setattr("snowflake.core.Root", MockRoot)
    monkeypatch.setattr("prefect_snowflake.experimental.workers.spcs.Root", MockRoot)

    return mock_root


@pytest.fixture
def worker_flow():
    return Flow(id=uuid.uuid4(), name="test-flow")


@pytest.fixture
def worker_flow_run(worker_flow):
    return FlowRun(id=uuid.uuid4(), flow_id=worker_flow.id, name="test-flow-run")


# Tests
def test_spcs_worker_registered_for_cli_discovery():
    assert (
        BaseWorker.get_worker_class_from_type("snowpark-container-service")
        is SPCSWorker
    )


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
            snowflake_credentials=snowflake_credentials,
            compute_pool="common.compute.test_pool",
            image_registry="common.compute.test_registry",
        )


async def test_job_configuration_creation(snowflake_credentials, worker_flow_run):
    config = {
        "snowflake_credentials": snowflake_credentials,
        "image": "my-image",
        "image_registry": "common.compute.test_registry",
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
    assert spcs_job_config.image_registry == "common.compute.test_registry"
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
            image_registry="common.compute.test_registry",
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
    mock_prefect_client,
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


@pytest.mark.parametrize(
    "timeout_seconds,expected_valid",
    [
        (0, True),  # Zero timeout means no timeout
        (1, True),  # Minimum positive timeout
        (3600, True),  # One hour timeout
        (-1, False),  # Negative timeouts should be invalid
    ],
)
async def test_timeout_validation(
    snowflake_credentials, worker_flow_run, timeout_seconds, expected_valid
):
    """Test validation of timeout values."""
    config_overrides = {
        "pool_start_timeout_seconds": timeout_seconds,
        "service_start_timeout_seconds": timeout_seconds,
    }

    if expected_valid:
        # Should not raise an exception
        config = await create_job_configuration(
            snowflake_credentials, worker_flow_run, config_overrides
        )
        assert config.pool_start_timeout_seconds == timeout_seconds
        assert config.service_start_timeout_seconds == timeout_seconds
    else:
        # Should raise a validation error when prepare_for_flow_run is called
        with pytest.raises(ValueError):
            await create_job_configuration(
                snowflake_credentials, worker_flow_run, config_overrides
            )


async def test_worker_run_with_task_status(
    snowflake_credentials,
    worker_flow_run,
):
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    mock_task_status = Mock()

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        await worker.run(
            flow_run=worker_flow_run,
            configuration=config,
            task_status=mock_task_status,
        )

    mock_task_status.started.assert_called_once()
    identifier = mock_task_status.started.call_args.args[0]
    assert identifier is not None
    assert "test_flow_run" in identifier


async def test_create_and_start_service_sql_generation(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection
):
    _, _, mock_cursor = mock_snowflake_connection

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {
            "external_access_integrations": ["integration1", "integration2"],
            "query_warehouse": "test_warehouse",
            "service_comment": "Test comment",
        },
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        service_name = worker._create_and_start_service(
            flow_run=worker_flow_run, configuration=config
        )

    mock_cursor.execute.assert_called_once()
    call_args = mock_cursor.execute.call_args[0]
    sql_cmd = call_args[0]
    params = call_args[1]

    assert "EXECUTE JOB SERVICE" in sql_cmd
    assert "ASYNC = TRUE" in sql_cmd
    assert "IDENTIFIER(%s)" in sql_cmd
    assert "QUERY_WAREHOUSE = IDENTIFIER(%s)" in sql_cmd
    assert "COMMENT = %s" in sql_cmd
    assert "EXTERNAL_ACCESS_INTEGRATIONS = (IDENTIFIER(%s), IDENTIFIER(%s))" in sql_cmd

    assert "test_warehouse" in params
    assert "Test comment" in params
    assert "integration1" in params
    assert "integration2" in params
    assert service_name is not None


async def test_watch_service_waits_for_pool_activation(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_pool = mock_schema.compute_pools["test_pool"]

    call_count = 0

    def pool_fetch_side_effect():
        nonlocal call_count
        call_count += 1
        mock_pool_state = MagicMock()
        mock_pool_state.state = "ACTIVE" if call_count > 2 else "STARTING"
        return mock_pool_state

    mock_pool.fetch.side_effect = pool_fetch_side_effect

    service_name = "test_service"

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"service_watch_poll_interval": 1}
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        exit_code = worker._watch_service(service_name, config)

    assert exit_code == 0
    assert call_count > 2


async def test_watch_service_pool_active(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)
    service_name = "test_service"

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        exit_code = worker._watch_service(service_name, config)

    assert exit_code == 0


async def test_watch_service_pool_timeout(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_pool = mock_schema.compute_pools["test_pool"]
    mock_pool_state = MagicMock()
    mock_pool_state.state = "STARTING"
    mock_pool.fetch.return_value = mock_pool_state

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"pool_start_timeout_seconds": 2, "service_watch_poll_interval": 1},
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(
            RuntimeError, match="Timed out.*while waiting for compute pool"
        ):
            worker._watch_service("test_service", config)


async def test_watch_service_handles_different_states(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    service_name = "test_service"
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_service = mock_schema.services[service_name]

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"service_watch_poll_interval": 1}
    )

    for state in ["DONE", "FAILED", "SUSPENDED", "DELETED", "INTERNAL_ERROR"]:
        expected_exit_code = 0 if state == "DONE" else 1
        mock_service.get_containers.side_effect = lambda s=state: iter(
            [create_mock_service_container(s)]
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)
            assert exit_code == expected_exit_code, (
                f"Expected exit code {expected_exit_code} for state {state}, got {exit_code}"
            )


async def test_watch_service_timeout_on_start(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    from snowflake.core.exceptions import NotFoundError

    service_name = "test_service"
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_service = mock_schema.services[service_name]

    def raise_not_found():
        raise NotFoundError("Service not found")

    mock_service.get_containers.side_effect = raise_not_found

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"service_start_timeout_seconds": 2, "service_watch_poll_interval": 1},
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(
            RuntimeError, match="Timed out.*while waiting for service start"
        ):
            worker._watch_service(service_name, config)


async def test_get_snowflake_connection_parameters_external():
    credentials = SnowflakeCredentials(
        account="test_account",
        user="test_user",
        password="test_password",
        role="test_role",
    )

    config = SPCSWorkerConfiguration(
        snowflake_credentials=credentials,
        compute_pool="common.compute.test_pool",
        image_registry="common.compute.test_registry",
        job_manifest={"spec": {"containers": []}},  # Minimal job manifest
    )

    params = SPCSWorker._get_snowflake_connection_parameters(config)

    assert params["account"] == "test_account"
    assert params["user"] == "test_user"
    assert params["password"] == "test_password"
    assert params["role"] == "test_role"
    assert params["application"] == "Prefect_Snowflake_Collection"
    assert "private_key" not in params


async def test_get_snowflake_connection_parameters_external_private_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    credentials = SnowflakeCredentials(
        account="test_account",
        user="test_user",
        private_key=pem,
        role="test_role",
        authenticator="snowflake_jwt",
    )

    config = SPCSWorkerConfiguration(
        snowflake_credentials=credentials,
        compute_pool="common.compute.test_pool",
        image_registry="common.compute.test_registry",
        job_manifest={"spec": {"containers": []}},
    )

    params = SPCSWorker._get_snowflake_connection_parameters(config)

    assert params["account"] == "test_account"
    assert params["user"] == "test_user"
    assert "private_key" in params
    assert params["role"] == "test_role"
    assert "password" not in params


async def test_get_snowflake_connection_parameters_in_snowflake(monkeypatch, tmp_path):
    monkeypatch.setenv("SNOWFLAKE_HOST", "test-host")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")

    # Create a mock token file
    token_file = tmp_path / "snowflake" / "session" / "token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("test-token")

    # Mock the Path.read_text to return our test token
    with patch("pathlib.Path.read_text", return_value="test-token"):
        credentials = SnowflakeCredentials(
            account="fallback_account",
            user="fallback_user",
            password="fallback_password",
        )

        config = SPCSWorkerConfiguration(
            snowflake_credentials=credentials,
            compute_pool="common.compute.test_pool",
            image_registry="common.compute.test_registry",
            job_manifest={"spec": {"containers": []}},
        )

        params = SPCSWorker._get_snowflake_connection_parameters(config)

    assert params["host"] == "test-host"
    assert params["account"] == "test-account"
    assert params["token"] == "test-token"
    assert params["authenticator"] == "oauth"
    assert params["application"] == "Prefect_Snowflake_Collection"


async def test_get_and_stream_output(snowflake_credentials, worker_flow_run):
    mock_service = create_mock_service()
    mock_container = create_mock_service_container("RUNNING")
    mock_service.get_service_logs.return_value = "2025-10-27T10:00:00.000Z Test log"

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        last_log_time = datetime.datetime(
            2025, 10, 27, 9, 59, 59, tzinfo=datetime.timezone.utc
        )
        new_time = worker._get_and_stream_output(
            mock_service, mock_container, last_log_time
        )

    mock_service.get_service_logs.assert_called_once()
    assert new_time > last_log_time


async def test_stream_output_filters_old_logs():
    worker = SPCSWorker(work_pool_name="test-pool")

    log_content = """2025-10-27T10:00:00.000Z Old log
2025-10-27T10:00:05.000Z New log"""

    last_log_time = datetime.datetime(
        2025, 10, 27, 10, 0, 2, tzinfo=datetime.timezone.utc
    )

    new_time = worker._stream_output(log_content, last_log_time)

    assert new_time >= last_log_time


async def test_job_manifest_env_variables(snowflake_credentials, worker_flow_run):
    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"env": {"CUSTOM_VAR": "custom_value", "ANOTHER_VAR": "another_value"}},
    )

    container = config.job_manifest["spec"]["containers"][0]

    # Should have custom vars plus base environment vars.
    assert "CUSTOM_VAR" in container["env"]
    assert container["env"]["CUSTOM_VAR"] == "custom_value"
    assert "ANOTHER_VAR" in container["env"]
    assert "PREFECT__FLOW_RUN_ID" in container["env"]


async def test_job_manifest_secrets_remove_api_key(
    snowflake_credentials, worker_flow_run
):
    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {
            "secrets": [
                {
                    "envVarName": "PREFECT_API_KEY",
                    "snowflakeSecret": "example_snowflake_secret",
                }
            ],
            "env": {"PREFECT_API_KEY": "should-be-removed"},
        },
    )

    container = config.job_manifest["spec"]["containers"][0]
    assert "PREFECT_API_KEY" not in container["env"]


async def test_job_manifest_command_parsing(snowflake_credentials, worker_flow_run):
    command = "python -m prefect.engine"

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"command": command}
    )

    container = config.job_manifest["spec"]["containers"][0]

    assert isinstance(container["args"], list)
    assert container["args"] == ["python", "-m", "prefect.engine"]


async def test_job_manifest_entrypoint_parsing(snowflake_credentials, worker_flow_run):
    entrypoint = "/opt/prefect/entrypoint.sh"

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"entrypoint": entrypoint}
    )

    container = config.job_manifest["spec"]["containers"][0]

    assert isinstance(container["command"], list)
    assert container["command"] == ["/opt/prefect/entrypoint.sh"]


async def test_job_manifest_memory_limit_defaults(
    snowflake_credentials, worker_flow_run
):
    """Test that memory_limit defaults to memory_request if not specified."""
    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"memory_request": "2G"}
    )

    container = config.job_manifest["spec"]["containers"][0]

    assert container["resources"]["requests"]["memory"] == "2G"
    assert container["resources"]["limits"]["memory"] == "2G"


async def test_job_manifest_omits_empty_resource_values(
    snowflake_credentials, worker_flow_run
):
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    container = config.job_manifest["spec"]["containers"][0]

    assert "cpu" not in container["resources"]["limits"]
    assert "nvidia.com/gpu" not in container["resources"]["requests"]
    assert "nvidia.com/gpu" not in container["resources"]["limits"]


async def test_job_manifest_includes_gpu_count_when_positive(
    snowflake_credentials, worker_flow_run
):
    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"gpu_count": 1}
    )

    container = config.job_manifest["spec"]["containers"][0]

    assert container["resources"]["requests"]["nvidia.com/gpu"] == 1
    assert container["resources"]["limits"]["nvidia.com/gpu"] == 1


async def test_job_manifest_removes_platform_monitor_without_metrics(
    snowflake_credentials, worker_flow_run
):
    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"metrics_groups": []}
    )

    assert "platformMonitor" not in config.job_manifest["spec"]


async def test_job_manifest_volumes_and_mounts(snowflake_credentials, worker_flow_run):
    volumes = [{"name": "data", "source": "/mnt/data"}]
    volume_mounts = [{"name": "data", "mountPath": "/app/data"}]

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"volumes": volumes, "volume_mounts": volume_mounts},
    )

    assert config.volumes == volumes
    assert config.volume_mounts == volume_mounts


@pytest.mark.parametrize(
    "field,value,error_match",
    [
        ("compute_pool", "invalid_format", "compute_pool must be in format"),
        ("image_registry", None, "image_registry is required"),
        ("gpu_count", -1, "gpu_count must be a non-negative integer"),
        ("image", "   ", "image cannot be empty"),
        ("cpu_request", "", "cpu_request cannot be empty"),
        ("memory_request", "", "memory_request cannot be empty"),
        (
            "service_watch_poll_interval",
            0,
            "service_watch_poll_interval must be a positive integer",
        ),
    ],
)
async def test_validation_errors(
    snowflake_credentials, worker_flow_run, field, value, error_match
):
    with pytest.raises(ValueError, match=error_match):
        overrides = {field: value}
        if field == "image_registry":
            config = await create_job_configuration(
                snowflake_credentials, worker_flow_run, overrides, run_prep=False
            )
            config.prepare_for_flow_run(worker_flow_run)
        else:
            await create_job_configuration(
                snowflake_credentials, worker_flow_run, overrides
            )


async def test_handle_snowflake_connection_error(
    snowflake_credentials, worker_flow_run, monkeypatch
):
    monkeypatch.setattr("time.sleep", lambda _: None)

    def raise_connection_error(*args, **kwargs):
        raise snowflake.connector.errors.DatabaseError("Connection failed")

    monkeypatch.setattr("snowflake.connector.connect", raise_connection_error)

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(RuntimeError, match="Failed to connect to Snowflake"):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_handle_service_creation_sql_error(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection, monkeypatch
):
    monkeypatch.setattr("time.sleep", lambda _: None)
    mock_connect, mock_connection, mock_cursor = mock_snowflake_connection

    mock_cursor.execute.side_effect = snowflake.connector.errors.ProgrammingError(
        "SQL compilation error: Object does not exist"
    )

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(RuntimeError, match="Verify that the compute pool"):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_service_enters_failed_state(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    service_name = "test_service"
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_service = mock_schema.services[service_name]

    mock_service.get_containers.side_effect = lambda: iter(
        [create_mock_service_container("FAILED", exit_code=1)]
    )

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"service_watch_poll_interval": 1}
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        result = await worker.run(flow_run=worker_flow_run, configuration=config)

    assert result.status_code == 1


async def test_service_enters_internal_error_state(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    service_name = "test_service"
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_service = mock_schema.services[service_name]

    mock_service.get_containers.side_effect = lambda: iter(
        [create_mock_service_container("INTERNAL_ERROR", exit_code=1)]
    )

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"service_watch_poll_interval": 1}
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        result = await worker.run(flow_run=worker_flow_run, configuration=config)

    assert result.status_code == 1


async def test_connection_lost_during_monitoring(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    service_name = "test_service"
    mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
    mock_service = mock_schema.services[service_name]

    call_count = [0]

    def get_containers_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return iter([create_mock_service_container("RUNNING")])
        else:
            raise snowflake.connector.errors.DatabaseError("Connection lost")

    mock_service.get_containers.side_effect = get_containers_side_effect

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"service_watch_poll_interval": 1}
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(
            snowflake.connector.errors.DatabaseError, match="Connection lost"
        ):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_task_status_not_provided(
    snowflake_credentials,
    worker_flow_run,
):
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        result = await worker.run(
            flow_run=worker_flow_run,
            configuration=config,
            task_status=None,
        )

    assert result.status_code == 0
    assert result.identifier is not None


async def test_worker_result_contains_identifier(
    snowflake_credentials,
    worker_flow_run,
):
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        result = await worker.run(flow_run=worker_flow_run, configuration=config)

    assert isinstance(result, SPCSWorkerResult)
    assert result.identifier is not None
    assert isinstance(result.identifier, str)
    assert len(result.identifier) > 0
    # Identifier should contain the flow run ID (with underscores instead of hyphens)
    assert str(worker_flow_run.id).replace("-", "_") in result.identifier


async def test_worker_configuration_from_template_and_values(snowflake_credentials):
    template = SPCSWorker.get_default_base_job_template()

    values = {
        "snowflake_credentials": snowflake_credentials,
        "compute_pool": "common.compute.test_pool",
        "image_registry": "common.compute.test_registry",
        "image": "custom-image:latest",
        "cpu_request": "2",
        "memory_request": "4G",
    }

    config = await SPCSWorkerConfiguration.from_template_and_values(template, values)

    assert config.image == "custom-image:latest"
    assert config.cpu_request == "2"
    assert config.memory_request == "4G"
    assert config.compute_pool == "common.compute.test_pool"


async def test_multiple_concurrent_runs(snowflake_credentials, worker_flow):
    flow_runs = [
        FlowRun(id=uuid.uuid4(), flow_id=worker_flow.id, name=f"test-flow-run-{i}")
        for i in range(3)
    ]

    configs = [
        await create_job_configuration(snowflake_credentials, fr) for fr in flow_runs
    ]

    results = []
    async with SPCSWorker(work_pool_name="test-pool") as worker:
        # Submit all runs sequentially
        for fr, config in zip(flow_runs, configs):
            result = await worker.run(fr, config)
            results.append(result)

    assert len(results) == 3
    for result in results:
        assert result.status_code == 0


async def test_worker_propagates_environment_variables(
    snowflake_credentials,
    worker_flow_run,
):
    custom_env = {
        "CUSTOM_VAR_1": "value1",
        "CUSTOM_VAR_2": "value2",
        "PREFECT_LOGGING_LEVEL": "DEBUG",
    }

    config = await create_job_configuration(
        snowflake_credentials, worker_flow_run, {"env": custom_env}
    )

    container = config.job_manifest["spec"]["containers"][0]

    # All custom vars should be present
    for key, value in custom_env.items():
        assert key in container["env"]
        assert container["env"][key] == value

    # Base Prefect env vars should also be present
    assert "PREFECT__FLOW_RUN_ID" in container["env"]


async def test_worker_with_custom_timeouts(
    snowflake_credentials,
    worker_flow_run,
):
    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {
            "pool_start_timeout_seconds": 120,
            "service_start_timeout_seconds": 60,
            "service_watch_poll_interval": 2,
        },
    )

    assert config.pool_start_timeout_seconds == 120
    assert config.service_start_timeout_seconds == 60
    assert config.service_watch_poll_interval == 2

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        result = await worker.run(flow_run=worker_flow_run, configuration=config)

    assert result.status_code == 0


async def test_sql_injection_protection_with_malicious_inputs(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection
):
    _, _, mock_cursor = mock_snowflake_connection

    malicious_warehouse = "warehouse'; DROP TABLE users; --"
    malicious_comment = "comment'; DELETE FROM services; --"
    malicious_eai = ["eai1'; GRANT ALL PRIVILEGES; --", "eai2'; DROP DATABASE; --"]

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {
            "query_warehouse": malicious_warehouse,
            "service_comment": malicious_comment,
            "external_access_integrations": malicious_eai,
        },
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        worker._create_and_start_service(flow_run=worker_flow_run, configuration=config)

    mock_cursor.execute.assert_called_once()
    sql_cmd, params = mock_cursor.execute.call_args[0]

    semicolon_count = sql_cmd.count(";")
    assert semicolon_count == 1, (
        f"Expected exactly 1 semicolon in SQL, found {semicolon_count}"
    )

    assert "IDENTIFIER(%s)" in sql_cmd
    assert "COMMENT = %s" in sql_cmd

    assert malicious_warehouse in params
    assert malicious_comment in params
    assert malicious_eai[0] in params
    assert malicious_eai[1] in params

    assert "DROP TABLE" not in sql_cmd
    assert "DELETE FROM" not in sql_cmd
    assert "GRANT ALL" not in sql_cmd
    assert "DROP DATABASE" not in sql_cmd


async def test_sql_uses_bind_parameters_for_all_user_inputs(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection
):
    _, _, mock_cursor = mock_snowflake_connection

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {
            "external_access_integrations": ["eai1", "eai2", "eai3"],
            "query_warehouse": "my_warehouse",
            "service_comment": "My service comment",
        },
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        worker._create_and_start_service(flow_run=worker_flow_run, configuration=config)

    mock_cursor.execute.assert_called_once()
    call_args = mock_cursor.execute.call_args[0]

    assert len(call_args) == 2, "execute should be called with SQL and params"

    sql_cmd = call_args[0]
    params = call_args[1]

    assert "IDENTIFIER(%s)" in sql_cmd
    assert "COMMENT = %s" in sql_cmd
    assert "FROM SPECIFICATION %s;" in sql_cmd

    assert isinstance(params, list)
    assert len(params) >= 6

    assert "my_warehouse" in params
    assert "My service comment" in params
    assert "eai1" in params
    assert "eai2" in params
    assert "eai3" in params


# kill_infrastructure / cancellation tests


async def test_kill_infrastructure_drops_service(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    mock_schema = mock_snowflake_root.databases["mydb"].schemas["myschema"]
    mock_service = mock_schema.services["test_service"]

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        await worker.kill_infrastructure(
            infrastructure_pid="test_service",
            configuration=config,
        )

    mock_service.drop.assert_called_once()


async def test_kill_infrastructure_raises_not_found(
    snowflake_credentials,
    worker_flow_run,
    mock_snowflake_root,
):
    from snowflake.core.exceptions import NotFoundError

    from prefect.exceptions import InfrastructureNotFound

    mock_schema = mock_snowflake_root.databases["mydb"].schemas["myschema"]
    mock_service = mock_schema.services["gone_service"]
    mock_service.drop.side_effect = NotFoundError("not found")

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(InfrastructureNotFound, match="not found"):
            await worker.kill_infrastructure(
                infrastructure_pid="gone_service",
                configuration=config,
            )


# Retry and error wrapping tests


async def test_create_service_retries_on_transient_failure(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection, monkeypatch
):
    """Test that service creation retries on transient Snowflake errors."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    _, _, mock_cursor = mock_snowflake_connection

    call_count = [0]

    def execute_with_transient_failure(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise snowflake.connector.errors.OperationalError("Connection reset")

    mock_cursor.execute.side_effect = execute_with_transient_failure

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        service_name = worker._create_and_start_service(
            flow_run=worker_flow_run, configuration=config
        )

    assert call_count[0] == 2
    assert service_name is not None


async def test_run_wraps_object_not_found_error(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection, monkeypatch
):
    """Test that ProgrammingError with 'does not exist' is wrapped with actionable message."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    _, _, mock_cursor = mock_snowflake_connection
    mock_cursor.execute.side_effect = snowflake.connector.errors.ProgrammingError(
        "SQL compilation error: Object 'BAD_POOL' does not exist"
    )

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(RuntimeError, match="Verify that the compute pool"):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_run_wraps_insufficient_privileges_error(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection, monkeypatch
):
    """Test that ProgrammingError with 'insufficient privileges' is wrapped."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    _, _, mock_cursor = mock_snowflake_connection
    mock_cursor.execute.side_effect = snowflake.connector.errors.ProgrammingError(
        "Insufficient privileges to operate on compute pool"
    )

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(RuntimeError, match="insufficient privileges"):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_run_wraps_connection_error_with_context(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection, monkeypatch
):
    """Test that DatabaseError with connection issues is wrapped."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    _, _, mock_cursor = mock_snowflake_connection
    mock_cursor.execute.side_effect = snowflake.connector.errors.DatabaseError(
        "Connection timeout after 30 seconds"
    )

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(RuntimeError, match="Check your network connectivity"):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_initiate_run_returns_identifier(snowflake_credentials, worker_flow_run):
    """Test that _initiate_run returns the infrastructure identifier."""
    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        identifier = await worker._initiate_run(
            flow_run=worker_flow_run, configuration=config
        )

    assert identifier is not None
    assert "test_flow_run" in identifier


async def test_initiate_run_wraps_errors(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection, monkeypatch
):
    """Test that _initiate_run wraps errors like run() does."""
    monkeypatch.setattr("time.sleep", lambda _: None)
    _, _, mock_cursor = mock_snowflake_connection
    mock_cursor.execute.side_effect = snowflake.connector.errors.ProgrammingError(
        "Object 'MISSING' does not exist"
    )

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(RuntimeError, match="Verify that the compute pool"):
            await worker._initiate_run(flow_run=worker_flow_run, configuration=config)


# ---- Error classification tests ----


class TestErrorClassification:
    """Tests for _is_transient_error and structured error handling."""

    def test_operational_error_is_transient(self):
        exc = snowflake.connector.errors.OperationalError("Connection reset by peer")
        assert _is_transient_error(exc) is True

    def test_interface_error_is_transient(self):
        exc = snowflake.connector.errors.InterfaceError("Failed to connect")
        assert _is_transient_error(exc) is True

    def test_database_error_with_connection_keyword_is_transient(self):
        exc = snowflake.connector.errors.DatabaseError("Connection lost during query")
        assert _is_transient_error(exc) is True

    def test_database_error_with_timeout_keyword_is_transient(self):
        exc = snowflake.connector.errors.DatabaseError("Timeout after 30 seconds")
        assert _is_transient_error(exc) is True

    def test_database_error_with_reset_keyword_is_transient(self):
        exc = snowflake.connector.errors.DatabaseError("Connection reset")
        assert _is_transient_error(exc) is True

    def test_database_error_with_network_keyword_is_transient(self):
        exc = snowflake.connector.errors.DatabaseError("Network is unreachable")
        assert _is_transient_error(exc) is True

    def test_programming_error_is_permanent(self):
        exc = snowflake.connector.errors.ProgrammingError("SQL compilation error")
        assert _is_transient_error(exc) is False

    def test_database_error_without_transient_keywords_is_permanent(self):
        exc = snowflake.connector.errors.DatabaseError(
            "Insufficient privileges to execute"
        )
        assert _is_transient_error(exc) is False

    def test_generic_exception_is_permanent(self):
        exc = ValueError("Something went wrong")
        assert _is_transient_error(exc) is False

    def test_runtime_error_is_permanent(self):
        exc = RuntimeError("Unexpected failure")
        assert _is_transient_error(exc) is False


class TestRetryBehavior:
    """Tests for retry decorator with error classification."""

    async def test_permanent_error_not_retried(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_connection,
        monkeypatch,
    ):
        """Permanent errors should fail immediately without retrying."""
        monkeypatch.setattr("time.sleep", lambda _: None)
        _, _, mock_cursor = mock_snowflake_connection

        mock_cursor.execute.side_effect = snowflake.connector.errors.ProgrammingError(
            "SQL compilation error: Object does not exist"
        )

        config = await create_job_configuration(snowflake_credentials, worker_flow_run)

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            with pytest.raises(RuntimeError, match="Verify that the compute pool"):
                await worker.run(flow_run=worker_flow_run, configuration=config)

        # Permanent error: should be called exactly once (no retries)
        assert mock_cursor.execute.call_count == 1

    async def test_transient_error_retried_then_succeeds(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_connection,
        monkeypatch,
    ):
        """Transient errors should be retried up to MAX_CREATE_SERVICE_ATTEMPTS."""
        monkeypatch.setattr("time.sleep", lambda _: None)
        _, _, mock_cursor = mock_snowflake_connection

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise snowflake.connector.errors.OperationalError(
                    "Connection reset by peer"
                )

        mock_cursor.execute.side_effect = execute_side_effect

        config = await create_job_configuration(snowflake_credentials, worker_flow_run)

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            result = await worker.run(flow_run=worker_flow_run, configuration=config)

        assert result.status_code == 0
        assert call_count[0] == 2  # First call fails, second succeeds

    async def test_transient_error_exhausts_retries(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_connection,
        monkeypatch,
    ):
        """Transient errors that persist should exhaust all retry attempts."""
        monkeypatch.setattr("time.sleep", lambda _: None)
        _, _, mock_cursor = mock_snowflake_connection

        mock_cursor.execute.side_effect = snowflake.connector.errors.OperationalError(
            "Connection reset by peer"
        )

        config = await create_job_configuration(snowflake_credentials, worker_flow_run)

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            # OperationalError is a DatabaseError subclass with "connection" in the message,
            # so _report_service_creation_failure wraps it as RuntimeError
            with pytest.raises(RuntimeError, match="Check your network connectivity"):
                await worker.run(flow_run=worker_flow_run, configuration=config)

        # Should have been called MAX_CREATE_SERVICE_ATTEMPTS times
        assert mock_cursor.execute.call_count == 3


# ---- Compute pool validation tests ----


class TestComputePoolValidation:
    """Tests for pre-run compute pool state validation."""

    async def test_suspended_pool_fails_fast(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """A SUSPENDED compute pool should fail immediately, not wait for timeout."""
        mock_pool = mock_snowflake_root.compute_pools["test_pool"]
        mock_pool_state = MagicMock()
        mock_pool_state.state = "SUSPENDED"
        mock_pool.fetch.return_value = mock_pool_state

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            with pytest.raises(RuntimeError, match="SUSPENDED.*Resume it"):
                worker._watch_service("test_service", config)

        # Should fail after a single check, not loop until timeout
        assert mock_pool.fetch.call_count == 1

    async def test_idle_pool_is_ready(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """An IDLE pool is ready — the worker should not wait for ACTIVE."""
        mock_pool = mock_snowflake_root.compute_pools["test_pool"]

        mock_state = MagicMock()
        mock_state.state = "IDLE"
        mock_pool.fetch.return_value = mock_state

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service("test_service", config)

        assert exit_code == 0
        assert mock_pool.fetch.call_count == 1

    async def test_resizing_pool_waits_for_active(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """A RESIZING pool should be waited on until it becomes ACTIVE."""
        mock_pool = mock_snowflake_root.compute_pools["test_pool"]

        states = iter(["RESIZING", "ACTIVE"])

        def fetch_side_effect():
            state = MagicMock()
            state.state = next(states)
            return state

        mock_pool.fetch.side_effect = fetch_side_effect

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service("test_service", config)

        assert exit_code == 0


# ---- Grace seconds tests ----


class TestGraceSeconds:
    """Tests for kill_infrastructure grace_seconds handling."""

    async def test_default_grace_seconds_no_warning(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
        caplog,
    ):
        """Default grace_seconds (30) should not produce a warning."""
        config = await create_job_configuration(snowflake_credentials, worker_flow_run)

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            await worker.kill_infrastructure(
                infrastructure_pid="test_service",
                configuration=config,
                grace_seconds=30,
            )

        assert "grace_seconds=" not in caplog.text

    async def test_custom_grace_seconds_logs_info(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
        caplog,
    ):
        """Non-default grace_seconds should log an info message."""
        import logging

        config = await create_job_configuration(snowflake_credentials, worker_flow_run)

        with caplog.at_level(logging.INFO):
            async with SPCSWorker(work_pool_name="test-pool") as worker:
                await worker.kill_infrastructure(
                    infrastructure_pid="test_service",
                    configuration=config,
                    grace_seconds=60,
                )

        assert "grace_seconds=60 ignored" in caplog.text
        assert "built-in 30-second SIGTERM" in caplog.text


# ---- Environment variable tests ----


class TestEnvironmentVariables:
    """Tests for environment variable handling and inheritance."""

    async def test_base_environment_variables_present(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """Base Prefect environment variables should always be set."""
        config = await create_job_configuration(
            snowflake_credentials, worker_flow_run, {"env": {}}
        )
        container = config.job_manifest["spec"]["containers"][0]

        assert "PREFECT__FLOW_RUN_ID" in container["env"]
        assert container["env"]["PREFECT__FLOW_RUN_ID"] == str(worker_flow_run.id)

    async def test_custom_env_merged_with_base(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """Custom environment variables should be merged with base variables."""
        custom_env = {"MY_VAR": "my_value", "ANOTHER": "value2"}
        config = await create_job_configuration(
            snowflake_credentials, worker_flow_run, {"env": custom_env}
        )
        container = config.job_manifest["spec"]["containers"][0]

        # Custom vars present
        assert container["env"]["MY_VAR"] == "my_value"
        assert container["env"]["ANOTHER"] == "value2"
        # Base vars also present
        assert "PREFECT__FLOW_RUN_ID" in container["env"]

    async def test_custom_env_overrides_base(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """Custom env vars should override base vars with the same key."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"env": {"PREFECT__FLOW_RUN_ID": "custom-override"}},
        )
        container = config.job_manifest["spec"]["containers"][0]

        assert container["env"]["PREFECT__FLOW_RUN_ID"] == "custom-override"

    async def test_api_auth_string_removed_with_secret(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """PREFECT_API_AUTH_STRING should be removed from env when a matching secret exists."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {
                "secrets": [
                    {
                        "envVarName": "PREFECT_API_AUTH_STRING",
                        "snowflakeSecret": "auth_secret",
                    }
                ],
                "env": {"PREFECT_API_AUTH_STRING": "should-be-removed"},
            },
        )
        container = config.job_manifest["spec"]["containers"][0]
        assert "PREFECT_API_AUTH_STRING" not in container["env"]

    async def test_api_key_kept_without_matching_secret(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """PREFECT_API_KEY should be kept if no matching secret is configured."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {
                "secrets": [{"envVarName": "OTHER_SECRET", "snowflakeSecret": "other"}],
                "env": {"PREFECT_API_KEY": "keep-this"},
            },
        )
        container = config.job_manifest["spec"]["containers"][0]
        assert container["env"]["PREFECT_API_KEY"] == "keep-this"


# ---- Log streaming tests ----


class TestLogStreaming:
    """Tests for log streaming edge cases."""

    async def test_stream_output_empty_string(self):
        """Empty log content should return the original last_log_time."""
        worker = SPCSWorker(work_pool_name="test-pool")
        last_time = datetime.datetime(
            2025, 10, 27, 10, 0, 0, tzinfo=datetime.timezone.utc
        )
        result = worker._stream_output("", last_time)
        assert result == last_time

    async def test_stream_output_only_whitespace(self):
        """Whitespace-only lines should be skipped."""
        worker = SPCSWorker(work_pool_name="test-pool")
        last_time = datetime.datetime(
            2025, 10, 27, 10, 0, 0, tzinfo=datetime.timezone.utc
        )
        result = worker._stream_output("   \n\n  \n", last_time)
        assert result == last_time

    async def test_stream_output_malformed_timestamp(self):
        """Lines with unparsable timestamps should be skipped gracefully."""
        worker = SPCSWorker(work_pool_name="test-pool")
        last_time = datetime.datetime(
            2025, 10, 27, 10, 0, 0, tzinfo=datetime.timezone.utc
        )
        result = worker._stream_output("not-a-timestamp Some log message", last_time)
        assert result == last_time

    async def test_stream_output_filters_old_and_keeps_new(self, capsys):
        """Only lines newer than last_log_time should be streamed."""
        worker = SPCSWorker(work_pool_name="test-pool")
        last_time = datetime.datetime(
            2025, 10, 27, 10, 0, 2, tzinfo=datetime.timezone.utc
        )

        log_content = (
            "2025-10-27T10:00:00.000Z Old log line\n"
            "2025-10-27T10:00:01.000Z Also old\n"
            "2025-10-27T10:00:05.000Z New log line\n"
            "2025-10-27T10:00:10.000Z Also new"
        )

        result = worker._stream_output(log_content, last_time)

        captured = capsys.readouterr()
        assert "Old log line" not in captured.err
        assert "Also old" not in captured.err
        assert "New log line" in captured.err
        assert "Also new" in captured.err
        assert result == datetime.datetime(
            2025, 10, 27, 10, 0, 10, tzinfo=datetime.timezone.utc
        )

    async def test_stream_output_during_running_state(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """Log streaming should work when service is in RUNNING state."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        call_count = [0]

        def get_containers_side_effect():
            call_count[0] += 1
            if call_count[0] <= 2:
                return iter([create_mock_service_container("RUNNING")])
            return iter([create_mock_service_container("DONE")])

        mock_service.get_containers.side_effect = get_containers_side_effect
        mock_service.get_service_logs.return_value = (
            "2025-10-27T10:00:05.000Z Running flow..."
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": True},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)

        assert exit_code == 0
        assert mock_service.get_service_logs.call_count >= 1


# ---- Service lifecycle tests ----


class TestServiceLifecycle:
    """Tests for full service lifecycle: create → monitor → complete."""

    async def test_running_then_done_returns_zero(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """Service that transitions RUNNING → DONE should return exit code 0."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        call_count = [0]

        def get_containers_side_effect():
            call_count[0] += 1
            if call_count[0] <= 3:
                return iter([create_mock_service_container("RUNNING")])
            return iter([create_mock_service_container("DONE")])

        mock_service.get_containers.side_effect = get_containers_side_effect

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            result = await worker.run(flow_run=worker_flow_run, configuration=config)

        assert result.status_code == 0
        assert call_count[0] > 1

    async def test_pending_then_running_then_done(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """Service that goes PENDING → RUNNING → DONE should succeed."""
        from snowflake.core.exceptions import NotFoundError

        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        call_count = [0]

        def get_containers_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise NotFoundError("Not ready yet")
            elif call_count[0] <= 3:
                return iter([create_mock_service_container("RUNNING")])
            return iter([create_mock_service_container("DONE")])

        mock_service.get_containers.side_effect = get_containers_side_effect

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            result = await worker.run(flow_run=worker_flow_run, configuration=config)

        assert result.status_code == 0

    async def test_suspending_returns_failure(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """Service that enters SUSPENDING state should return non-zero."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("SUSPENDING")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            result = await worker.run(flow_run=worker_flow_run, configuration=config)

        assert result.status_code == 1

    async def test_deleting_returns_failure(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """Service that enters DELETING state should return non-zero."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("DELETING")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            result = await worker.run(flow_run=worker_flow_run, configuration=config)

        assert result.status_code == 1


# ---- Slugify edge case tests ----


class TestSlugify:
    """Tests for service name slugification edge cases."""

    def test_empty_service_name_returns_none(self):
        result = SPCSWorker._slugify_service_name("", uuid.uuid4())
        assert result is None

    def test_none_service_name_returns_none(self):
        result = SPCSWorker._slugify_service_name(None, uuid.uuid4())
        assert result is None

    def test_special_characters_cleaned(self):
        flow_run_id = uuid.uuid4()
        result = SPCSWorker._slugify_service_name("My Flow! @#$% Name", flow_run_id)
        assert result is not None
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result
        assert result.endswith(str(flow_run_id).replace("-", "_"))

    def test_unicode_characters_cleaned(self):
        flow_run_id = uuid.uuid4()
        result = SPCSWorker._slugify_service_name("Fluß Wörk", flow_run_id)
        assert result is not None
        assert all(c.isalnum() or c in ("-", "_") for c in result)

    def test_very_long_name_truncated_to_63(self):
        flow_run_id = uuid.uuid4()
        long_name = "A" * 200
        result = SPCSWorker._slugify_service_name(long_name, flow_run_id)
        assert len(result) <= 63

    def test_underscores_in_name_preserved(self):
        flow_run_id = uuid.uuid4()
        result = SPCSWorker._slugify_service_name("my_flow_name", flow_run_id)
        assert result is not None
        assert "my_flow_name" in result


# ---- Concurrent run isolation tests ----


class TestConcurrentRunIsolation:
    """Tests for concurrent runs producing unique service names."""

    async def test_unique_service_names_per_flow_run(
        self,
        snowflake_credentials,
        worker_flow,
    ):
        """Each flow run should get a unique service name."""
        flow_runs = [
            FlowRun(
                id=uuid.uuid4(),
                flow_id=worker_flow.id,
                name=f"test-flow-run-{i}",
            )
            for i in range(5)
        ]

        names = set()
        for fr in flow_runs:
            name = SPCSWorker._slugify_service_name("test-flow", fr.id)
            names.add(name)

        assert len(names) == 5

    async def test_same_flow_different_runs_get_different_names(
        self,
        snowflake_credentials,
        worker_flow,
    ):
        """Same flow name but different run IDs should produce different service names."""
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()

        name1 = SPCSWorker._slugify_service_name("identical-flow", id1)
        name2 = SPCSWorker._slugify_service_name("identical-flow", id2)

        assert name1 != name2
        assert name1.startswith("identical_flow_")
        assert name2.startswith("identical_flow_")


# ---- Configuration edge case tests ----


class TestConfigurationEdgeCases:
    """Tests for configuration validation edge cases."""

    async def test_compute_pool_missing_raises(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """Missing compute_pool should raise during prepare_for_flow_run."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"compute_pool": None},
            run_prep=False,
        )
        with pytest.raises(ValueError, match="compute_pool is required"):
            config.prepare_for_flow_run(worker_flow_run)

    async def test_cpu_limit_empty_string_raises(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """Empty string cpu_limit should raise."""
        with pytest.raises(ValueError, match="cpu_limit cannot be empty"):
            await create_job_configuration(
                snowflake_credentials,
                worker_flow_run,
                {"cpu_limit": "  "},
            )

    async def test_memory_limit_empty_string_raises(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """Empty string memory_limit should raise."""
        with pytest.raises(ValueError, match="memory_limit cannot be empty"):
            await create_job_configuration(
                snowflake_credentials,
                worker_flow_run,
                {"memory_limit": "  "},
            )

    async def test_gpu_count_zero_is_valid(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """gpu_count=0 should be valid (explicitly no GPUs)."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"gpu_count": 0},
        )
        assert config.gpu_count == 0

    async def test_explicit_memory_limit_used(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """When memory_limit is explicitly set, it should be used instead of memory_request."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"memory_request": "2G", "memory_limit": "4G"},
        )
        container = config.job_manifest["spec"]["containers"][0]
        assert container["resources"]["requests"]["memory"] == "2G"
        assert container["resources"]["limits"]["memory"] == "4G"

    async def test_metrics_groups_present_keeps_platform_monitor(
        self,
        snowflake_credentials,
        worker_flow_run,
    ):
        """When metrics_groups is non-empty, platformMonitor should be kept."""
        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"metrics_groups": ["system.all"]},
        )
        assert "platformMonitor" in config.job_manifest["spec"]

    async def test_no_external_access_integrations_omits_clause(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_connection,
    ):
        """When no EAIs are configured, the SQL should not include the clause."""
        _, _, mock_cursor = mock_snowflake_connection

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"external_access_integrations": []},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            worker._create_and_start_service(
                flow_run=worker_flow_run, configuration=config
            )

        sql_cmd = mock_cursor.execute.call_args[0][0]
        assert "EXTERNAL_ACCESS_INTEGRATIONS" not in sql_cmd

    async def test_no_query_warehouse_omits_clause(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_connection,
    ):
        """When no query_warehouse is configured, the SQL should not include it."""
        _, _, mock_cursor = mock_snowflake_connection

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"query_warehouse": None},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            worker._create_and_start_service(
                flow_run=worker_flow_run, configuration=config
            )

        sql_cmd = mock_cursor.execute.call_args[0][0]
        assert "QUERY_WAREHOUSE" not in sql_cmd

    async def test_no_service_comment_omits_clause(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_connection,
    ):
        """When no service_comment is configured, the SQL should not include it."""
        _, _, mock_cursor = mock_snowflake_connection

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_comment": None},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            worker._create_and_start_service(
                flow_run=worker_flow_run, configuration=config
            )

        sql_cmd = mock_cursor.execute.call_args[0][0]
        assert "COMMENT" not in sql_cmd


# ---- Worker type and metadata tests ----


class TestWorkerMetadata:
    """Tests for worker type, description, and configuration metadata."""

    def test_worker_type(self):
        assert SPCSWorker.type == "snowpark-container-service"

    def test_worker_has_description(self):
        assert SPCSWorker._description is not None
        assert len(SPCSWorker._description) > 0

    def test_default_base_job_template_structure(self):
        template = SPCSWorker.get_default_base_job_template()
        assert "job_configuration" in template
        assert "variables" in template

    def test_worker_result_type(self):
        result = SPCSWorkerResult(status_code=0, identifier="svc")
        assert result.status_code == 0
        assert result.identifier == "svc"

    def test_worker_result_failure(self):
        result = SPCSWorkerResult(status_code=1, identifier="svc")
        assert result.status_code == 1


# ---- Crash log forwarding and diagnostics tests ----


class TestCrashLogForwarding:
    """Tests for crash log forwarding when stream_output=False."""

    async def test_crash_logs_forwarded_on_failure_without_stream_output(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """When stream_output=False and service FAILED, logs should still be fetched."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("FAILED")]
        )
        mock_service.get_service_logs.return_value = (
            "2025-10-27T10:00:05.000Z Error: container crashed"
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)

        assert exit_code == 1
        assert mock_service.get_service_logs.call_count >= 1

    async def test_crash_logs_forwarded_on_internal_error_without_stream_output(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """When stream_output=False and service hits INTERNAL_ERROR, logs should still be fetched."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("INTERNAL_ERROR")]
        )
        mock_service.get_service_logs.return_value = (
            "2025-10-27T10:00:05.000Z Internal error occurred"
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)

        assert exit_code == 1
        assert mock_service.get_service_logs.call_count >= 1

    async def test_crash_log_retrieval_failure_does_not_raise(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """If crash log retrieval fails, it should be swallowed (not crash the worker)."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("FAILED")]
        )
        mock_service.get_service_logs.side_effect = Exception("Log retrieval failed")

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)

        assert exit_code == 1

    async def test_no_crash_logs_for_non_failure_states(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """DONE state without stream_output should NOT fetch logs."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("DONE")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)

        assert exit_code == 0
        assert mock_service.get_service_logs.call_count == 0


class TestFailureDiagnostics:
    """Tests for structured failure diagnostic messages."""

    async def test_failed_service_logs_error_with_event_table_hint(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
        caplog,
    ):
        """FAILED status should log an error with event table query hint."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("FAILED")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            import logging

            with caplog.at_level(logging.ERROR):
                worker._watch_service(service_name, config)

        assert (
            "event table" in caplog.text.lower() or "event_table" in caplog.text.lower()
        )

    async def test_internal_error_logs_retry_guidance(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
        caplog,
    ):
        """INTERNAL_ERROR should log guidance about retrying."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("INTERNAL_ERROR")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            import logging

            with caplog.at_level(logging.ERROR):
                worker._watch_service(service_name, config)

        assert "transient" in caplog.text.lower() or "retry" in caplog.text.lower()

    async def test_suspended_service_logs_resume_guidance(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
        caplog,
    ):
        """SUSPENDED status should log guidance about resuming the compute pool."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("SUSPENDED")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            import logging

            with caplog.at_level(logging.WARNING):
                worker._watch_service(service_name, config)

        assert "resume" in caplog.text.lower()

    async def test_deleted_service_logs_cancellation_hint(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
        caplog,
    ):
        """DELETED status should log a hint about external cancellation."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]

        mock_service.get_containers.side_effect = lambda: iter(
            [create_mock_service_container("DELETED")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1, "stream_output": False},
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            import logging

            with caplog.at_level(logging.WARNING):
                worker._watch_service(service_name, config)

        assert "cancel" in caplog.text.lower() or "deleted" in caplog.text.lower()


class TestInfrastructurePending:
    """Tests for InfrastructurePending state proposal during run()."""

    async def test_run_proposes_infrastructure_pending(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """run() should propose InfrastructurePending after creating the service."""

        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]
        mock_service.get_containers.return_value = iter(
            [create_mock_service_container("DONE")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        mock_client = AsyncMock()
        mock_client.set_flow_run_state = AsyncMock(
            return_value=MagicMock(status=MagicMock(value="ACCEPT"))
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect_snowflake.experimental.workers.spcs.prefect"
        ) as mock_prefect:
            mock_prefect.get_client.return_value = mock_ctx
            with patch(
                "prefect_snowflake.experimental.workers.spcs.propose_state",
                new_callable=AsyncMock,
            ) as mock_propose:
                async with SPCSWorker(work_pool_name="test-pool") as worker:
                    result = await worker.run(
                        flow_run=worker_flow_run, configuration=config
                    )

        assert result.status_code == 0
        mock_propose.assert_called_once()
        call_kwargs = mock_propose.call_args
        proposed_state = call_kwargs.kwargs.get("state") or call_kwargs[1].get(
            "state", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        )
        assert proposed_state is not None
        assert proposed_state.name == "InfrastructurePending"
        proposed_flow_run_id = call_kwargs.kwargs.get("flow_run_id") or call_kwargs[
            1
        ].get("flow_run_id")
        assert proposed_flow_run_id == worker_flow_run.id

    async def test_run_continues_if_pending_proposal_fails(
        self,
        snowflake_credentials,
        worker_flow_run,
        mock_snowflake_root,
    ):
        """run() should still complete even if InfrastructurePending proposal fails."""
        service_name = "test_service"
        mock_schema = mock_snowflake_root.databases["common"].schemas["compute"]
        mock_service = mock_schema.services[service_name]
        mock_service.get_containers.return_value = iter(
            [create_mock_service_container("DONE")]
        )

        config = await create_job_configuration(
            snowflake_credentials,
            worker_flow_run,
            {"service_watch_poll_interval": 1},
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("No server"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect_snowflake.experimental.workers.spcs.prefect"
        ) as mock_prefect:
            mock_prefect.get_client.return_value = mock_ctx

            async with SPCSWorker(work_pool_name="test-pool") as worker:
                result = await worker.run(
                    flow_run=worker_flow_run, configuration=config
                )

        assert result.status_code == 0
