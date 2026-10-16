from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest
import yaml
from armada_client.armada import event_pb2, job_pb2, submit_pb2
from armada_client.asyncio_client import ArmadaAsyncIOClient
from armada_client.event import Event
from prefect_armada.credentials import ArmadaClusterConfig, ArmadaCredentials
from prefect_armada.jobs import ArmadaJob

from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings
from prefect.testing.utilities import prefect_test_harness

BASEDIR = (
    Path.cwd() / "src" / "integrations" / "prefect-armada" / "tests"
    if Path.cwd().name == "prefect"
    else Path.cwd() / "tests"
)
SAMPLE_JOB_PATH = BASEDIR / "sample_armada_resources" / "sample_job.yaml"


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    try:
        with prefect_test_harness():
            yield
    except OSError as e:
        if "Directory not empty" in str(e):
            pass
        else:
            raise


@pytest.fixture(scope="session", autouse=True)
def disable_api_logging():
    """
    Disables API logging for all tests.
    """
    with temporary_settings(updates={PREFECT_LOGGING_TO_API_ENABLED: False}):
        yield


@pytest.fixture
def sample_job_dict():
    return yaml.safe_load(SAMPLE_JOB_PATH.read_text())


@pytest.fixture
def armada_cluster_config():
    return ArmadaClusterConfig(
        host="armada.example.com",
        port=50051,
        disable_ssl=True,
    )


@pytest.fixture
def armada_credentials(armada_cluster_config):
    return ArmadaCredentials(cluster_config=armada_cluster_config)


def make_job_submit_response(
    job_id: str = "test-job-id", error: str = ""
) -> submit_pb2.JobSubmitResponse:
    """Builds a `JobSubmitResponse` for a single submitted job."""
    return submit_pb2.JobSubmitResponse(
        job_response_items=[
            submit_pb2.JobSubmitResponseItem(job_id=job_id, error=error)
        ]
    )


def make_job_status_response(**job_states: Any) -> job_pb2.JobStatusResponse:
    """Builds a `JobStatusResponse` from job ID to `JobState` value mappings."""
    return job_pb2.JobStatusResponse(job_states=job_states)


def make_event(
    event_type: str,
    job_id: str = "test-job-id",
    message_id: str = "1",
    annotations: dict | None = None,
    **fields: Any,
) -> Event:
    """Builds an Armada `Event` of the given type."""
    event_cls = {
        "submitted": event_pb2.JobSubmittedEvent,
        "queued": event_pb2.JobQueuedEvent,
        "leased": event_pb2.JobLeasedEvent,
        "pending": event_pb2.JobPendingEvent,
        "running": event_pb2.JobRunningEvent,
        "succeeded": event_pb2.JobSucceededEvent,
        "failed": event_pb2.JobFailedEvent,
        "cancelled": event_pb2.JobCancelledEvent,
        "preempted": event_pb2.JobPreemptedEvent,
        "lease_expired": event_pb2.JobLeaseExpiredEvent,
    }[event_type]

    if event_type == "submitted":
        fields["job"] = submit_pb2.Job(id=job_id, annotations=annotations or {})

    message = event_pb2.EventMessage(**{event_type: event_cls(job_id=job_id, **fields)})
    return Event(event_pb2.EventStreamMessage(id=message_id, message=message))


class FakeRpcError(grpc.RpcError):
    """A gRPC error with a status code and details, like the real client raises."""

    def __init__(self, code: grpc.StatusCode, details: str = ""):
        self._code = code
        self._details = details

    def code(self) -> grpc.StatusCode:
        return self._code

    def details(self) -> str:
        return self._details


class FakeEventStream:
    """An async iterator that mimics an Armada job set event stream."""

    def __init__(self, events: list, hang: bool = False):
        self._events = list(events)
        self._hang = hang
        self.cancelled = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._events:
            return self._events.pop(0)
        if self._hang:
            # Armada keeps job set streams open, so mimic a stream that has no
            # more events but has not ended.
            import anyio

            await anyio.sleep(60)
        raise StopAsyncIteration

    def cancel(self):
        self.cancelled = True


@dataclass
class FakeLogLine:
    line: str
    timestamp: str = "2026-07-29T00:00:00Z"


class FakeLogResponse:
    def __init__(self, lines: list[str]):
        self.log = [FakeLogLine(line) for line in lines]


@pytest.fixture
def mock_armada_client(monkeypatch: pytest.MonkeyPatch):
    """Patches `ArmadaCredentials.get_client` to yield a mock Armada client."""
    client = AsyncMock(spec=ArmadaAsyncIOClient)
    client.unmarshal_event_response = MagicMock(side_effect=lambda event: event)
    client.unwatch_events = MagicMock()

    @asynccontextmanager
    async def get_client(self):
        yield client

    monkeypatch.setattr(ArmadaCredentials, "get_client", get_client)
    return client


@pytest.fixture
def mock_binoculars_client(monkeypatch: pytest.MonkeyPatch):
    """Patches `ArmadaCredentials.get_binoculars_client` with a mock client."""
    client = MagicMock()
    client.logs.return_value = FakeLogResponse(["line one", "line two"])

    @contextmanager
    def get_binoculars_client(self):
        yield client

    monkeypatch.setattr(
        ArmadaCredentials, "get_binoculars_client", get_binoculars_client
    )
    return client


@pytest.fixture
def valid_armada_job_block(armada_credentials, sample_job_dict):
    return ArmadaJob(
        credentials=armada_credentials,
        job_request=sample_job_dict,
        queue="test-queue",
        job_set_id="test-job-set",
        interval_seconds=0,
    )
