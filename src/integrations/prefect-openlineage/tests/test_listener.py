"""
Unit tests for PrefectOpenLineageListener module.

Tests cover event processing, Prefect API interactions, and OpenLineage event creation.
"""

import ast
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json
import pytest

from prefect_openlineage.listener import PrefectOpenLineageListener
from prefect_openlineage.adapter import PrefectOpenLineageAdapter
from prefect.events.schemas.events import Event
from test_events import FLOW_START_EVENT, FLOW_COMPLETE_EVENT, TASK_START_EVENT, TASK_COMPLETE_EVENT


# ========== Fixtures ==========


@pytest.fixture
def mock_prefect_client():
    """Create a mock Prefect API client."""
    client = AsyncMock()
    client._client = AsyncMock()
    return client


@pytest.fixture
def mock_adapter():
    """Create a mock OpenLineage adapter."""
    adapter = MagicMock(spec=PrefectOpenLineageAdapter)
    adapter.create_and_emit_flow_event = MagicMock()
    adapter.create_and_emit_task_event = MagicMock()
    return adapter


@pytest.fixture
def listener(mock_prefect_client, mock_adapter):
    """Create a listener instance with mocked dependencies."""
    return PrefectOpenLineageListener(
        client=mock_prefect_client,
        adapter=mock_adapter
    )


@pytest.fixture
def sample_flow_event():
    """Create a sample flow start event."""
    return Event(**json.loads(FLOW_START_EVENT))


@pytest.fixture
def sample_task_event():
    """Create a sample task start event."""
    return Event(**json.loads(TASK_START_EVENT))


# ========== Tests for build_run_id ==========


def test_build_run_id_returns_string(listener):
    """Test that build_run_id returns a string UUID."""
    run_id = listener.build_run_id(
        execution_time=datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00"),
        run_name="test_flow",
        namespace="default"
    )
    assert isinstance(run_id, str)
    assert len(run_id) > 0


def test_build_run_id_deterministic(listener):
    """Test that build_run_id is deterministic (same inputs produce same output)."""
    execution_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    run_name = "test_flow"
    namespace = "default"
    
    run_id_1 = listener.build_run_id(execution_time, run_name, namespace)
    run_id_2 = listener.build_run_id(execution_time, run_name, namespace)
    
    assert run_id_1 == run_id_2


def test_build_run_id_different_for_different_inputs(listener):
    """Test that different inputs produce different UUIDs."""
    execution_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    
    run_id_1 = listener.build_run_id(execution_time, "flow_a", "default")
    run_id_2 = listener.build_run_id(execution_time, "flow_b", "default")
    
    assert run_id_1 != run_id_2


# ========== Tests for get_deployment_and_flow_info ==========


@pytest.mark.asyncio
async def test_get_deployment_and_flow_info_success(listener, mock_prefect_client):
    """Test successful retrieval of deployment and flow info."""
    # Setup mock responses
    flow_run = MagicMock()
    flow_run.deployment_id = "dep-123"
    flow_run.flow_id = "flow-456"
    flow_run.start_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    
    deployment = MagicMock()
    deployment.id = "dep-123"
    deployment.created = datetime.fromisoformat("2026-07-05T08:05:01.001+00:00")
    deployment.updated = datetime.fromisoformat("2026-07-05T08:06:02.100+00:00")
    deployment.name = "test_deploy"
    deployment.job_variables = {"env": {"OPENLINEAGE_NAMESPACE": "custom_namespace"}}
    
    flow = MagicMock()
    flow.name = "test_flow"
    
    mock_prefect_client.read_flow_run.return_value = flow_run
    mock_prefect_client.read_deployment.return_value = deployment
    mock_prefect_client.read_flow.return_value = flow
    
    result = await listener.get_deployment_and_flow_info("flow-run-123")
    
    assert isinstance(result, tuple)
    assert len(result) == 7
    assert result[0] == "dep-123"  # deployment_id
    assert result[4] == "test_deploy"  # deployment_name
    assert result[5] == "custom_namespace"  # namespace
    assert result[6] == "test_flow"  # flow_name


@pytest.mark.asyncio
async def test_get_deployment_and_flow_info_uses_env_namespace(listener, mock_prefect_client):
    """Test that env namespace is used when deployment variable not found."""
    flow_run = MagicMock()
    flow_run.deployment_id = "dep-123"
    flow_run.flow_id = "flow-456"
    flow_run.start_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    
    deployment = MagicMock()
    deployment.id = "dep-123"
    deployment.created = datetime.fromisoformat("2026-07-05T08:05:01.001+00:00")
    deployment.updated = datetime.fromisoformat("2026-07-05T08:06:02.100+00:00")
    deployment.name = "test_deploy"
    deployment.job_variables = {"env": {}}  # Empty, so namespace should come from module-level JOB_NAMESPACE
    
    flow = MagicMock()
    flow.name = "test_flow"
    
    mock_prefect_client.read_flow_run.return_value = flow_run
    mock_prefect_client.read_deployment.return_value = deployment
    mock_prefect_client.read_flow.return_value = flow
    
    # Patch the module-level JOB_NAMESPACE variable
    with patch("prefect_openlineage.listener.JOB_NAMESPACE", "env_namespace"):
        result = await listener.get_deployment_and_flow_info("flow-run-123")
    
    assert result[5] == "env_namespace"


# ========== Tests for get_prefect_version ==========


@pytest.mark.asyncio
async def test_get_prefect_version_success(listener, mock_prefect_client):
    """Test successful version retrieval."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"version": "3.7.6"}
    mock_prefect_client._client.get.return_value = mock_response
    
    version = await listener.get_prefect_version()
    
    assert version == {"version": "3.7.6"}
    mock_prefect_client._client.get.assert_called_once_with("/admin/version")


@pytest.mark.asyncio
async def test_get_prefect_version_handles_error(listener, mock_prefect_client):
    """Test that version retrieval handles errors gracefully."""
    mock_prefect_client._client.get.side_effect = TypeError("API error")
    
    version = await listener.get_prefect_version()
    
    assert version is None


# ========== Tests for get_flow_ns ==========


@pytest.mark.asyncio
async def test_get_flow_ns_from_deployment_variables(listener, mock_prefect_client):
    """Test namespace retrieval from deployment job variables."""
    flow_run = MagicMock()
    flow_run.deployment_id = "dep-123"
    
    deployment = MagicMock()
    deployment.job_variables = {"env": {"OPENLINEAGE_NAMESPACE": "custom_ns"}}
    
    mock_prefect_client.read_flow_run.return_value = flow_run
    mock_prefect_client.read_deployment.return_value = deployment
    
    ns = await listener.get_flow_ns("flow-run-123")
    
    assert ns == "custom_ns"


@pytest.mark.asyncio
async def test_get_flow_ns_from_env_variable(listener, mock_prefect_client):
    """Test namespace retrieval from environment variable when deployment variable not found."""
    flow_run = MagicMock()
    flow_run.deployment_id = "dep-123"
    
    deployment = MagicMock()
    deployment.job_variables = {"env": {}}
    
    mock_prefect_client.read_flow_run.return_value = flow_run
    mock_prefect_client.read_deployment.return_value = deployment
    
    # Patch the module-level JOB_NAMESPACE variable
    with patch("prefect_openlineage.listener.JOB_NAMESPACE", "env_ns"):
        ns = await listener.get_flow_ns("flow-run-123")
    
    assert ns == "env_ns"


# ========== Tests for get_job_ns ==========


@pytest.mark.asyncio
async def test_get_job_ns_delegates_to_get_flow_ns(listener, mock_prefect_client):
    """Test that get_job_ns delegates to get_flow_ns."""
    task_run = MagicMock()
    task_run.flow_run_id = "flow-run-123"
    
    mock_prefect_client.read_task_run.return_value = task_run
    
    with patch.object(listener, "get_flow_ns", return_value="test_ns") as mock_get_flow_ns:
        ns = await listener.get_job_ns("task-run-123")
    
    assert ns == "test_ns"
    mock_get_flow_ns.assert_called_once_with("flow-run-123")


# ========== Tests for get_flow_run_start_time ==========


@pytest.mark.asyncio
async def test_get_flow_run_start_time(listener, mock_prefect_client):
    """Test retrieval of flow run start time."""
    flow_run = MagicMock()
    start_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    flow_run.start_time = start_time
    
    mock_prefect_client.read_flow_run.return_value = flow_run
    
    result = await listener.get_flow_run_start_time("flow-run-123")
    
    assert result == start_time
    mock_prefect_client.read_flow_run.assert_called_once_with("flow-run-123")


# ========== Tests for get_artifacts_by_task_run ==========


@pytest.mark.asyncio
async def test_get_artifacts_by_task_run_success(listener, mock_prefect_client):
    """Test successful artifact retrieval and parsing."""
    artifacts = [
        {
            "description": "ol-dataset_input",
            "data": str([{"database_uri": "postgres://localhost", "table": "users"}])
        },
        {
            "description": "ol-dataset_output",
            "data": str([{"database_uri": "postgres://localhost", "table": "results"}])
        }
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = artifacts
    
    mock_prefect_client._client.post.return_value = mock_response
    
    result = await listener.get_artifacts_by_task_run("task-run-123")
    
    assert len(result) == 2
    assert result[0]["uri"] == "postgres://localhost"
    assert result[0]["table"] == "users"
    assert result[0]["dataset_type"] == "input"
    assert result[1]["dataset_type"] == "output"


@pytest.mark.asyncio
async def test_get_artifacts_by_task_run_filters_ol_datasets(listener, mock_prefect_client):
    """Test that non-openlineage artifacts are filtered out."""
    artifacts = [
        {
            "description": "regular artifact",
            "data": str([{"database_uri": "postgres://localhost", "table": "users"}])
        },
        {
            "description": "ol-dataset_input",
            "data": str([{"database_uri": "postgres://localhost", "table": "results"}])
        }
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = artifacts
    
    mock_prefect_client._client.post.return_value = mock_response
    
    result = await listener.get_artifacts_by_task_run("task-run-123")
    
    assert len(result) == 1
    assert result[0]["uri"] == "postgres://localhost"


@pytest.mark.asyncio
async def test_get_artifacts_by_task_run_no_artifacts(listener, mock_prefect_client):
    """Test handling when no artifacts are found."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    
    mock_prefect_client._client.post.return_value = mock_response
    
    result = await listener.get_artifacts_by_task_run("task-run-123")
    
    assert result == []


@pytest.mark.asyncio
async def test_get_artifacts_by_task_run_empty_list(listener, mock_prefect_client):
    """Test handling when artifacts list is empty."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    
    mock_prefect_client._client.post.return_value = mock_response
    
    result = await listener.get_artifacts_by_task_run("task-run-123")
    
    assert result == []


# ========== Tests for get_parent_runs ==========


@pytest.mark.asyncio
async def test_get_parent_runs_success(listener, mock_prefect_client):
    """Test successful retrieval of parent task runs."""
    payload = {
        "task_run": {
            "task_inputs": {
                "__parents__": [
                    {"input_type": "task_run", "id": "parent-task-123"},
                    {"input_type": "parameter", "id": "param-456"}
                ]
            }
        }
    }
    
    parent_task_run = MagicMock()
    parent_task_run.name = "parent_task-abc"
    parent_task_run.start_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    
    mock_prefect_client.read_task_run.return_value = parent_task_run
    
    with patch.object(listener, "get_job_ns", return_value="default") as mock_get_ns:
        result = await listener.get_parent_runs(payload, "task-run-123")
    
    assert len(result) == 1
    assert result[0]["name"] == "parent_task"
    assert result[0]["namespace"] == "default"
    assert isinstance(result[0]["id"], str)


@pytest.mark.asyncio
async def test_get_parent_runs_no_parents(listener, mock_prefect_client):
    """Test handling when task has no parent dependencies."""
    payload = {
        "task_run": {
            "task_inputs": {
                "__parents__": []
            }
        }
    }
    
    result = await listener.get_parent_runs(payload, "task-run-123")
    
    assert result == []


@pytest.mark.asyncio
async def test_get_parent_runs_missing_key(listener, mock_prefect_client):
    """Test handling when __parents__ key is missing."""
    payload = {
        "task_run": {
            "task_inputs": {}
        }
    }
    
    result = await listener.get_parent_runs(payload, "task-run-123")
    
    assert result == []


@pytest.mark.asyncio
async def test_get_parent_runs_filters_non_task_inputs(listener, mock_prefect_client):
    """Test that non-task parent inputs are filtered out."""
    payload = {
        "task_run": {
            "task_inputs": {
                "__parents__": [
                    {"input_type": "task_run", "id": "parent-task-123"},
                    {"input_type": "task_run", "id": "parent-task-456"},
                    {"input_type": "parameter", "id": "param-789"}
                ]
            }
        }
    }
    
    parent_task_run = MagicMock()
    parent_task_run.name = "parent_task-abc"
    parent_task_run.start_time = datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")
    
    mock_prefect_client.read_task_run.return_value = parent_task_run
    
    with patch.object(listener, "get_job_ns", return_value="default"):
        result = await listener.get_parent_runs(payload, "task-run-123")
    
    assert len(result) == 2


# ========== Tests for collect_and_process_flow_runs ==========


@pytest.mark.asyncio
async def test_collect_and_process_flow_runs_success(listener, sample_flow_event, mock_adapter):
    """Test successful flow event processing."""
    mock_adapter.create_and_emit_flow_event = MagicMock()
    
    with patch.object(listener, "get_deployment_and_flow_info") as mock_get_info:
        mock_get_info.return_value = (
            "dep-123",  # deployment_id
            datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00"),  # start_time
            "2026-07-05T08:05:01.001Z",  # deployment_created
            "2026-07-05T08:06:02.100Z",  # deployment_updated
            "test_deploy",  # deployment_name
            "default",  # namespace
            "test_flow"  # flow_name
        )
        
        prefect_version = "3.7.6"
        event_state = "START"
        
        await listener.collect_and_process_flow_runs(prefect_version, sample_flow_event, event_state)
    
    # The function loops through related items and processes each, so it may be called multiple times
    assert mock_adapter.create_and_emit_flow_event.call_count > 0
    call_args = mock_adapter.create_and_emit_flow_event.call_args_list[0]
    assert call_args.kwargs["eventType"] == "START"
    assert call_args.kwargs["flowName"] == "GitHub Stars"


@pytest.mark.asyncio
async def test_collect_and_process_flow_runs_handles_attribute_error(listener, sample_flow_event, mock_adapter):
    """Test that AttributeError during build_run_id is handled gracefully."""
    with patch.object(listener, "get_deployment_and_flow_info") as mock_get_info, \
         patch.object(listener, "build_run_id") as mock_build_run_id, \
         patch("prefect_openlineage.listener.logger"):
        
        mock_get_info.return_value = (
            "dep-123",
            datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00"),
            "2026-07-05T08:05:01.001Z",
            "2026-07-05T08:06:02.100Z",
            "test_deploy",
            "default",
            "test_flow"
        )
        
        # Make build_run_id raise AttributeError
        mock_build_run_id.side_effect = AttributeError("Build failed")
        
        # The function should handle the error and not raise an exception
        await listener.collect_and_process_flow_runs("3.7.6", sample_flow_event, "START")
    
    mock_adapter.create_and_emit_flow_event.assert_not_called()


# ========== Tests for collect_and_process_task_runs ==========


@pytest.mark.asyncio
async def test_collect_and_process_task_runs_success(listener, sample_task_event, mock_adapter):
    """Test successful task event processing."""
    mock_adapter.create_and_emit_task_event = MagicMock()
    
    task_run = MagicMock()
    task_run.start_time = datetime.fromisoformat("2026-07-07T13:21:07.336123+00:00")
    
    with patch.object(listener, "get_job_ns", return_value="default"), \
         patch.object(listener, "build_run_id", return_value="task-run-id"), \
         patch.object(listener, "get_artifacts_by_task_run", return_value=[]), \
         patch.object(listener, "get_parent_runs", return_value=[]), \
         patch.object(listener, "get_deployment_and_flow_info") as mock_get_info:
        
        mock_prefect_client = listener.client
        mock_prefect_client.read_task_run.return_value = task_run
        
        mock_get_info.return_value = (
            "dep-123",
            datetime.fromisoformat("2026-07-07T13:21:07.336123+00:00"),
            "2026-07-05T08:05:01.001Z",
            "2026-07-05T08:06:02.100Z",
            "test_deploy",
            "default",
            "GitHub Stars"
        )
        
        await listener.collect_and_process_task_runs("3.7.6", sample_task_event, "START")
    
    mock_adapter.create_and_emit_task_event.assert_called_once()
    call_args = mock_adapter.create_and_emit_task_event.call_args
    assert call_args.kwargs["eventType"] == "START"
    assert call_args.kwargs["taskName"] == "fake_ingest"


@pytest.mark.asyncio
async def test_collect_and_process_task_runs_with_datasets(listener, sample_task_event, mock_adapter):
    """Test task processing with input and output datasets."""
    mock_adapter.create_and_emit_task_event = MagicMock()
    
    task_run = MagicMock()
    task_run.start_time = datetime.fromisoformat("2026-07-07T13:21:07.336123+00:00")
    
    datasets = [
        {"uri": "postgres://localhost", "table": "users", "dataset_type": "input"},
        {"uri": "postgres://localhost", "table": "results", "dataset_type": "output"}
    ]
    
    with patch.object(listener, "get_job_ns", return_value="default"), \
         patch.object(listener, "build_run_id", return_value="task-run-id"), \
         patch.object(listener, "get_artifacts_by_task_run", return_value=datasets), \
         patch.object(listener, "get_parent_runs", return_value=[]), \
         patch.object(listener, "get_deployment_and_flow_info") as mock_get_info:
        
        mock_prefect_client = listener.client
        mock_prefect_client.read_task_run.return_value = task_run
        
        mock_get_info.return_value = (
            "dep-123",
            datetime.fromisoformat("2026-07-07T13:21:07.336123+00:00"),
            "2026-07-05T08:05:01.001Z",
            "2026-07-05T08:06:02.100Z",
            "test_deploy",
            "default",
            "GitHub Stars"
        )
        
        await listener.collect_and_process_task_runs("3.7.6", sample_task_event, "START")
    
    call_args = mock_adapter.create_and_emit_task_event.call_args
    assert len(call_args.kwargs["inputDatasets"]) == 1
    assert len(call_args.kwargs["outputDatasets"]) == 1
    assert call_args.kwargs["inputDatasets"][0]["uri"] == "postgres://localhost"


@pytest.mark.asyncio
async def test_collect_and_process_task_runs_no_task_run(listener, sample_task_event, mock_adapter):
    """Test handling when task run is not found."""
    listener.client.read_task_run.return_value = None
    
    await listener.collect_and_process_task_runs("3.7.6", sample_task_event, "START")
    
    mock_adapter.create_and_emit_task_event.assert_not_called()


@pytest.mark.asyncio
async def test_collect_and_process_task_runs_with_job_dependencies(listener, sample_task_event, mock_adapter):
    """Test task processing with job dependencies."""
    mock_adapter.create_and_emit_task_event = MagicMock()
    
    task_run = MagicMock()
    task_run.start_time = datetime.fromisoformat("2026-07-07T13:21:07.336123+00:00")
    
    parent_runs = [
        {"name": "parent_task", "namespace": "default", "id": "parent-run-id"}
    ]
    
    with patch.object(listener, "get_job_ns", return_value="default"), \
         patch.object(listener, "build_run_id", return_value="task-run-id"), \
         patch.object(listener, "get_artifacts_by_task_run", return_value=[]), \
         patch.object(listener, "get_parent_runs", return_value=parent_runs), \
         patch.object(listener, "get_deployment_and_flow_info") as mock_get_info:
        
        mock_prefect_client = listener.client
        mock_prefect_client.read_task_run.return_value = task_run
        
        mock_get_info.return_value = (
            "dep-123",
            datetime.fromisoformat("2026-07-07T13:21:07.336123+00:00"),
            "2026-07-05T08:05:01.001Z",
            "2026-07-05T08:06:02.100Z",
            "test_deploy",
            "default",
            "GitHub Stars"
        )
        
        await listener.collect_and_process_task_runs("3.7.6", sample_task_event, "START")
    
    call_args = mock_adapter.create_and_emit_task_event.call_args
    assert len(call_args.kwargs["jobDeps"]) == 1
    assert call_args.kwargs["jobDeps"][0]["name"] == "parent_task"


# ========== Event state mapping tests ==========


def test_listener_initialization(listener, mock_prefect_client, mock_adapter):
    """Test listener initialization with custom client and adapter."""
    assert listener.client == mock_prefect_client
    assert listener.ol_adapter == mock_adapter


def test_listener_initialization_defaults():
    """Test listener initialization with default client and adapter."""
    with patch("prefect_openlineage.listener.get_client") as mock_get_client:
        listener = PrefectOpenLineageListener()
        mock_get_client.assert_called_once()
