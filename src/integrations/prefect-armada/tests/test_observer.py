import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest
from armada_client.armada import event_pb2
from conftest import FakeEventStream, FakeRpcError, make_event
from prefect_armada import observer
from prefect_armada.credentials import ArmadaCredentials

from prefect.client.schemas.objects import FlowRun
from prefect.exceptions import Abort, ObjectNotFound
from prefect.states import Completed, Crashed, Pending, Running, Scheduled

FLOW_RUN_ID = str(uuid.uuid4())
PREFECT_ANNOTATIONS = {
    "prefect.io/flow-run-id": FLOW_RUN_ID,
    "prefect.io/flow-run-name": "my-flow-run-name",
    "prefect.io/deployment-id": "11111111-1111-1111-1111-111111111111",
    "prefect.io/deployment-name": "my-deployment",
    "prefect.io/flow-id": "22222222-2222-2222-2222-222222222222",
    "prefect.io/flow-name": "my-flow",
    "prefect.io/work-pool-id": "33333333-3333-3333-3333-333333333333",
    "prefect.io/work-pool-name": "my-work-pool",
    "prefect.io/worker-name": "My Worker",
}


@pytest.fixture(autouse=True)
def clean_observer_state():
    """Keeps observer module state from leaking between tests."""
    yield
    observer._watch_registry.clear()
    observer._pending_restarts.clear()
    observer._watch_tasks.clear()
    observer._last_event_cache.clear()
    observer.events_client = None
    observer.orchestration_client = None
    observer._observer_loop = None
    observer._observer_thread = None
    observer._stop_flag = None
    observer._ready_flag = None


@pytest.fixture
def mock_events_client():
    client = AsyncMock()
    observer.events_client = client
    return client


@pytest.fixture
def mock_orchestration_client():
    client = AsyncMock()
    observer.orchestration_client = client
    return client


def flow_run_with_state(state):
    return FlowRun(
        id=uuid.UUID(FLOW_RUN_ID),
        flow_id=uuid.uuid4(),
        name="my-flow-run-name",
        state=state,
    )


class TestJobSetWatchState:
    def test_is_not_finished_without_any_jobs(self):
        assert observer._JobSetWatchState().is_finished is False

    def test_is_not_finished_while_a_job_is_running(self):
        state = observer._JobSetWatchState()
        state.submitted_job_ids = {"a", "b"}
        state.finished_job_ids = {"a"}

        assert state.is_finished is False

    def test_is_finished_when_every_job_is_finished(self):
        state = observer._JobSetWatchState()
        state.submitted_job_ids = {"a", "b"}
        state.finished_job_ids = {"a", "b"}

        assert state.is_finished is True


class TestObserveJobSet:
    def test_registers_a_job_set(self):
        credentials = ArmadaCredentials()

        observer.observe_job_set(credentials, "my-queue", "my-job-set")

        assert observer._watch_registry == {("my-queue", "my-job-set"): credentials}
        assert observer._pending_restarts == set()

    def test_repeated_registration_queues_a_restart(self):
        credentials = ArmadaCredentials()

        observer.observe_job_set(credentials, "my-queue", "my-job-set")
        observer.observe_job_set(credentials, "my-queue", "my-job-set")

        assert observer._pending_restarts == {("my-queue", "my-job-set")}

    async def test_ensure_watch_starts_one_task_per_job_set(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        watched = []

        async def fake_watch(credentials, queue, job_set_id):
            watched.append((queue, job_set_id))

        monkeypatch.setattr(observer, "_watch_job_set", fake_watch)
        key = ("my-queue", "my-job-set")
        observer._watch_registry[key] = ArmadaCredentials()

        await observer._ensure_watch(key)
        task = observer._watch_tasks[key]
        await task

        assert watched == [("my-queue", "my-job-set")]

    async def test_ensure_watch_is_a_no_op_for_unregistered_job_sets(self):
        await observer._ensure_watch(("my-queue", "my-job-set"))
        assert observer._watch_tasks == {}


class TestRelatedResources:
    def test_builds_related_resources_from_annotations(self):
        related = observer._related_resources_from_annotations(PREFECT_ANNOTATIONS)

        roles = {resource.role: resource.id for resource in related}
        assert roles["flow-run"] == f"prefect.flow-run.{FLOW_RUN_ID}"
        assert roles["deployment"].startswith("prefect.deployment.")
        assert roles["flow"].startswith("prefect.flow.")
        assert roles["work-pool"].startswith("prefect.work-pool.")
        assert roles["worker"] == "prefect.worker.armada.my-worker"

    def test_returns_nothing_without_prefect_annotations(self):
        assert observer._related_resources_from_annotations({}) == []


class TestEventOccurred:
    def test_returns_none_when_unset(self):
        message = event_pb2.JobFailedEvent(job_id="job-1")
        assert observer._event_occurred(message) is None

    def test_reads_a_protobuf_timestamp(self):
        message = event_pb2.JobFailedEvent(job_id="job-1")
        message.created.FromDatetime(datetime(2026, 7, 29, tzinfo=timezone.utc))

        occurred = observer._event_occurred(message)

        assert occurred == datetime(2026, 7, 29, tzinfo=timezone.utc)

    def test_returns_none_for_a_message_without_a_created_field(self):
        assert observer._event_occurred(object()) is None


class TestReplicateJobEvent:
    async def test_emits_a_prefect_event(self, mock_events_client):
        event = make_event("running", job_id="job-1", message_id="msg-1")

        await observer._replicate_job_event(
            event=event,
            queue="my-queue",
            job_set_id="my-job-set",
            annotations=PREFECT_ANNOTATIONS,
        )

        emitted = mock_events_client.emit.await_args[1]["event"]
        assert emitted.event == "prefect.armada.job.running"
        assert emitted.resource.id == "prefect.armada.job.job-1"
        assert emitted.resource["armada.queue"] == "my-queue"
        assert emitted.resource["armada.job-set-id"] == "my-job-set"
        assert any(
            resource.id == f"prefect.flow-run.{FLOW_RUN_ID}"
            for resource in emitted.related
        )

    async def test_event_ids_are_deterministic(self, mock_events_client):
        event = make_event("running", job_id="job-1", message_id="msg-1")

        await observer._replicate_job_event(
            event=event, queue="q", job_set_id="s", annotations=PREFECT_ANNOTATIONS
        )
        first = mock_events_client.emit.await_args[1]["event"].id
        observer._last_event_cache.clear()
        await observer._replicate_job_event(
            event=event, queue="q", job_set_id="s", annotations=PREFECT_ANNOTATIONS
        )
        second = mock_events_client.emit.await_args[1]["event"].id

        assert first == second

    async def test_successive_events_follow_each_other(self, mock_events_client):
        await observer._replicate_job_event(
            event=make_event("running", job_id="job-1", message_id="msg-1"),
            queue="q",
            job_set_id="s",
            annotations=PREFECT_ANNOTATIONS,
        )
        first = mock_events_client.emit.await_args[1]["event"]

        await observer._replicate_job_event(
            event=make_event("succeeded", job_id="job-1", message_id="msg-2"),
            queue="q",
            job_set_id="s",
            annotations=PREFECT_ANNOTATIONS,
        )
        second = mock_events_client.emit.await_args[1]["event"]

        assert second.follows == first.id

    async def test_includes_the_failure_reason(self, mock_events_client):
        event = make_event(
            "failed", job_id="job-1", message_id="msg-1", reason="OOMKilled"
        )

        await observer._replicate_job_event(
            event=event, queue="q", job_set_id="s", annotations=PREFECT_ANNOTATIONS
        )

        emitted = mock_events_client.emit.await_args[1]["event"]
        assert emitted.resource["armada.reason"] == "OOMKilled"


class TestHandleEvent:
    async def test_records_annotations_from_submitted_events(self, mock_events_client):
        state = observer._JobSetWatchState()

        await observer._handle_event(
            make_event("submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )

        assert state.submitted_job_ids == {"job-1"}
        assert state.annotations["job-1"] == PREFECT_ANNOTATIONS
        mock_events_client.emit.assert_awaited_once()

    async def test_ignores_jobs_that_prefect_did_not_submit(self, mock_events_client):
        state = observer._JobSetWatchState()

        await observer._handle_event(
            make_event("submitted", job_id="job-1", annotations={"other": "system"}),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )
        await observer._handle_event(
            make_event("failed", job_id="job-1", message_id="2"),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )

        mock_events_client.emit.assert_not_awaited()

    async def test_marks_a_flow_run_as_crashed_on_failure(
        self, mock_events_client, monkeypatch: pytest.MonkeyPatch
    ):
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        state = observer._JobSetWatchState()
        state.annotations["job-1"] = PREFECT_ANNOTATIONS

        await observer._handle_event(
            make_event(
                "failed", job_id="job-1", reason="OOMKilled", pod_namespace="prefect"
            ),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )

        assert state.finished_job_ids == {"job-1"}
        assert mark_crashed.await_args[1] == {
            "flow_run_id": FLOW_RUN_ID,
            "job_id": "job-1",
            "event_type": "failed",
            "reason": "OOMKilled",
            "namespace": "prefect",
            "credentials": mark_crashed.await_args[1]["credentials"],
        }

    async def test_does_not_mark_a_successful_job_as_crashed(
        self, mock_events_client, monkeypatch: pytest.MonkeyPatch
    ):
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        state = observer._JobSetWatchState()
        state.annotations["job-1"] = PREFECT_ANNOTATIONS

        await observer._handle_event(
            make_event("succeeded", job_id="job-1"),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )

        mark_crashed.assert_not_awaited()
        assert state.is_finished is True

    async def test_can_skip_event_replication(
        self, mock_events_client, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_REPLICATE_JOB_EVENTS", "false"
        )
        state = observer._JobSetWatchState()
        state.annotations["job-1"] = PREFECT_ANNOTATIONS

        await observer._handle_event(
            make_event("running", job_id="job-1"),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )

        mock_events_client.emit.assert_not_awaited()


class TestWatchJobSet:
    @pytest.fixture(autouse=True)
    def fast_retries(self, monkeypatch: pytest.MonkeyPatch):
        """Keeps retry backoff from slowing the tests down."""
        monkeypatch.setattr(observer, "WATCH_RETRY_MAX_ATTEMPTS", 3)
        monkeypatch.setattr(observer, "WATCH_RETRY_MAX_DELAY_SECONDS", 0)

    async def test_watches_until_every_job_is_finished(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        stream = FakeEventStream(
            [
                make_event(
                    "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                ),
                make_event("running", job_id="job-1", message_id="2"),
                make_event(
                    "failed", job_id="job-1", message_id="3", reason="OOMKilled"
                ),
                # The watch should end before reaching this event
                make_event("submitted", job_id="job-2", message_id="4"),
            ],
            hang=True,
        )
        mock_armada_client.get_job_events_stream.return_value = stream

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        assert mock_events_client.emit.await_count == 3
        mark_crashed.assert_awaited_once()
        mock_armada_client.unwatch_events.assert_called_once_with(stream)

    async def test_retries_a_job_set_that_is_not_visible_yet(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """Armada makes a job set visible shortly after its first submission."""
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        mock_armada_client.get_job_events_stream.side_effect = [
            FakeRpcError(grpc.StatusCode.NOT_FOUND, "Jobset does not exist"),
            FakeEventStream(
                [
                    make_event(
                        "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                    ),
                    make_event("succeeded", job_id="job-1", message_id="2"),
                ],
                hang=True,
            ),
        ]

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        assert mock_armada_client.get_job_events_stream.await_count == 2
        assert mock_events_client.emit.await_count == 2

    async def test_gives_up_after_the_retry_limit(
        self, mock_events_client, mock_armada_client
    ):
        mock_armada_client.get_job_events_stream.side_effect = RuntimeError(
            "connection reset"
        )

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        # 3 attempts, per the `fast_retries` fixture
        assert mock_armada_client.get_job_events_stream.await_count == 3


class TestMarkFlowRunAsCrashed:
    @pytest.fixture(autouse=True)
    def no_grace_period(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_CRASHED_RUN_GRACE_SECONDS", "0"
        )

    @pytest.fixture
    def propose_state(self, monkeypatch: pytest.MonkeyPatch):
        mock = AsyncMock(return_value=Crashed())
        monkeypatch.setattr(observer, "propose_state", mock)
        return mock

    async def _mark(self, credentials=None):
        await observer._mark_flow_run_as_crashed(
            flow_run_id=FLOW_RUN_ID,
            job_id="job-1",
            event_type="failed",
            reason="OOMKilled",
            namespace="default",
            credentials=credentials or ArmadaCredentials(),
        )

    async def test_marks_a_running_flow_run_as_crashed(
        self, mock_orchestration_client, propose_state
    ):
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Running()
        )

        await self._mark()

        state = propose_state.await_args[1]["state"]
        assert state.is_crashed()
        assert "Armada job job-1 for this flow run failed: OOMKilled" in state.message

    @pytest.mark.parametrize(
        "state", [Completed(), Scheduled()], ids=["final", "scheduled"]
    )
    async def test_leaves_final_and_scheduled_runs_alone(
        self, mock_orchestration_client, propose_state, state
    ):
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            state
        )

        await self._mark()

        propose_state.assert_not_awaited()

    async def test_handles_a_missing_flow_run(
        self, mock_orchestration_client, propose_state
    ):
        mock_orchestration_client.read_flow_run.side_effect = ObjectNotFound(
            http_exc=Exception("not found")
        )

        await self._mark()

        propose_state.assert_not_awaited()

    async def test_handles_a_concurrent_state_transition(
        self, mock_orchestration_client, propose_state
    ):
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Running()
        )
        propose_state.side_effect = Abort("already terminal")

        await self._mark()

    async def test_forwards_logs_for_a_pending_run(
        self,
        mock_orchestration_client,
        propose_state,
        mock_binoculars_client,
        monkeypatch: pytest.MonkeyPatch,
    ):
        send_logs = MagicMock()
        monkeypatch.setattr(observer, "_send_crashed_job_logs", send_logs)
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Pending()
        )

        await self._mark()

        propose_state.assert_awaited_once()
        assert send_logs.call_args[1]["lines"] == ["line one", "line two"]

    async def test_does_not_forward_logs_when_disabled(
        self,
        mock_orchestration_client,
        propose_state,
        mock_binoculars_client,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_FORWARD_CRASHED_RUN_LOGS", "false"
        )
        send_logs = MagicMock()
        monkeypatch.setattr(observer, "_send_crashed_job_logs", send_logs)
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Pending()
        )

        await self._mark()

        send_logs.assert_not_called()

    async def test_does_not_forward_logs_when_the_crash_was_rejected(
        self,
        mock_orchestration_client,
        propose_state,
        mock_binoculars_client,
        monkeypatch: pytest.MonkeyPatch,
    ):
        send_logs = MagicMock()
        monkeypatch.setattr(observer, "_send_crashed_job_logs", send_logs)
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Pending()
        )
        propose_state.return_value = Running()

        await self._mark()

        send_logs.assert_not_called()


class TestFetchCrashedJobLogs:
    async def test_returns_the_tail_of_the_logs(
        self, mock_binoculars_client, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_FORWARD_CRASHED_RUN_LOGS_TAIL_LINES",
            "1",
        )

        lines = await observer._fetch_crashed_job_logs(
            flow_run_id=FLOW_RUN_ID,
            job_id="job-1",
            namespace="default",
            credentials=ArmadaCredentials(),
        )

        assert lines == ["line two"]

    @pytest.mark.parametrize(
        "status_code,details",
        [
            (grpc.StatusCode.NOT_FOUND, "pod is gone"),
            (grpc.StatusCode.UNAVAILABLE, "connection refused"),
        ],
    )
    async def test_returns_none_when_logs_are_unavailable(
        self,
        mock_binoculars_client,
        status_code: grpc.StatusCode,
        details: str,
    ):
        mock_binoculars_client.logs.side_effect = FakeRpcError(status_code, details)

        lines = await observer._fetch_crashed_job_logs(
            flow_run_id=FLOW_RUN_ID,
            job_id="job-1",
            namespace="default",
            credentials=ArmadaCredentials(),
        )

        assert lines is None


class TestObserverLifecycle:
    async def test_start_and_stop(self):
        observer.start_observer()
        try:
            assert observer._observer_thread is not None
            assert observer._observer_thread.is_alive()
            assert observer._observer_loop is not None
        finally:
            observer.stop_observer()

        assert observer._observer_thread is None
        assert observer._watch_registry == {}

    async def test_start_is_idempotent(self):
        observer.start_observer()
        thread = observer._observer_thread
        try:
            observer.start_observer()
            assert observer._observer_thread is thread
        finally:
            observer.stop_observer()

    async def test_configured_job_sets_are_watched(
        self, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS", "my-queue/my-job-set"
        )
        watched = []

        async def fake_watch(credentials, queue, job_set_id):
            watched.append((queue, job_set_id))

        monkeypatch.setattr(observer, "_watch_job_set", fake_watch)

        observer.start_observer()
        try:
            # Give the observer thread a moment to start its watches
            for _ in range(50):
                if watched:
                    break
                await anyio_sleep(0.05)
        finally:
            observer.stop_observer()

        assert watched == [("my-queue", "my-job-set")]

    async def test_malformed_configured_job_sets_are_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS", "not-a-job-set"
        )

        observer._register_configured_job_sets(ArmadaCredentials())

        assert observer._watch_registry == {}


async def anyio_sleep(seconds: float) -> None:
    import anyio

    await anyio.sleep(seconds)
