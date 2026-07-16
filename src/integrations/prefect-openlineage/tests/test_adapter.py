"""
Unit tests for PrefectOpenLineageAdapter module.

Tests cover OpenLineage event creation and emission.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from openlineage.client.run import RunEvent, RunState
from prefect_openlineage.adapter import PRODUCER, PrefectOpenLineageAdapter

# ========== Fixtures ==========


@pytest.fixture
def mock_client():
    """Create a mock OpenLineage client."""
    client = MagicMock()
    client.emit = MagicMock()
    return client


@pytest.fixture
def adapter(mock_client):
    """Create an adapter instance with mocked OpenLineage client."""
    return PrefectOpenLineageAdapter(client=mock_client)


@pytest.fixture
def sample_datetime():
    """Create a sample datetime for testing."""
    return datetime.fromisoformat("2026-07-06T11:04:46.467291+00:00")


@pytest.fixture
def sample_run_id():
    """Create a sample valid UUID for run ID."""
    return str(uuid.uuid4())


# ========== Tests for create_and_emit_flow_event ==========


def test_create_and_emit_flow_event_start(adapter, sample_datetime, sample_run_id):
    """Test creation and emission of a flow START event."""
    adapter.create_and_emit_flow_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        flowName="test_flow",
        flowNamespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
    )

    adapter.client.emit.assert_called_once()
    event = adapter.client.emit.call_args[0][0]

    assert isinstance(event, RunEvent)
    assert event.eventType == RunState.START
    assert event.eventTime == sample_datetime.isoformat()
    assert event.job.name == "test_flow"
    assert event.job.namespace == "default"
    assert event.producer == PRODUCER


def test_create_and_emit_flow_event_complete(adapter, sample_datetime, sample_run_id):
    """Test creation and emission of a flow COMPLETE event."""
    adapter.create_and_emit_flow_event(
        runId=sample_run_id,
        eventType="COMPLETE",
        eventTime=sample_datetime,
        flowName="test_flow",
        flowNamespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
    )

    event = adapter.client.emit.call_args[0][0]
    assert event.eventType == RunState.COMPLETE


def test_create_and_emit_flow_event_failed(adapter, sample_datetime, sample_run_id):
    """Test creation and emission of a flow FAILED event."""
    adapter.create_and_emit_flow_event(
        runId=sample_run_id,
        eventType="FAILED",
        eventTime=sample_datetime,
        flowName="test_flow",
        flowNamespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
    )

    event = adapter.client.emit.call_args[0][0]
    assert event.eventType == RunState.FAIL


def test_create_and_emit_flow_event_has_processing_engine_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that flow event includes processingEngine facet."""
    adapter.create_and_emit_flow_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        flowName="test_flow",
        flowNamespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
    )

    event = adapter.client.emit.call_args[0][0]

    assert "processingEngine" in event.run.facets
    assert event.run.facets["processingEngine"].version == "3.7.6"
    assert event.run.facets["processingEngine"].name == "Prefect"


def test_create_and_emit_flow_event_has_deployment_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that flow event includes prefectDeployment facet."""
    adapter.create_and_emit_flow_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        flowName="test_flow",
        flowNamespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
    )

    event = adapter.client.emit.call_args[0][0]

    assert "prefectDeployment" in event.run.facets
    assert event.run.facets["prefectDeployment"].deployment_id == "dep-123"
    assert event.run.facets["prefectDeployment"].name == "test_deploy"


def test_create_and_emit_flow_event_has_job_type_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that flow event includes jobType facet."""
    adapter.create_and_emit_flow_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        flowName="test_flow",
        flowNamespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
    )

    event = adapter.client.emit.call_args[0][0]

    assert "jobType" in event.job.facets
    assert event.job.facets["jobType"].processingType == "BATCH"
    assert event.job.facets["jobType"].integration == "Prefect"
    assert event.job.facets["jobType"].jobType == "FLOW"


def test_create_and_emit_flow_event_handles_emission_error(
    adapter, sample_datetime, sample_run_id
):
    """Test that emission errors are caught and logged."""
    adapter.client.emit.side_effect = Exception("Emission failed")

    with patch("prefect_openlineage.adapter.logger") as mock_logger:
        adapter.create_and_emit_flow_event(
            runId=sample_run_id,
            eventType="START",
            eventTime=sample_datetime,
            flowName="test_flow",
            flowNamespace="default",
            prefectVersion="3.7.6",
            deploymentId="dep-123",
            deploymentCreated="2026-07-05T08:05:01.001Z",
            deploymentUpdated="2026-07-05T08:06:02.100Z",
            deploymentName="test_deploy",
        )

        mock_logger.exception.assert_called_once()


# ========== Tests for create_and_emit_task_event ==========


def test_create_and_emit_task_event_start(adapter, sample_datetime, sample_run_id):
    """Test creation and emission of a task START event."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        jobDeps=[],
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    adapter.client.emit.assert_called_once()
    event = adapter.client.emit.call_args[0][0]

    assert isinstance(event, RunEvent)
    assert event.eventType == RunState.START
    assert event.job.name == "test_task"
    assert event.job.namespace == "default"


def test_create_and_emit_task_event_complete(adapter, sample_datetime, sample_run_id):
    """Test creation and emission of a task COMPLETE event."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="COMPLETE",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]
    assert event.eventType == RunState.COMPLETE


def test_create_and_emit_task_event_failed(adapter, sample_datetime, sample_run_id):
    """Test creation and emission of a task FAILED event."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="FAILED",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]
    assert event.eventType == RunState.FAIL


def test_create_and_emit_task_event_has_nominal_time_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes nominalTime facet."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "nominalTime" in event.run.facets
    assert event.run.facets["nominalTime"].nominalStartTime == sample_datetime


def test_create_and_emit_task_event_has_parent_run_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes parentRun facet."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "parentRun" in event.run.facets
    assert event.run.facets["parentRun"].run["runId"] == "flow-run-456"
    assert event.run.facets["parentRun"].job["name"] == "test_flow"


def test_create_and_emit_task_event_has_job_dependencies(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes job dependencies facet."""
    job_deps = [
        {"namespace": "default", "name": "parent_task_1"},
        {"namespace": "default", "name": "parent_task_2"},
    ]

    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        jobDeps=job_deps,
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "jobDependencies" in event.run.facets
    assert len(event.run.facets["jobDependencies"].upstream) == 2


def test_create_and_emit_task_event_no_job_dependencies(
    adapter, sample_datetime, sample_run_id
):
    """Test that jobDependencies facet is not included when no dependencies exist."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        jobDeps=[],
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "jobDependencies" not in event.run.facets


def test_create_and_emit_task_event_has_input_datasets(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes input datasets."""
    input_datasets = [
        {"uri": "postgres://localhost", "table": "users"},
        {"uri": "postgres://localhost", "table": "accounts"},
    ]

    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=input_datasets,
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert len(event.inputs) == 2
    assert event.inputs[0].namespace == "postgres://localhost"
    assert event.inputs[0].name == "users"


def test_create_and_emit_task_event_has_output_datasets(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes output datasets."""
    output_datasets = [{"uri": "postgres://localhost", "table": "results"}]

    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=output_datasets,
    )

    event = adapter.client.emit.call_args[0][0]

    assert len(event.outputs) == 1
    assert event.outputs[0].namespace == "postgres://localhost"
    assert event.outputs[0].name == "results"


def test_create_and_emit_task_event_has_deployment_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes prefectDeployment facet."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "prefectDeployment" in event.run.facets
    assert event.run.facets["prefectDeployment"].deployment_id == "dep-123"
    assert event.run.facets["prefectDeployment"].name == "test_deploy"


def test_create_and_emit_task_event_has_processing_engine_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes processingEngine facet."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "processingEngine" in event.run.facets
    assert event.run.facets["processingEngine"].version == "3.7.6"
    assert event.run.facets["processingEngine"].name == "Prefect"


def test_create_and_emit_task_event_has_job_type_facet(
    adapter, sample_datetime, sample_run_id
):
    """Test that task event includes jobType facet."""
    adapter.create_and_emit_task_event(
        runId=sample_run_id,
        eventType="START",
        eventTime=sample_datetime,
        expectedEventTime=sample_datetime,
        flowRunId="flow-run-456",
        flowName="test_flow",
        taskName="test_task",
        namespace="default",
        prefectVersion="3.7.6",
        deploymentId="dep-123",
        deploymentCreated="2026-07-05T08:05:01.001Z",
        deploymentUpdated="2026-07-05T08:06:02.100Z",
        deploymentName="test_deploy",
        inputDatasets=[],
        outputDatasets=[],
    )

    event = adapter.client.emit.call_args[0][0]

    assert "jobType" in event.job.facets
    assert event.job.facets["jobType"].processingType == "BATCH"
    assert event.job.facets["jobType"].integration == "Prefect"
    assert event.job.facets["jobType"].jobType == "TASK"


def test_create_and_emit_task_event_handles_emission_error(
    adapter, sample_datetime, sample_run_id
):
    """Test that emission errors are caught and logged."""
    adapter.client.emit.side_effect = Exception("Emission failed")

    with patch("prefect_openlineage.adapter.logger") as mock_logger:
        adapter.create_and_emit_task_event(
            runId=sample_run_id,
            eventType="START",
            eventTime=sample_datetime,
            expectedEventTime=sample_datetime,
            flowRunId="flow-run-456",
            flowName="test_flow",
            taskName="test_task",
            namespace="default",
            prefectVersion="3.7.6",
            deploymentId="dep-123",
            deploymentCreated="2026-07-05T08:05:01.001Z",
            deploymentUpdated="2026-07-05T08:06:02.100Z",
            deploymentName="test_deploy",
            inputDatasets=[],
            outputDatasets=[],
        )

        mock_logger.exception.assert_called_once()


# ========== Tests for adapter initialization ==========


def test_adapter_initialization_with_client():
    """Test adapter initialization with provided client."""
    client = MagicMock()
    adapter = PrefectOpenLineageAdapter(client=client)

    assert adapter.client == client


def test_adapter_initialization_without_client():
    """Test adapter initialization with default client."""
    with patch("prefect_openlineage.adapter.OpenLineageClient") as mock_client_class:
        adapter = PrefectOpenLineageAdapter()

        mock_client_class.assert_called_once()


def test_producer_constant():
    """Test that PRODUCER constant is correctly set."""
    assert (
        PRODUCER
        == "https://github.com/prefectHQ/prefect/src/integrations/prefect-openlineage"
    )
