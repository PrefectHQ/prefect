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
import uuid
from contextlib import aclosing
from datetime import datetime, timedelta, timezone
from typing import Any

import anyio
import grpc
from anyio.to_thread import run_sync
from armada_client.event import Event as ArmadaEvent
from cachetools import TTLCache

from prefect import __version__, get_client
from prefect.client.orchestration import PrefectClient
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
from prefect_armada.events import stream_job_set_events
from prefect_armada.exceptions import rpc_details, rpc_status_code
from prefect_armada.settings import ArmadaSettings
from prefect_armada.utilities import UNSUCCESSFUL_EVENT_TYPES

logger = get_logger("prefect_armada.observer")

# Armada event types after which a job will never run again.
TERMINAL_EVENT_TYPES = {"succeeded", "failed", "cancelled", "preempted"}

# How many times to (re)connect to a job set's event stream before giving up,
# and the ceiling on the exponential backoff between attempts. Eight attempts
# with this backoff spans a little over two minutes.
WATCH_RETRY_MAX_ATTEMPTS = 8
WATCH_RETRY_MAX_DELAY_SECONDS = 30

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
_pending_restarts: set[_JobSetKey] = set()
_watch_tasks: dict[_JobSetKey, asyncio.Task[None]] = {}

_observer_thread: threading.Thread | None = None
_observer_loop: asyncio.AbstractEventLoop | None = None
_stop_flag: threading.Event | None = None
_ready_flag: threading.Event | None = None


class _JobSetWatchState:
    """Tracks what the observer knows about the jobs in a job set."""

    def __init__(self) -> None:
        self.annotations: dict[str, dict[str, str]] = {}
        self.submitted_job_ids: set[str] = set()
        self.finished_job_ids: set[str] = set()

    @property
    def is_finished(self) -> bool:
        """Whether every job seen in this job set has reached a terminal event."""
        return bool(self.submitted_job_ids) and self.submitted_job_ids.issubset(
            self.finished_job_ids
        )


def observe_job_set(
    credentials: ArmadaCredentials, queue: str, job_set_id: str
) -> None:
    """
    Registers an Armada job set to be watched by the observer.

    Safe to call from any thread and safe to call repeatedly for the same job
    set; a job set that is already being watched is only re-watched if its
    current watch has already finished.

    Args:
        credentials: The credentials used to connect to Armada.
        queue: The name of the Armada queue the job set was submitted to.
        job_set_id: The name of the Armada job set to watch.
    """
    key = (queue, job_set_id)
    with _registry_lock:
        already_watching = key in _watch_registry
        _watch_registry[key] = credentials
        if already_watching:
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
    task.add_done_callback(lambda _: _finalize_watch(key))


def _finalize_watch(key: _JobSetKey) -> None:
    """Cleans up after a job set watch has ended, restarting it if needed."""
    _watch_tasks.pop(key, None)
    with _registry_lock:
        restart = key in _pending_restarts
        _pending_restarts.discard(key)
        if not restart:
            _watch_registry.pop(key, None)

    if restart and _observer_loop is not None:
        asyncio.run_coroutine_threadsafe(_ensure_watch(key), _observer_loop)


async def _watch_job_set(
    credentials: ArmadaCredentials, queue: str, job_set_id: str
) -> None:
    """
    Watches an Armada job set's event stream until every job in it has finished.

    Armada replays a job set's history from the beginning of the stream, so a
    watch that is restarted will see events it has already handled. Replicated
    Prefect events use deterministic IDs so that the replay is deduplicated by
    Prefect's event system rather than producing duplicates.
    """
    logger.debug("Watching Armada job set %r in queue %r", job_set_id, queue)
    state = _JobSetWatchState()

    # A watch usually starts moments after the job set's first job is submitted,
    # before Armada has made the job set visible to the event service, so the
    # first attempts routinely fail with NOT_FOUND. Retrying with backoff is
    # what keeps a flow run's job set from going unobserved.
    for attempt in range(1, WATCH_RETRY_MAX_ATTEMPTS + 1):
        try:
            async with aclosing(
                stream_job_set_events(
                    armada_credentials=credentials,
                    queue=queue,
                    job_set_id=job_set_id,
                )
            ) as event_stream:
                async for event in event_stream:
                    # The stream is working, so later failures get a full set of
                    # retries of their own.
                    attempt = 1
                    await _handle_event(event, queue, job_set_id, state, credentials)
                    if state.is_finished:
                        logger.debug(
                            "Finished watching Armada job set %r in queue %r",
                            job_set_id,
                            queue,
                        )
                        return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if attempt >= WATCH_RETRY_MAX_ATTEMPTS:
                logger.warning(
                    "Giving up watching Armada job set %r in queue %r after %s "
                    "attempts",
                    job_set_id,
                    queue,
                    attempt,
                    exc_info=True,
                )
                return
            delay = min(2 ** (attempt - 1), WATCH_RETRY_MAX_DELAY_SECONDS)
            logger.debug(
                "Error watching Armada job set %r in queue %r (%s); retrying in %ss",
                job_set_id,
                queue,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
        else:
            # The stream ended without the job set finishing, e.g. Armada closed
            # it; reconnect to pick up where it left off.
            logger.debug(
                "Event stream for Armada job set %r in queue %r ended; reconnecting",
                job_set_id,
                queue,
            )
            await asyncio.sleep(min(2 ** (attempt - 1), WATCH_RETRY_MAX_DELAY_SECONDS))


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
        occurred = occurred.replace(tzinfo=timezone.utc)
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


async def _mark_flow_run_as_crashed(
    flow_run_id: str,
    job_id: str,
    event_type: str,
    reason: str,
    namespace: str,
    credentials: ArmadaCredentials,
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

    # Exit early for terminal/final/scheduled/paused states
    if (
        flow_run.state.is_final()
        or flow_run.state.is_scheduled()
        or flow_run.state.is_paused()
    ):
        logger.debug(
            "Flow run %s is in final, scheduled, or paused state, skipping",
            flow_run_id,
        )
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
    if flow_run.state.is_final():
        logger.debug(
            "Flow run %s reached a final state on its own, skipping", flow_run_id
        )
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


async def _observer_main() -> None:
    """Runs the observer until it is stopped."""
    global _observer_loop
    global events_client
    global orchestration_client

    _observer_loop = asyncio.get_running_loop()

    logger.info("Initializing clients")
    async with get_client() as prefect_client, get_events_client() as prefect_events:
        orchestration_client = prefect_client
        events_client = prefect_events
        logger.info("Clients successfully initialized")

        _register_configured_job_sets(ArmadaCredentials())

        with _registry_lock:
            keys = list(_watch_registry)
        for key in keys:
            await _ensure_watch(key)

        if _ready_flag is not None:
            _ready_flag.set()

        try:
            while _stop_flag is None or not _stop_flag.is_set():
                await asyncio.sleep(0.5)
        finally:
            tasks = list(_watch_tasks.values())
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            _watch_tasks.clear()
            _observer_loop = None
            orchestration_client = None
            events_client = None


def _observer_thread_entry(settings_context: SettingsContext) -> None:
    """Entrypoint for the observer thread."""
    try:
        # Prefect settings live in a context variable, which a new thread does
        # not inherit, so the starting thread's settings are re-applied here to
        # ensure the observer talks to the same Prefect API as its worker. A
        # context object can only be entered once, so a new one is built from
        # the captured profile and settings.
        with SettingsContext(
            profile=settings_context.profile, settings=settings_context.settings
        ):
            asyncio.run(_observer_main())
    except Exception:
        logger.exception("Armada observer stopped unexpectedly")
    finally:
        # Ensure a caller waiting on startup is never blocked by a failure here.
        if _ready_flag is not None:
            _ready_flag.set()


def start_observer() -> None:
    """
    Start the observer in a separate thread.
    """
    global _observer_thread
    global _stop_flag
    global _ready_flag

    if _observer_thread is not None:
        return

    _stop_flag = threading.Event()
    _ready_flag = threading.Event()

    _observer_thread = threading.Thread(
        target=_observer_thread_entry,
        args=(get_settings_context(),),
        name="prefect-armada-observer",
        daemon=True,
    )
    _observer_thread.start()
    if not _ready_flag.wait(timeout=30):
        logger.warning(
            "Armada observer did not report readiness within 30 seconds; "
            "continuing without it"
        )
    _ready_flag = None


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
        _pending_restarts.clear()
