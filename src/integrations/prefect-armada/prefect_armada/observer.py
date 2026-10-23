"""
Module containing the Armada observer, which watches Armada job set events on
behalf of Prefect.

Armada is asynchronous: a worker submits a job and Armada schedules it onto one
of its Kubernetes clusters at some later point. The observer keeps Prefect in
sync with what Armada does with those jobs by

- replicating Armada job events into Prefect's event system, where they can be
  used by Automations, and
- marking a flow run as `Crashed` when its Armada job fails before the flow run
  is able to report its own state (for example a bad image or a missing
  dependency).

Armada only exposes events per job set, so the observer watches the job sets that
this process submits to. Additional job sets can be watched by setting
`PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS` to a comma-separated list of
`<queue>/<job_set_id>` entries.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections.abc import Mapping
from contextlib import aclosing
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import grpc
import httpx
from anyio.to_thread import run_sync
from armada_client.event import Event as ArmadaEvent
from cachetools import TTLCache
from websockets.exceptions import ConnectionClosed

from prefect import __version__, get_client
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
from prefect.context import SettingsContext, get_settings_context
from prefect.events import Event, RelatedResource
from prefect.events.clients import EventsClient, get_events_client
from prefect.events.schemas.events import Resource
from prefect.exceptions import Abort, ObjectNotFound
from prefect.logging.loggers import flow_run_logger, get_logger
from prefect.settings import get_current_settings
from prefect.states import Crashed
from prefect.utilities.engine import propose_state
from prefect.utilities.slugify import slugify
from prefect_armada.credentials import ArmadaCredentials
from prefect_armada.events import _stream_job_set_events
from prefect_armada.exceptions import (
    ArmadaObserverStartupError,
    rpc_details,
    rpc_status_code,
)
from prefect_armada.settings import ArmadaSettings
from prefect_armada.utilities import UNSUCCESSFUL_EVENT_TYPES, parse_job_pid

logger = get_logger("prefect_armada.observer")

# Armada event types after which a job will never run again.
TERMINAL_EVENT_TYPES = {"succeeded", "failed", "cancelled", "preempted"}

# How many consecutive failures a job set's watch tolerates before giving up on
# a job set that has never become visible or that fails permanently, and before
# skipping an event it cannot handle; and the ceiling on the exponential backoff
# between attempts. Eight attempts with this backoff spans a little over two
# minutes. Any other failure is retried until every job in the job set has
# finished, so that a long-running job outlasts dropped connections.
WATCH_RETRY_MAX_ATTEMPTS = 8
WATCH_RETRY_MAX_DELAY_SECONDS = 30

# How long a job set's event stream must stay connected before it ending, cleanly
# or not, counts as a dropped connection rather than a failed one. Proxies and load
# balancers routinely close streams that have been idle for a while, which must
# not slow down reconnecting or be reported as a failure.
WATCH_STABLE_CONNECTION_SECONDS = 30

# Errors from a job set's event stream that retrying will not fix. Armada reports
# NOT_FOUND both before a new job set becomes visible and after an old one's
# events have expired.
_PERMANENT_STREAM_ERRORS = {
    grpc.StatusCode.NOT_FOUND,
    grpc.StatusCode.PERMISSION_DENIED,
    grpc.StatusCode.UNAUTHENTICATED,
}

# How long `start_observer` waits for the observer's first startup attempt.
OBSERVER_STARTUP_TIMEOUT_SECONDS = 30

# The ceiling on the exponential backoff between attempts to restart the
# observer after it fails, for example because the Prefect API is unreachable.
OBSERVER_RESTART_MAX_DELAY_SECONDS = 30

# Failures the observer expects to clear on their own, such as the Prefect API
# being unreachable. Anything else (bad credentials, invalid settings) is
# treated as permanent, mirroring how Prefect's events client classifies them.
_TRANSIENT_STARTUP_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionClosed,
    TimeoutError,
    OSError,
    httpx.TransportError,
)

# Cache used to keep track of the last event for a job. This is used to populate
# the `follows` field on events to get correct event ordering. We only hold each
# job's last event for 5 minutes to avoid holding onto too much memory, and 5
# minutes is the same as the `TIGHT_TIMING` in `prefect.events.utilities`.
_last_event_cache: TTLCache[str, Event] = TTLCache(maxsize=1000, ttl=60 * 5)

events_client: EventsClient | None = None
orchestration_client: PrefectClient | None = None

_JobSetKey = tuple[str, str]

_registry_lock = threading.Lock()
_watch_registry: dict[_JobSetKey, ArmadaCredentials] = {}
# The jobs this process submitted to each watched job set. A watch does not end
# until all of them have finished, even if every job it has seen so far has.
_expected_job_ids: dict[_JobSetKey, set[str]] = {}
# Job sets configured via settings. Nothing re-registers them when more jobs are
# submitted, so their watches never end.
_persistent_job_sets: set[_JobSetKey] = set()
_pending_restarts: set[_JobSetKey] = set()
# Job sets whose watch has decided to end but has not been cleaned up yet. A job
# registered for one of these needs a new watch rather than the current one.
_finishing_watches: set[_JobSetKey] = set()
_watch_tasks: dict[_JobSetKey, asyncio.Task[None]] = {}

_observer_thread: threading.Thread | None = None
_observer_loop: asyncio.AbstractEventLoop | None = None
_stop_flag: threading.Event | None = None
# Set once the observer's first startup attempt has finished, whether or not it
# succeeded; `_observer_loop` is only set while the observer is running.
_startup_flag: threading.Event | None = None
# The permanent failure that made the observer give up on its first startup.
_startup_error: Exception | None = None
# Guards the hand-off of a startup failure to `start_observer`, so that one is
# only recorded while `start_observer` is still waiting to read it.
_startup_lock = threading.Lock()


class _JobSetWatchState:
    """Tracks what the observer knows about the jobs in a job set."""

    def __init__(self) -> None:
        self.annotations: dict[str, dict[str, str]] = {}
        self.submitted_job_ids: set[str] = set()
        self.finished_job_ids: set[str] = set()
        # The order in which jobs were submitted to the job set, as the position
        # of each job's `submitted` event in the stream.
        self.submission_order: dict[str, int] = {}

    @property
    def is_finished(self) -> bool:
        """Whether every job seen in this job set has reached a terminal event."""
        return bool(self.submitted_job_ids) and self.submitted_job_ids.issubset(
            self.finished_job_ids
        )


def _is_watch_finished(key: _JobSetKey, state: _JobSetWatchState) -> bool:
    """
    Whether a job set's watch can end.

    Armada replays a job set's history from the start, so a restarted watch can
    see an earlier job finish before it sees a later job being submitted. Every
    job seen so far having finished is therefore not enough on its own; the jobs
    this process submitted must have finished too.
    """
    with _registry_lock:
        if key in _persistent_job_sets:
            return False
        expected_job_ids = _expected_job_ids.get(key, set())
        finished = state.is_finished and expected_job_ids.issubset(
            state.finished_job_ids
        )
        if finished:
            # Decided under the lock so that `observe_job_set` either adds its
            # job before this check or sees that the watch is ending.
            _finishing_watches.add(key)
        return finished


def _registered_job_ids(key: _JobSetKey) -> set[str]:
    """Returns the jobs registered for a job set so far."""
    with _registry_lock:
        return set(_expected_job_ids.get(key, ()))


def _try_end_watch(key: _JobSetKey, known_job_ids: set[str]) -> bool:
    """
    Marks a failing watch as ending, unless a job was registered for its job set
    since `known_job_ids` was read.

    A newly submitted job is a reason to keep trying, and checking for one under
    the lock means `observe_job_set` either registers its job before this check
    or sees that the watch is ending and queues a restart.
    """
    with _registry_lock:
        if not _expected_job_ids.get(key, set()).issubset(known_job_ids):
            return False
        _finishing_watches.add(key)
        return True


def observe_job_set(
    credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    job_id: str | None = None,
) -> None:
    """
    Registers an Armada job set to be watched by the observer.

    Safe to call from any thread and safe to call repeatedly for the same job
    set. A running watch keeps going until `job_id` has finished; a job set is
    only re-watched if its current watch is already ending, or if no `job_id` is
    given.

    Args:
        credentials: The credentials used to connect to Armada.
        queue: The name of the Armada queue the job set was submitted to.
        job_set_id: The name of the Armada job set to watch.
        job_id: The ID of the job just submitted to the job set, if any. The
            job set is watched until this job has finished.
    """
    key = (queue, job_set_id)
    with _registry_lock:
        already_watching = key in _watch_registry
        _watch_registry[key] = credentials
        if job_id:
            _expected_job_ids.setdefault(key, set()).add(job_id)
        if already_watching and (not job_id or key in _finishing_watches):
            _pending_restarts.add(key)

    loop = _observer_loop
    if loop is None or already_watching:
        # Either the observer has not started yet, in which case it will pick up
        # the registry when it does, or a watch is already running.
        return

    asyncio.run_coroutine_threadsafe(_ensure_watch(key), loop)


async def _ensure_watch(key: _JobSetKey) -> None:
    """Starts a watch for a job set if one is not already running."""
    if key in _watch_tasks:
        return

    with _registry_lock:
        credentials = _watch_registry.get(key)
    if credentials is None:
        return

    queue, job_set_id = key
    task = asyncio.create_task(_watch_job_set(credentials, queue, job_set_id))
    _watch_tasks[key] = task
    task.add_done_callback(lambda task: _finalize_watch(key, task.cancelled()))


def _finalize_watch(key: _JobSetKey, cancelled: bool = False) -> None:
    """
    Cleans up after a job set watch has ended, restarting it if needed.

    A watch is only cancelled when the observer stops. If the observer is
    restarting after a failure, it watches every registered job set again, so a
    cancelled watch's job set stays registered; `stop_observer` clears the
    registry when the observer stops for good.
    """
    _watch_tasks.pop(key, None)
    with _registry_lock:
        restart = key in _pending_restarts
        _pending_restarts.discard(key)
        _finishing_watches.discard(key)
        if cancelled:
            return
        if not restart:
            _watch_registry.pop(key, None)
            _expected_job_ids.pop(key, None)
            _persistent_job_sets.discard(key)

    if restart and _observer_loop is not None:
        asyncio.run_coroutine_threadsafe(_ensure_watch(key), _observer_loop)


async def _watch_job_set(
    credentials: ArmadaCredentials, queue: str, job_set_id: str
) -> None:
    """
    Watches an Armada job set until every job in it has finished, restarting the
    watch if it fails unexpectedly.

    The job set stays registered across the restart, so that no job registered
    in the meantime goes unwatched, and the restart waits for the longest retry
    delay so that a failure that recurs does not restart in a tight loop.
    """
    try:
        await _watch_job_set_events(credentials, queue, job_set_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Watching Armada job set %r in queue %r failed unexpectedly; "
            "restarting in %ss",
            job_set_id,
            queue,
            WATCH_RETRY_MAX_DELAY_SECONDS,
        )
        await asyncio.sleep(WATCH_RETRY_MAX_DELAY_SECONDS)
        with _registry_lock:
            _pending_restarts.add((queue, job_set_id))


async def _watch_job_set_events(
    credentials: ArmadaCredentials, queue: str, job_set_id: str
) -> None:
    """
    Watches an Armada job set's event stream until every job in it has finished.

    Armada replays a job set's history from the beginning of the stream, so a
    watch that is restarted will see events it has already handled. Replicated
    Prefect events use deterministic IDs so that the replay is deduplicated by
    Prefect's event system rather than producing duplicates. Within a watch,
    reconnects resume after the last handled event instead.
    """
    logger.debug("Watching Armada job set %r in queue %r", job_set_id, queue)
    key = (queue, job_set_id)
    state = _JobSetWatchState()
    # The jobs registered when the current run of failures began.
    known_job_ids: set[str] = set()
    last_message_id: str | None = None
    job_set_seen = False
    # Consecutive connections that ended soon after opening without handling a
    # new event.
    failures = 0
    # An event that could not be handled, and how many times in a row it failed.
    failing_message_id: str | None = None
    event_failures = 0

    while True:
        error: Exception | None = None
        # Set when the error came from handling an event rather than from the
        # stream, which says nothing about whether the stream itself works.
        handling_error: Exception | None = None
        # When the connection was established, which a connection attempt that
        # hangs and then fails never reaches.
        connected_at: float | None = None

        def mark_connected() -> None:
            nonlocal connected_at
            connected_at = time.monotonic()

        try:
            async with aclosing(
                _stream_job_set_events(
                    armada_credentials=credentials,
                    queue=queue,
                    job_set_id=job_set_id,
                    from_message_id=last_message_id,
                    on_connected=mark_connected,
                )
            ) as event_stream:
                async for event in event_stream:
                    job_set_seen = True
                    try:
                        await _handle_event(
                            event, queue, job_set_id, state, credentials
                        )
                    except Exception as exc:
                        if event.id == failing_message_id:
                            event_failures += 1
                        else:
                            failing_message_id, event_failures = event.id, 1
                        if event_failures < WATCH_RETRY_MAX_ATTEMPTS:
                            # Reconnecting delivers the event again.
                            handling_error = exc
                            raise
                        # Retrying an event that keeps failing would stall the
                        # job set's later events indefinitely.
                        logger.warning(
                            "Skipping Armada %s event for job %s in job set %r "
                            "after %s failed attempts to handle it",
                            event.type.value,
                            getattr(event.message, "job_id", ""),
                            job_set_id,
                            event_failures,
                            exc_info=True,
                        )
                    # Only advance once the event is handled, so an event whose
                    # handling failed is delivered again after reconnecting.
                    last_message_id = event.id or last_message_id
                    failures = 0
                    if _is_watch_finished(key, state):
                        logger.debug(
                            "Finished watching Armada job set %r in queue %r",
                            job_set_id,
                            queue,
                        )
                        return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = exc

        if (
            connected_at is not None
            and time.monotonic() - connected_at >= WATCH_STABLE_CONNECTION_SECONDS
        ):
            # The stream was healthy until it was closed, so this is the first
            # attempt to reconnect rather than another failure in a row.
            failures = 0
        failures += 1
        if failures == 1:
            known_job_ids = _registered_job_ids(key)
        stream_error = None if error is handling_error else error
        if failures >= WATCH_RETRY_MAX_ATTEMPTS and _should_give_up(
            key, job_set_seen, stream_error
        ):
            if _try_end_watch(key, known_job_ids):
                logger.warning(
                    "Giving up watching Armada job set %r in queue %r after %s "
                    "attempts",
                    job_set_id,
                    queue,
                    failures,
                    exc_info=error,
                )
                return
            # A job was just submitted to the job set, so start counting again.
            known_job_ids = _registered_job_ids(key)
            failures = 1

        delay = min(2 ** (failures - 1), WATCH_RETRY_MAX_DELAY_SECONDS)
        log = logger.warning if failures == WATCH_RETRY_MAX_ATTEMPTS else logger.debug
        if error is None:
            # The stream ended without the job set finishing, e.g. Armada or a
            # proxy closed it.
            log(
                "Event stream for Armada job set %r in queue %r ended; "
                "reconnecting in %ss",
                job_set_id,
                queue,
                delay,
            )
        else:
            log(
                "Error watching Armada job set %r in queue %r (%s); retrying in %ss",
                job_set_id,
                queue,
                error,
                delay,
            )
        await asyncio.sleep(delay)


def _should_give_up(
    key: _JobSetKey, job_set_seen: bool, error: Exception | None
) -> bool:
    """
    Whether a watch that keeps failing should stop.

    A watch usually starts moments after the job set's first job is submitted,
    before Armada has made the job set visible, so its first attempts routinely
    fail with NOT_FOUND. A job set that never becomes visible is given up on, as
    is one whose stream fails permanently, for example because its events have
    expired. Anything else is retried, because giving up would leave unfinished
    jobs unobserved. Configured job sets are never given up on, since nothing
    would register them again.
    """
    with _registry_lock:
        if key in _persistent_job_sets:
            return False
    if not job_set_seen:
        return True
    return error is not None and rpc_status_code(error) in _PERMANENT_STREAM_ERRORS


async def _handle_event(
    event: ArmadaEvent,
    queue: str,
    job_set_id: str,
    state: _JobSetWatchState,
    credentials: ArmadaCredentials,
) -> None:
    """Handles a single Armada job event."""
    settings = ArmadaSettings()
    event_type = event.type.value
    message = event.message
    job_id = getattr(message, "job_id", "") or ""
    if not job_id:
        return

    if event_type == "submitted":
        state.submitted_job_ids.add(job_id)
        state.submission_order.setdefault(job_id, len(state.submission_order))
        state.annotations[job_id] = dict(getattr(message.job, "annotations", {}) or {})

    if event_type in TERMINAL_EVENT_TYPES:
        # A job set may have been submitted to before this watch started, so
        # every job that reaches a terminal event counts as one we have seen.
        state.submitted_job_ids.add(job_id)
        state.finished_job_ids.add(job_id)

    annotations = state.annotations.get(job_id, {})
    flow_run_id = annotations.get("prefect.io/flow-run-id")
    if not flow_run_id:
        # Not a job submitted by Prefect, or its submitted event predates this
        # stream's history.
        return

    if settings.observer.replicate_job_events:
        await _replicate_job_event(
            event=event,
            queue=queue,
            job_set_id=job_set_id,
            annotations=annotations,
        )

    if event_type in UNSUCCESSFUL_EVENT_TYPES:
        await _mark_flow_run_as_crashed(
            flow_run_id=flow_run_id,
            job_id=job_id,
            event_type=event_type,
            reason=getattr(message, "reason", "") or "",
            namespace=getattr(message, "pod_namespace", "") or "default",
            credentials=credentials,
            queue=queue,
            job_set_id=job_set_id,
            submission_order=state.submission_order,
        )


def _event_occurred(message: Any) -> datetime | None:
    """Returns the time an Armada event occurred, if it reports one."""
    created = getattr(message, "created", None)
    if created is None:
        return None
    try:
        # An unset protobuf timestamp reads as the Unix epoch, which would be a
        # misleading `occurred` time.
        if not message.HasField("created"):
            return None
    except (AttributeError, ValueError):
        pass
    try:
        if isinstance(created, datetime):
            occurred = created
        else:
            occurred = created.ToDatetime()
    except (AttributeError, ValueError):
        return None
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    return occurred


async def _replicate_job_event(
    event: ArmadaEvent,
    queue: str,
    job_set_id: str,
    annotations: dict[str, str],
) -> None:
    """
    Replicates an Armada job event to the Prefect event system.

    This handler is resilient to restarts of the observer and allows multiple
    instances of the observer to coexist without duplicate events.
    """
    if events_client is None:
        raise RuntimeError("Events client not initialized")

    message = event.message
    job_id = message.job_id
    event_type = event.type.value

    # Create a deterministic event ID based on the Armada job and the message
    # that produced the event. Armada message IDs are stable across replays of a
    # job set's event stream, so Prefect's event system can deduplicate a replay.
    event_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        json.dumps(
            {"job_id": job_id, "type": event_type, "message_id": event.id},
            sort_keys=True,
        ),
    )

    resource: dict[str, str] = {
        "prefect.resource.id": f"prefect.armada.job.{job_id}",
        "prefect.resource.name": job_id,
        "armada.queue": queue,
        "armada.job-set-id": job_set_id,
    }
    if namespace := getattr(message, "pod_namespace", ""):
        resource["kubernetes.namespace"] = namespace
    if cluster_id := getattr(message, "cluster_id", ""):
        resource["armada.cluster-id"] = cluster_id
    if reason := getattr(message, "reason", ""):
        resource["armada.reason"] = reason

    occurred = _event_occurred(message)

    prefect_event = Event(
        event=f"prefect.armada.job.{event_type}",
        resource=Resource.model_validate(resource),
        id=event_id,
        related=_related_resources_from_annotations(annotations),
        **({"occurred": occurred} if occurred else {}),
    )

    # This check replicates a similar check in `emit_event` in
    # `prefect.events.utilities`
    if ((prev_event := _last_event_cache.get(job_id)) is not None) and (
        -timedelta(minutes=5)
        < (prefect_event.occurred - prev_event.occurred)
        < timedelta(minutes=5)
    ):
        prefect_event.follows = prev_event.id

    await events_client.emit(event=prefect_event)
    _last_event_cache[job_id] = prefect_event


def _related_resources_from_annotations(
    annotations: dict[str, str],
) -> list[RelatedResource]:
    """Convert Prefect job annotations to related resources"""
    related: list[RelatedResource] = []
    if flow_run_id := annotations.get("prefect.io/flow-run-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": annotations.get(
                        "prefect.io/flow-run-name"
                    ),
                }
            )
        )
    if deployment_id := annotations.get("prefect.io/deployment-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.deployment.{deployment_id}",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": annotations.get(
                        "prefect.io/deployment-name"
                    ),
                }
            )
        )
    if flow_id := annotations.get("prefect.io/flow-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow.{flow_id}",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": annotations.get("prefect.io/flow-name"),
                }
            )
        )
    if work_pool_id := annotations.get("prefect.io/work-pool-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool_id}",
                    "prefect.resource.role": "work-pool",
                    "prefect.resource.name": annotations.get(
                        "prefect.io/work-pool-name"
                    ),
                }
            )
        )
    if worker_name := annotations.get("prefect.io/worker-name"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.worker.armada.{slugify(worker_name)}",
                    "prefect.resource.role": "worker",
                    "prefect.resource.name": worker_name,
                    "prefect.worker-type": "armada",
                    "prefect.version": __version__,
                }
            )
        )
    return related


def _is_superseded(
    flow_run: FlowRun,
    queue: str,
    job_set_id: str,
    job_id: str,
    submission_order: Mapping[str, int],
) -> bool:
    """
    Whether a flow run has moved on from an Armada job to a newer one.

    A rescheduled flow run is resubmitted into the same job set, whose replayed
    history still holds the failures of its earlier jobs, so a failure only
    belongs to the run if the job is the one its worker last recorded. The
    recorded job can also be stale: the worker records a new job's ID moments
    after submitting it, and may fail to record it at all. A recorded job that
    was submitted before the failed one is therefore an earlier attempt, and the
    failed job is the current one.
    """
    if not flow_run.infrastructure_pid:
        return False
    try:
        current_queue, current_job_set_id, current_job_id = parse_job_pid(
            flow_run.infrastructure_pid
        )
    except ValueError:
        # Not an Armada job, e.g. the run last ran on other infrastructure.
        return False
    if current_job_id == job_id:
        return False
    if (current_queue, current_job_set_id) != (queue, job_set_id):
        # The run was last submitted to another job set, which only happens when
        # its job set changed between attempts, so this failure is from before.
        return True

    current_position = submission_order.get(current_job_id)
    failed_position = submission_order.get(job_id)
    if current_position is None or failed_position is None:
        # A job not seen yet is one submitted after the events handled so far.
        return True
    return current_position > failed_position


async def _mark_flow_run_as_crashed(
    flow_run_id: str,
    job_id: str,
    event_type: str,
    reason: str,
    namespace: str,
    credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    submission_order: Mapping[str, int],
) -> None:
    """
    Marks a flow run as crashed if its Armada job did not run to completion.
    """
    if orchestration_client is None:
        raise RuntimeError("Orchestration client not initialized")

    settings = ArmadaSettings()

    try:
        flow_run = await orchestration_client.read_flow_run(
            flow_run_id=uuid.UUID(flow_run_id)
        )
    except ObjectNotFound:
        logger.debug("Flow run %s not found, skipping", flow_run_id)
        return

    assert flow_run.state is not None, "Expected flow run state to be set"

    def is_superseded() -> bool:
        superseded = _is_superseded(
            flow_run, queue, job_set_id, job_id, submission_order
        )
        if superseded:
            logger.debug(
                "Armada job %s is not flow run %s's current job (%s), skipping",
                job_id,
                flow_run_id,
                flow_run.infrastructure_pid,
            )
        return superseded

    # Exit early for final, scheduled and paused runs, and for runs being
    # cancelled: cancelling a run cancels its Armada job, and the worker marks
    # the run Cancelled, which a Crashed proposal would race.
    if (
        flow_run.state.is_final()
        or flow_run.state.is_scheduled()
        or flow_run.state.is_paused()
        or flow_run.state.is_cancelling()
    ):
        logger.debug(
            "Flow run %s is in a final, scheduled, paused, or cancelling state, "
            "skipping",
            flow_run_id,
        )
        return

    # Checked before fetching logs and waiting, so that replaying an earlier
    # attempt's failure does not hold up the job set's later events.
    if is_superseded():
        return

    # Eagerly fetch job logs while the flow run is still in a pre-connectivity
    # state. Armada's log service can only serve logs while the job's pod
    # exists, which may no longer be true by the time the wait below finishes.
    captured_logs: list[str] | None = None
    if flow_run.state.is_pending() and settings.observer.forward_crashed_run_logs:
        captured_logs = await _fetch_crashed_job_logs(
            flow_run_id=flow_run_id,
            job_id=job_id,
            namespace=namespace,
            credentials=credentials,
        )

    # A flow run that has started reports its own state, so give a pending run a
    # chance to do so before declaring it crashed.
    with anyio.move_on_after(settings.observer.crashed_run_grace_seconds):
        while flow_run.state is not None and flow_run.state.is_pending():
            await anyio.sleep(5)
            flow_run = await orchestration_client.read_flow_run(
                flow_run_id=uuid.UUID(flow_run_id)
            )

    assert flow_run.state is not None, "Expected flow run state to be set"
    if flow_run.state.is_final() or flow_run.state.is_cancelling():
        logger.debug(
            "Flow run %s reached a final or cancelling state on its own, skipping",
            flow_run_id,
        )
        return

    # The run may have been rescheduled and resubmitted during the wait.
    if is_superseded():
        return

    message = f"Armada job {job_id} for this flow run {event_type}"
    if reason:
        message += f": {reason}"

    logger.warning(
        "Armada job %s %s and flow run %s has not reported a final state, "
        "marking as crashed",
        job_id,
        event_type,
        flow_run_id,
    )

    # A concurrent transition (another worker replica or an API call) may move
    # the run to a terminal state between our checks and this proposal, in which
    # case the server rejects the Crashed transition with an Abort.
    try:
        result_state = await propose_state(
            client=orchestration_client,
            state=Crashed(message=message),
            flow_run_id=uuid.UUID(flow_run_id),
        )
    except Abort:
        logger.debug(
            "Crash proposal for flow run %s aborted; run is already terminal",
            flow_run_id,
            exc_info=True,
        )
        return

    # Only forward job logs if the crash transition was accepted. If the run
    # advanced beyond Pending during the wait loop, `propose_state` will be
    # rejected and we must not attach stale crash logs to a live run.
    if captured_logs and result_state.is_crashed():
        _send_crashed_job_logs(
            flow_run_id=flow_run_id, job_id=job_id, lines=captured_logs
        )


def _read_job_log_lines(
    credentials: ArmadaCredentials, job_id: str, namespace: str
) -> list[str]:
    """Reads the log lines for an Armada job using a synchronous client."""
    with credentials.get_binoculars_client() as binoculars_client:
        response = binoculars_client.logs(
            job_id=job_id,
            since_time="",
            pod_namespace=namespace,
        )
    return [line.line for line in response.log if line.line.strip()]


async def _fetch_crashed_job_logs(
    flow_run_id: str,
    job_id: str,
    namespace: str,
    credentials: ArmadaCredentials,
) -> list[str] | None:
    """Fetches the tail of an Armada job's logs, if they are still available."""
    settings = ArmadaSettings()

    # Logs are a best-effort addition to the crash report. Binoculars rejects the
    # request once the job's pod is gone (NOT_FOUND) and is unreachable when it
    # is not deployed alongside Armada (UNAVAILABLE), neither of which should
    # stop the flow run from being marked as crashed.
    try:
        lines = await run_sync(_read_job_log_lines, credentials, job_id, namespace)
    except grpc.RpcError as exc:
        logger.debug(
            "Could not fetch logs for Armada job %s of flow run %s: %s %s",
            job_id,
            flow_run_id,
            rpc_status_code(exc),
            rpc_details(exc),
        )
        return None

    if not lines:
        return None

    return lines[-settings.observer.forward_crashed_run_logs_tail_lines :]


def _send_crashed_job_logs(flow_run_id: str, job_id: str, lines: list[str]) -> None:
    """Forward previously-fetched job logs as individual flow-run log entries."""
    max_size = get_current_settings().logging.to_api.max_log_size
    fr_logger = flow_run_logger(flow_run_id=uuid.UUID(flow_run_id)).getChild("observer")

    fr_logger.error(f"Logs from Armada job {job_id!r}:")
    for line in lines:
        if len(line) > max_size:
            line = line[: max_size - len("... [truncated]")] + "... [truncated]"
        fr_logger.error(line)


def _register_configured_job_sets(credentials: ArmadaCredentials) -> None:
    """Registers the job sets configured via settings for watching."""
    for entry in ArmadaSettings().observer.job_sets or set():
        queue, _, job_set_id = entry.partition("/")
        if not queue or not job_set_id:
            logger.warning(
                "Ignoring malformed observer job set %r; expected "
                "'<queue>/<job_set_id>'",
                entry,
            )
            continue
        with _registry_lock:
            _watch_registry.setdefault((queue, job_set_id), credentials)
            _persistent_job_sets.add((queue, job_set_id))


async def _observer_main(
    stop_flag: threading.Event, started: threading.Event | None = None
) -> None:
    """
    Runs the observer until it is stopped.

    Args:
        stop_flag: Set to stop the observer.
        started: Set once the observer is running and watching its job sets.
    """
    global _observer_loop
    global events_client
    global orchestration_client

    logger.info("Initializing clients")
    async with get_client() as prefect_client, get_events_client() as prefect_events:
        orchestration_client = prefect_client
        events_client = prefect_events
        logger.info("Clients successfully initialized")

        try:
            _register_configured_job_sets(ArmadaCredentials())

            # Publishing the loop is what tells `observe_job_set` the observer
            # is running, so it must happen before the registry is read to
            # avoid missing a job set registered in between.
            _observer_loop = asyncio.get_running_loop()

            with _registry_lock:
                keys = list(_watch_registry)
            for key in keys:
                await _ensure_watch(key)

            if started is not None:
                started.set()
            if _startup_flag is not None:
                _startup_flag.set()

            while not stop_flag.is_set():
                await asyncio.sleep(0.5)
        finally:
            _observer_loop = None
            tasks = list(_watch_tasks.values())
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            _watch_tasks.clear()
            orchestration_client = None
            events_client = None


def _observer_thread_entry(
    settings_context: SettingsContext, stop_flag: threading.Event
) -> None:
    """
    Entrypoint for the observer thread.

    Runs the observer until it is stopped, restarting it if it fails. Jobs that
    never reach the Prefect API can only report their failure through the
    observer, so a failure here (most likely an unreachable Prefect API) must
    not leave the worker submitting jobs with nothing watching them.

    The exception is a first startup that fails for a reason retrying will not
    fix while `start_observer` is still waiting for it. That is recorded for
    `start_observer` to raise, so the worker refuses to start rather than run
    without an observer indefinitely. Any other failure, including a permanent
    one after the observer has started or after `start_observer` has stopped
    waiting, is logged and retried, since nothing else would report it.
    """
    global _startup_error

    failures = 0
    ever_started = False
    try:
        # Prefect settings live in a context variable, which a new thread does
        # not inherit, so the starting thread's settings are re-applied here to
        # ensure the observer talks to the same Prefect API as its worker. A
        # context object can only be entered once, so a new one is built from
        # the captured profile and settings.
        with SettingsContext(
            profile=settings_context.profile, settings=settings_context.settings
        ):
            while not stop_flag.is_set():
                started = threading.Event()
                try:
                    asyncio.run(_observer_main(stop_flag, started))
                except Exception as exc:
                    if started.is_set():
                        # The observer had been running, so this failure starts
                        # a new run of restarts rather than continuing one.
                        ever_started = True
                        failures = 0
                    with _startup_lock:
                        report = (
                            not ever_started
                            and _startup_flag is not None
                            and not isinstance(exc, _TRANSIENT_STARTUP_EXCEPTIONS)
                        )
                        if report:
                            _startup_error = exc
                    if report:
                        return
                    delay = min(2**failures, OBSERVER_RESTART_MAX_DELAY_SECONDS)
                    failures += 1
                    logger.exception(
                        "Armada observer stopped unexpectedly; restarting in %s "
                        "seconds",
                        delay,
                    )
                    # Unblock a caller waiting on startup; `_observer_loop`
                    # tells it that the observer is not actually running.
                    if _startup_flag is not None:
                        _startup_flag.set()
                    stop_flag.wait(delay)
    finally:
        if _startup_flag is not None:
            _startup_flag.set()


def start_observer() -> None:
    """
    Start the observer in a separate thread.

    Waits for the observer's first startup attempt to finish. If that attempt
    fails for a reason that may clear on its own, such as an unreachable
    Prefect API, the observer keeps retrying in the background, and job sets
    registered in the meantime are watched once it is running.

    Raises:
        ArmadaObserverStartupError: If the first startup attempt fails for a
            reason that retrying will not fix.
    """
    global _observer_thread
    global _stop_flag
    global _startup_flag
    global _startup_error

    if _observer_thread is not None:
        return

    _stop_flag = threading.Event()
    _startup_flag = threading.Event()
    _startup_error = None

    _observer_thread = threading.Thread(
        target=_observer_thread_entry,
        args=(get_settings_context(), _stop_flag),
        name="prefect-armada-observer",
        daemon=True,
    )
    _observer_thread.start()
    ready = _startup_flag.wait(timeout=OBSERVER_STARTUP_TIMEOUT_SECONDS)
    with _startup_lock:
        # Once no one is waiting, the observer thread logs and retries its
        # failures instead of recording them here.
        _startup_flag = None
        error, _startup_error = _startup_error, None

    if error is not None:
        stop_observer()
        raise ArmadaObserverStartupError(
            f"The Armada observer failed to start: {error}"
        ) from error
    if not ready:
        logger.warning(
            "Armada observer did not report readiness within %s seconds; "
            "continuing without it",
            OBSERVER_STARTUP_TIMEOUT_SECONDS,
        )
    elif _observer_loop is None:
        logger.warning(
            "Armada observer failed to start and will keep retrying in the "
            "background; until it is running, Armada jobs that fail before "
            "their flow run starts will not be marked as crashed"
        )


def stop_observer() -> None:
    """
    Stop the observer thread.
    """
    global _observer_thread
    global _stop_flag

    if _stop_flag:
        _stop_flag.set()
    if _observer_thread:
        _observer_thread.join()
    _observer_thread = None
    _stop_flag = None
    with _registry_lock:
        _watch_registry.clear()
        _expected_job_ids.clear()
        _persistent_job_sets.clear()
        _pending_restarts.clear()
        _finishing_watches.clear()
