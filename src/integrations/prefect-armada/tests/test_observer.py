import asyncio
import threading
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import anyio
import grpc
import pytest
from armada_client.armada import event_pb2
from conftest import FakeEventStream, FakeRpcError, make_event
from prefect_armada import observer
from prefect_armada.credentials import ArmadaCredentials
from prefect_armada.exceptions import ArmadaObserverStartupError

from prefect.client.schemas.objects import FlowRun
from prefect.exceptions import Abort, ObjectNotFound
from prefect.states import (
    Cancelling,
    Completed,
    Crashed,
    Pending,
    Running,
    Scheduled,
)

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
    observer._expected_job_ids.clear()
    observer._persistent_job_sets.clear()
    observer._pending_restarts.clear()
    observer._finishing_watches.clear()
    observer._watch_tasks.clear()
    observer._last_event_cache.clear()
    observer.events_client = None
    observer.orchestration_client = None
    observer._observer_loop = None
    observer._observer_thread = None
    observer._stop_flag = None
    observer._startup_flag = None
    observer._startup_error = None


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


def flow_run_with_state(state, infrastructure_pid=None):
    return FlowRun(
        id=uuid.UUID(FLOW_RUN_ID),
        flow_id=uuid.uuid4(),
        name="my-flow-run-name",
        state=state,
        infrastructure_pid=infrastructure_pid,
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

    def test_records_the_jobs_submitted_to_a_job_set(self):
        credentials = ArmadaCredentials()

        observer.observe_job_set(credentials, "my-queue", "my-job-set", "job-1")
        observer.observe_job_set(credentials, "my-queue", "my-job-set", "job-2")

        assert observer._expected_job_ids == {
            ("my-queue", "my-job-set"): {"job-1", "job-2"}
        }

    def test_registering_a_job_keeps_the_running_watch(self):
        """The running watch waits for the new job, so no restart is needed."""
        credentials = ArmadaCredentials()

        observer.observe_job_set(credentials, "my-queue", "my-job-set", "job-1")
        observer.observe_job_set(credentials, "my-queue", "my-job-set", "job-2")

        assert observer._pending_restarts == set()

    def test_registering_a_job_restarts_a_watch_that_is_ending(self):
        key = ("my-queue", "my-job-set")
        observer.observe_job_set(ArmadaCredentials(), *key, "job-1")
        state = observer._JobSetWatchState()
        state.submitted_job_ids = {"job-1"}
        state.finished_job_ids = {"job-1"}
        assert observer._is_watch_finished(key, state) is True

        observer.observe_job_set(ArmadaCredentials(), *key, "job-2")

        assert observer._pending_restarts == {key}

    def test_a_finished_watch_forgets_its_jobs(self):
        key = ("my-queue", "my-job-set")
        observer.observe_job_set(ArmadaCredentials(), *key, "job-1")

        observer._finalize_watch(key)

        assert observer._watch_registry == {}
        assert observer._expected_job_ids == {}

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
        message.created.FromDatetime(datetime(2026, 7, 29, tzinfo=UTC))

        occurred = observer._event_occurred(message)

        assert occurred == datetime(2026, 7, 29, tzinfo=UTC)

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
            "queue": "my-queue",
            "job_set_id": "my-job-set",
            "submission_order": {},
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

    async def test_does_not_mark_a_requeued_job_as_crashed(
        self, mock_events_client, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Armada may requeue a job whose lease expired, and emits a separate `failed`
        event when it does not.
        """
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        state = observer._JobSetWatchState()
        state.annotations["job-1"] = PREFECT_ANNOTATIONS

        await observer._handle_event(
            make_event("lease_expired", job_id="job-1"),
            "my-queue",
            "my-job-set",
            state,
            ArmadaCredentials(),
        )

        mark_crashed.assert_not_awaited()
        assert state.finished_job_ids == set()

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

    async def test_keeps_watching_a_job_set_through_repeated_disconnects(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """
        A long-running job's stream can drop many times, for example when a load
        balancer closes idle connections, and the watch must outlast all of them.
        """
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        mock_armada_client.get_job_events_stream.side_effect = [
            FakeEventStream(
                [
                    make_event(
                        "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                    ),
                ]
            ),
            # More consecutive failures than the retry limit
            *[RuntimeError("connection reset")] * 5,
            FakeEventStream(
                [make_event("failed", job_id="job-1", message_id="2")], hang=True
            ),
        ]

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        mark_crashed.assert_awaited_once()
        # Reconnects resume after the last handled event rather than replaying
        # the job set's history.
        calls = mock_armada_client.get_job_events_stream.await_args_list
        assert calls[0][1]["from_message_id"] is None
        assert all(call[1]["from_message_id"] == "1" for call in calls[1:])

    async def test_idle_disconnects_are_not_reported_as_failures(
        self,
        mock_events_client,
        mock_armada_client,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ):
        """
        Proxies close streams that have been idle for a while, which must not
        count towards the run of failures that slows reconnects and logs warnings.
        """
        monkeypatch.setattr(observer, "WATCH_STABLE_CONNECTION_SECONDS", 0.01)
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        # Every connection is established, then closed while idle
        mock_armada_client.channel = MagicMock(channel_ready=AsyncMock())

        async def stream_closed_after_idling(events):
            for event in events:
                yield event
            await anyio.sleep(0.02)

        mock_armada_client.get_job_events_stream.side_effect = [
            stream_closed_after_idling(
                [
                    make_event(
                        "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                    )
                ]
            ),
            # More idle disconnects in a row than the retry limit
            *[stream_closed_after_idling([]) for _ in range(5)],
            FakeEventStream(
                [make_event("failed", job_id="job-1", message_id="2")], hang=True
            ),
        ]

        with caplog.at_level("DEBUG", logger="prefect.prefect_armada.observer"):
            await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        mark_crashed.assert_awaited_once()
        assert [
            record.getMessage()
            for record in caplog.records
            if record.levelname == "WARNING"
        ] == []

    async def test_slow_connection_failures_still_count_as_failures(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """
        A connection attempt that hangs and then fails, e.g. to a blackholed host,
        never connected, however long it took.
        """
        monkeypatch.setattr(observer, "WATCH_STABLE_CONNECTION_SECONDS", 0.01)

        async def never_ready():
            await anyio.sleep(3600)

        mock_armada_client.channel = MagicMock(channel_ready=never_ready)

        async def slow_failure():
            await anyio.sleep(0.02)
            raise FakeRpcError(grpc.StatusCode.UNAVAILABLE, "failed to connect")
            yield

        mock_armada_client.get_job_events_stream.side_effect = lambda **_: (
            slow_failure()
        )

        with anyio.fail_after(5):
            await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        # Gave up on the never-visible job set after 3 attempts per `fast_retries`
        assert mock_armada_client.get_job_events_stream.await_count == 3

    async def test_skips_an_event_that_keeps_failing(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """One event that cannot be handled must not stall the job set forever."""
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        handle_event = observer._handle_event

        async def flaky_handle_event(event, *args):
            if event.id == "2":
                raise RuntimeError("Prefect API unavailable")
            await handle_event(event, *args)

        monkeypatch.setattr(observer, "_handle_event", flaky_handle_event)
        running = make_event("running", job_id="job-1", message_id="2")
        mock_armada_client.get_job_events_stream.side_effect = [
            FakeEventStream(
                [
                    make_event(
                        "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                    ),
                    running,
                ]
            ),
            FakeEventStream([running]),
            FakeEventStream(
                [running, make_event("failed", job_id="job-1", message_id="3")],
                hang=True,
            ),
        ]

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        # Skipped after 3 attempts, per the `fast_retries` fixture
        assert mock_armada_client.get_job_events_stream.await_count == 3
        mark_crashed.assert_awaited_once()

    async def test_an_error_handling_an_event_does_not_end_the_watch(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """
        A gRPC error raised while handling an event, e.g. by a call to another
        Armada service, says nothing about whether the job set's stream works.
        """
        handle_event = observer._handle_event

        async def handle_event_failing_on_submitted(event, *args):
            if event.id == "1":
                raise FakeRpcError(grpc.StatusCode.PERMISSION_DENIED, "denied")
            await handle_event(event, *args)

        monkeypatch.setattr(
            observer, "_handle_event", handle_event_failing_on_submitted
        )
        submitted = make_event(
            "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
        )
        mock_armada_client.get_job_events_stream.side_effect = [
            # Not visible yet, so the run of failures is already under way
            FakeRpcError(grpc.StatusCode.NOT_FOUND, "Jobset does not exist"),
            FakeRpcError(grpc.StatusCode.NOT_FOUND, "Jobset does not exist"),
            FakeEventStream([submitted]),
            FakeEventStream([submitted]),
            FakeEventStream(
                [submitted, make_event("succeeded", job_id="job-1", message_id="2")],
                hang=True,
            ),
        ]

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        # The event is skipped after 3 attempts per `fast_retries`, and the watch
        # then finishes normally
        assert mock_armada_client.get_job_events_stream.await_count == 5

    async def test_restarts_a_watch_that_fails_unexpectedly(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """A job registered while a failed watch winds down must still be watched."""
        key = ("my-queue", "my-job-set")
        observer.observe_job_set(ArmadaCredentials(), *key, "job-1")

        def broken_registered_job_ids(key):
            raise RuntimeError("unexpected")

        # Called outside the stream's error handling once the stream ends
        monkeypatch.setattr(observer, "_registered_job_ids", broken_registered_job_ids)
        mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
            [make_event("submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS)]
        )

        await observer._watch_job_set(ArmadaCredentials(), *key)
        observer._finalize_watch(key)

        assert observer._watch_registry == {key: observer._watch_registry[key]}
        assert observer._expected_job_ids == {key: {"job-1"}}

    async def test_gives_up_on_a_job_set_whose_events_have_expired(
        self, mock_events_client, mock_armada_client
    ):
        mock_armada_client.get_job_events_stream.side_effect = [
            FakeEventStream(
                [
                    make_event(
                        "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                    )
                ]
            ),
            *[FakeRpcError(grpc.StatusCode.NOT_FOUND, "Jobset does not exist")] * 5,
        ]

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        # The stream ending and two failed reconnects make the 3 attempts allowed
        # by `fast_retries`
        assert mock_armada_client.get_job_events_stream.await_count == 3

    async def test_keeps_trying_when_a_job_is_submitted_while_failing(
        self, mock_events_client, mock_armada_client
    ):
        """A new submission suggests the job set is about to become visible."""
        calls = 0

        async def get_job_events_stream(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                observer.observe_job_set(
                    ArmadaCredentials(), "my-queue", "my-job-set", "job-2"
                )
            raise FakeRpcError(grpc.StatusCode.NOT_FOUND, "Jobset does not exist")

        mock_armada_client.get_job_events_stream.side_effect = get_job_events_stream

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        # 3 attempts, then another 2 once job-2 is registered, per `fast_retries`
        assert calls == 5
        assert observer._finishing_watches == {("my-queue", "my-job-set")}

    async def test_does_not_give_up_on_a_configured_job_set(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """Nothing would register a configured job set again once dropped."""
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS", "my-queue/my-job-set"
        )
        observer._register_configured_job_sets(ArmadaCredentials())
        mock_armada_client.get_job_events_stream.side_effect = FakeRpcError(
            grpc.StatusCode.NOT_FOUND, "Jobset does not exist"
        )

        with anyio.move_on_after(0.5) as scope:
            await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        assert scope.cancelled_caught, "Expected the watch to still be running"
        assert mock_armada_client.get_job_events_stream.await_count > 3

    async def test_does_not_stop_before_a_registered_job_finishes(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """
        A job set's history is replayed from the start, so a watch can see an
        earlier job finish before it sees a later job being submitted.
        """
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        observer.observe_job_set(ArmadaCredentials(), "my-queue", "my-job-set", "job-2")
        mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
            [
                make_event(
                    "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                ),
                make_event("succeeded", job_id="job-1", message_id="2"),
                make_event(
                    "submitted",
                    job_id="job-2",
                    message_id="3",
                    annotations=PREFECT_ANNOTATIONS,
                ),
                make_event("failed", job_id="job-2", message_id="4"),
            ],
            hang=True,
        )

        await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        mark_crashed.assert_awaited_once()
        assert mark_crashed.await_args[1]["job_id"] == "job-2"

    async def test_configured_job_sets_are_watched_indefinitely(
        self, mock_events_client, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """Nothing re-registers a configured job set, so its watch must not end."""
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS", "my-queue/my-job-set"
        )
        observer._register_configured_job_sets(ArmadaCredentials())
        mark_crashed = AsyncMock()
        monkeypatch.setattr(observer, "_mark_flow_run_as_crashed", mark_crashed)
        mock_armada_client.get_job_events_stream.return_value = FakeEventStream(
            [
                make_event(
                    "submitted", job_id="job-1", annotations=PREFECT_ANNOTATIONS
                ),
                make_event("succeeded", job_id="job-1", message_id="2"),
                make_event(
                    "submitted",
                    job_id="job-2",
                    message_id="3",
                    annotations=PREFECT_ANNOTATIONS,
                ),
                make_event("failed", job_id="job-2", message_id="4"),
            ],
            hang=True,
        )

        with anyio.move_on_after(0.5) as scope:
            await observer._watch_job_set(ArmadaCredentials(), "my-queue", "my-job-set")

        assert scope.cancelled_caught, "Expected the watch to still be running"
        mark_crashed.assert_awaited_once()
        assert mark_crashed.await_args[1]["job_id"] == "job-2"


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

    async def _mark(self, credentials=None, submission_order=None):
        await observer._mark_flow_run_as_crashed(
            flow_run_id=FLOW_RUN_ID,
            job_id="job-1",
            event_type="failed",
            reason="OOMKilled",
            namespace="default",
            credentials=credentials or ArmadaCredentials(),
            queue="my-queue",
            job_set_id="my-job-set",
            submission_order=submission_order or {},
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
        "state",
        [Completed(), Scheduled(), Cancelling()],
        ids=["final", "scheduled", "cancelling"],
    )
    async def test_leaves_final_scheduled_and_cancelling_runs_alone(
        self, mock_orchestration_client, propose_state, state
    ):
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            state
        )

        await self._mark()

        propose_state.assert_not_awaited()

    @pytest.mark.parametrize(
        "state", [Pending(), Running()], ids=["pending", "running"]
    )
    async def test_ignores_a_job_from_an_earlier_attempt(
        self, mock_orchestration_client, propose_state, state
    ):
        """
        A rescheduled flow run is resubmitted into the same job set, whose replayed
        history still holds the earlier job's failure.
        """
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            state, infrastructure_pid="my-queue:my-job-set:job-2"
        )

        await self._mark(submission_order={"job-1": 0, "job-2": 1})

        propose_state.assert_not_awaited()

    @pytest.mark.parametrize(
        "infrastructure_pid",
        ["my-queue:my-job-set:job-2", "my-queue:other-job-set:job-2"],
        ids=["not-seen-yet", "other-job-set"],
    )
    async def test_ignores_a_failure_from_before_the_run_was_resubmitted(
        self, mock_orchestration_client, propose_state, infrastructure_pid
    ):
        """
        Replaying a job set from the start reaches an earlier job's failure before
        the run's current job has been submitted.
        """
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Running(), infrastructure_pid=infrastructure_pid
        )

        await self._mark(submission_order={"job-1": 0})

        propose_state.assert_not_awaited()

    async def test_marks_the_failed_job_as_crashed_when_the_recorded_job_is_older(
        self, mock_orchestration_client, propose_state
    ):
        """
        The worker records a new job's ID after submitting it, and may fail to, so
        a recorded job submitted before the failed one is from an earlier attempt.
        """
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Running(), infrastructure_pid="my-queue:my-job-set:job-0"
        )

        await self._mark(submission_order={"job-0": 0, "job-1": 1})

        propose_state.assert_awaited_once()

    async def test_skips_an_earlier_attempts_failure_without_waiting(
        self,
        mock_orchestration_client,
        propose_state,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Waiting would hold up the job set's later events, such as real failures."""
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_CRASHED_RUN_GRACE_SECONDS", "60"
        )
        fetch_logs = AsyncMock()
        monkeypatch.setattr(observer, "_fetch_crashed_job_logs", fetch_logs)
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Pending(), infrastructure_pid="my-queue:my-job-set:job-2"
        )

        with anyio.fail_after(1):
            await self._mark(submission_order={"job-1": 0, "job-2": 1})

        propose_state.assert_not_awaited()
        fetch_logs.assert_not_awaited()
        mock_orchestration_client.read_flow_run.assert_awaited_once()

    @pytest.mark.parametrize(
        "infrastructure_pid",
        ["my-queue:my-job-set:job-1", "my-queue:etl:nightly:job-1", "12345"],
        ids=["current-job", "job-set-with-colons", "not-an-armada-job"],
    )
    async def test_marks_the_flow_runs_current_job_as_crashed(
        self, mock_orchestration_client, propose_state, infrastructure_pid
    ):
        mock_orchestration_client.read_flow_run.return_value = flow_run_with_state(
            Running(), infrastructure_pid=infrastructure_pid
        )

        await self._mark()

        propose_state.assert_awaited_once()

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

    async def test_restarts_after_client_initialization_fails(
        self, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(observer, "OBSERVER_RESTART_MAX_DELAY_SECONDS", 0.01)
        real_get_events_client = observer.get_events_client
        api_available = threading.Event()
        watched = []

        def flaky_get_events_client():
            if not api_available.is_set():
                raise ConnectionRefusedError("Prefect API is unavailable")
            return real_get_events_client()

        async def fake_watch(credentials, queue, job_set_id):
            watched.append((queue, job_set_id))

        monkeypatch.setattr(observer, "get_events_client", flaky_get_events_client)
        monkeypatch.setattr(observer, "_watch_job_set", fake_watch)

        observer.start_observer()
        try:
            # The failed startup must not leave a dead thread or loop behind
            assert observer._observer_thread.is_alive()
            assert observer._observer_loop is None

            # A job submitted while the observer is down is watched once it is up
            observer.observe_job_set(ArmadaCredentials(), "my-queue", "my-job-set")
            assert watched == []

            api_available.set()
            for _ in range(100):
                if watched:
                    break
                await anyio_sleep(0.05)
        finally:
            observer.stop_observer()

        assert watched == [("my-queue", "my-job-set")]

    async def test_a_restarted_observer_still_watches_in_flight_job_sets(
        self, mock_armada_client, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Stopping the observer's main loop after a failure cancels its watches, and
        the restarted loop must pick their job sets up again.
        """
        key = ("my-queue", "my-job-set")
        started = []

        async def fake_watch(credentials, queue, job_set_id):
            started.append((queue, job_set_id))
            await anyio.sleep(3600)

        monkeypatch.setattr(observer, "_watch_job_set", fake_watch)
        observer.observe_job_set(ArmadaCredentials(), *key, "job-1")
        stop_flag = threading.Event()

        for run in range(1, 3):
            main = asyncio.create_task(observer._observer_main(stop_flag))
            for _ in range(200):
                if len(started) == run:
                    break
                await anyio_sleep(0.01)
            # Ending the main loop runs the same cleanup as a failure does
            main.cancel()
            await asyncio.gather(main, return_exceptions=True)

        assert started == [key, key]
        assert observer._expected_job_ids == {key: {"job-1"}}

    @pytest.mark.parametrize(
        "started_first",
        [True, False],
        ids=["after-starting", "after-start-observer-stopped-waiting"],
    )
    async def test_restarts_after_a_permanent_failure_no_one_is_waiting_for(
        self, monkeypatch: pytest.MonkeyPatch, started_first
    ):
        """
        Only a waiting `start_observer` can report a startup failure, so any later
        failure must be retried rather than silently end the observer.
        """
        monkeypatch.setattr(observer, "OBSERVER_RESTART_MAX_DELAY_SECONDS", 0.01)
        monkeypatch.setattr(observer, "OBSERVER_STARTUP_TIMEOUT_SECONDS", 0.1)
        start_observer_returned = threading.Event()
        restarted = threading.Event()
        calls = 0

        async def fake_observer_main(stop_flag, started=None):
            nonlocal calls
            calls += 1
            if calls > 1:
                restarted.set()
                return
            if started_first:
                if started is not None:
                    started.set()
                observer._startup_flag.set()
            start_observer_returned.wait(timeout=5)
            # Not one of the transient failures the observer expects
            raise RuntimeError("Permanent failure")

        monkeypatch.setattr(observer, "_observer_main", fake_observer_main)

        observer.start_observer()
        try:
            start_observer_returned.set()
            assert await anyio.to_thread.run_sync(restarted.wait, 5)
        finally:
            observer.stop_observer()

    async def test_stops_while_waiting_to_restart(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def broken_get_events_client():
            raise ConnectionRefusedError("Prefect API is unavailable")

        monkeypatch.setattr(observer, "get_events_client", broken_get_events_client)

        observer.start_observer()
        thread = observer._observer_thread
        observer.stop_observer()

        assert not thread.is_alive()
        assert observer._observer_thread is None

    async def test_raises_when_startup_fails_permanently(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def broken_get_events_client():
            raise ValueError("bad credentials")

        monkeypatch.setattr(observer, "get_events_client", broken_get_events_client)

        with pytest.raises(
            ArmadaObserverStartupError, match="bad credentials"
        ) as exc_info:
            observer.start_observer()

        assert isinstance(exc_info.value.__cause__, ValueError)
        assert observer._observer_thread is None
        assert observer._observer_loop is None

    async def test_can_start_after_a_permanent_startup_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        with monkeypatch.context() as patch:
            patch.setattr(
                observer, "get_events_client", MagicMock(side_effect=ValueError("bad"))
            )
            with pytest.raises(ArmadaObserverStartupError):
                observer.start_observer()

        observer.start_observer()
        try:
            assert observer._observer_loop is not None
        finally:
            observer.stop_observer()

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
