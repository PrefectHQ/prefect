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
)

from prefect.client.schemas import FlowRun
from prefect.server.schemas.core import Flow
from prefect.utilities.dockerutils import get_prefect_image_name


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
    service_name = mock_task_status.started.call_args.args[0]
    assert service_name is not None
    assert "test_flow_run" in service_name


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
        mock_pool_state.state = "ACTIVE" if call_count > 2 else "IDLE"
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
    mock_pool_state.state = "IDLE"
    mock_pool.fetch.return_value = mock_pool_state

    config = await create_job_configuration(
        snowflake_credentials,
        worker_flow_run,
        {"pool_start_timeout_seconds": 2, "service_watch_poll_interval": 1},
    )

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(
            RuntimeError, match="Timed out.*while waiting for compute pool start"
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
        exit_code_val = 0 if state == "DONE" else 1
        mock_service.get_containers.side_effect = (
            lambda s=state, ec=exit_code_val: iter(
                [create_mock_service_container(s, exit_code=ec)]
            )
        )

        async with SPCSWorker(work_pool_name="test-pool") as worker:
            exit_code = worker._watch_service(service_name, config)
            assert exit_code == 0


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
    assert "private_key" in params
    assert params["role"] == "test_role"


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
    def raise_connection_error(*args, **kwargs):
        raise snowflake.connector.errors.DatabaseError("Connection failed")

    monkeypatch.setattr("snowflake.connector.connect", raise_connection_error)

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(
            snowflake.connector.errors.DatabaseError, match="Connection failed"
        ):
            await worker.run(flow_run=worker_flow_run, configuration=config)


async def test_handle_service_creation_sql_error(
    snowflake_credentials, worker_flow_run, mock_snowflake_connection
):
    mock_connect, mock_connection, mock_cursor = mock_snowflake_connection

    mock_cursor.execute.side_effect = snowflake.connector.errors.ProgrammingError(
        "SQL compilation error: Object does not exist"
    )

    config = await create_job_configuration(snowflake_credentials, worker_flow_run)

    async with SPCSWorker(work_pool_name="test-pool") as worker:
        with pytest.raises(snowflake.connector.errors.ProgrammingError):
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

    # Worker should still return successfully, letting Prefect handle the failure
    assert result.status_code == 0


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

    # Worker returns 0, Prefect handles the actual failure
    assert result.status_code == 0


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
