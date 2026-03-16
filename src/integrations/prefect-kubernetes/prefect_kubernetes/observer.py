from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import anyio
import kopf
from cachetools import TTLCache
from kubernetes_asyncio import config
from kubernetes_asyncio.client import ApiClient, BatchV1Api, CoreV1Api, V1Job

from prefect import __version__, get_client
from prefect.client.orchestration import PrefectClient
from prefect.events import Event, RelatedResource
from prefect.events.clients import EventsClient, get_events_client
from prefect.events.filters import (
    EventFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventResourceFilter,
)
from prefect.events.schemas.events import Resource
from prefect.exceptions import Abort, ObjectNotFound
from prefect.logging.loggers import flow_run_logger
from prefect.settings import PREFECT_LOGGING_TO_API_MAX_LOG_SIZE
from prefect.states import Crashed, InfrastructurePending
from prefect.types import DateTime
from prefect.utilities.engine import propose_state
from prefect.utilities.slugify import slugify
from prefect_kubernetes.diagnostics import InfrastructureDiagnosis, diagnose_k8s_pod
from prefect_kubernetes.settings import KubernetesSettings

# Cache used to keep track of the last event for a pod. This is used populate the `follows` field
# on events to get correct event ordering. We only hold each pod's last event for 5 minutes to avoid
# holding onto too much memory and 5 minutes is the same as the `TIGHT_TIMING` in `prefect.events.utilities`.
_last_event_cache: TTLCache[str, Event] = TTLCache(
    maxsize=1000, ttl=60 * 5
)  # 5 minutes

# Tracks the last diagnosis per pod UID so we don't emit duplicate
# flow run logs on repeated MODIFIED events.  Stores the full
# InfrastructureDiagnosis (a frozen dataclass) for equality comparison.
_last_diagnosis_cache: TTLCache[str, InfrastructureDiagnosis] = TTLCache(
    maxsize=1000, ttl=60 * 5
)

settings = KubernetesSettings()

events_client: EventsClient | None = None
orchestration_client: PrefectClient | None = None
_startup_event_semaphore: asyncio.Semaphore | None = None


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.scanning.disabled = True


@kopf.on.startup()
async def initialize_clients(logger: kopf.Logger, **kwargs: Any):
    logger.info("Initializing clients")
    global events_client
    global orchestration_client
    global _startup_event_semaphore
    _startup_event_semaphore = asyncio.Semaphore(
        settings.observer.startup_event_concurrency
    )
    orchestration_client = await get_client().__aenter__()
    events_client = await get_events_client().__aenter__()
    logger.info("Clients successfully initialized")


@kopf.on.cleanup()
async def cleanup_fn(logger: kopf.Logger, **kwargs: Any):
    logger.info("Cleaning up clients")
    await events_client.__aexit__(None, None, None)
    await orchestration_client.__aexit__(None, None, None)
    logger.info("Clients successfully cleaned up")


async def _replicate_pod_event(  # pyright: ignore[reportUnusedFunction]
    event: kopf.RawEvent,
    uid: str,
    name: str,
    namespace: str,
    labels: kopf.Labels,
    status: kopf.Status,
    logger: logging.Logger,
    **kwargs: Any,
):
    """
    Replicates a pod event to the Prefect event system.

    This handler is resilient to restarts of the observer and allows
    multiple instances of the observer to coexist without duplicate events.
    """
    global events_client
    global orchestration_client
    event_type = event["type"]
    phase = status["phase"]

    logger.debug(f"Pod event received - type: {event_type}, phase: {phase}, uid: {uid}")

    # Extract the creation timestamp from the Kubernetes event
    k8s_created_time = None
    if isinstance(event, dict) and "object" in event:
        obj = event["object"]
        if isinstance(obj, dict) and "metadata" in obj:
            metadata = obj["metadata"]
            if "creationTimestamp" in metadata:
                k8s_created_time = DateTime.fromisoformat(
                    metadata["creationTimestamp"].replace("Z", "+00:00")
                )

    # Create a deterministic event ID based on the pod's ID, phase, and restart count.
    # This ensures that the event ID is the same for the same pod in the same phase and restart count
    # and Prefect's event system will be able to deduplicate events.
    event_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        json.dumps(
            {
                "uid": uid,
                "phase": phase,
                "restart_count": sum(
                    cs.get("restartCount", 0)
                    for cs in status.get("containerStatuses", [])
                ),
            },
            sort_keys=True,
        ),
    )

    # Check if a corresponding event already exists. If so, we don't need to emit a new one.
    # This handles the case where the observer is restarted and we don't want to emit duplicate events
    # and the case where you're moving from an older version of the worker without the observer to a newer version with the observer.
    if event_type is None:
        if orchestration_client is None:
            raise RuntimeError("Orchestration client not initialized")
        if _startup_event_semaphore is None:
            raise RuntimeError("Startup event semaphore not initialized")

        # Use semaphore to limit concurrent API calls during startup to prevent
        # overwhelming the API server when there are many existing pods/jobs
        async with _startup_event_semaphore:
            # Use the Kubernetes event timestamp for the filter to avoid "Query time range is too large" error
            event_filter = EventFilter(
                event=EventNameFilter(name=[f"prefect.kubernetes.pod.{phase.lower()}"]),
                resource=EventResourceFilter(
                    id=[f"prefect.kubernetes.pod.{uid}"],
                ),
                occurred=EventOccurredFilter(
                    since=(
                        k8s_created_time
                        if k8s_created_time
                        else (datetime.now(timezone.utc) - timedelta(hours=1))
                    )
                ),
            )

            response = await orchestration_client.request(
                "POST",
                "/events/filter",
                json=dict(
                    filter=event_filter.model_dump(exclude_unset=True, mode="json")
                ),
            )
            # If the event already exists, we don't need to emit a new one.
            if response.json()["events"]:
                return

    flow_run_id_label = labels.get("prefect.io/flow-run-id")
    try:
        flow_run_id = uuid.UUID(flow_run_id_label) if flow_run_id_label else None
    except ValueError:
        flow_run_id = None

    # Propose InfrastructurePending for pods still in Pending phase
    if phase == "Pending" and flow_run_id and orchestration_client:
        try:
            flow_run = await orchestration_client.read_flow_run(flow_run_id=flow_run_id)
            if flow_run.state is not None and (
                flow_run.state.is_running()
                or flow_run.state.is_final()
                or flow_run.state.is_paused()
                or flow_run.state.is_cancelling()
                or flow_run.state.name == "InfrastructurePending"
            ):
                logger.debug(
                    f"Flow run {flow_run_id} is in state {flow_run.state.name!r}, "
                    f"skipping InfrastructurePending proposal"
                )
            else:
                # Use a timeout to prevent propose_state's internal WAIT
                # loop from blocking the observer's event processing.
                with anyio.move_on_after(5):
                    await propose_state(
                        client=orchestration_client,
                        state=InfrastructurePending(
                            message="Kubernetes pod is pending."
                        ),
                        flow_run_id=flow_run_id,
                    )
        except ObjectNotFound:
            logger.debug(f"Flow run {flow_run_id} not found, skipping")
        except (Abort, Exception):
            logger.debug(
                f"Failed to propose InfrastructurePending for flow run {flow_run_id}",
                exc_info=True,
            )

    # Diagnose pod failures and emit actionable flow run logs.
    # Only log when the diagnosis changes to avoid spamming on repeated
    # MODIFIED events for the same failure condition.  Clear the cache
    # entry when the pod recovers so a recurrence is logged again.
    diagnosis = diagnose_k8s_pod(status)
    if diagnosis and flow_run_id:
        last_diagnosis = _last_diagnosis_cache.get(uid)
        if diagnosis != last_diagnosis:
            _last_diagnosis_cache[uid] = diagnosis
            fr_logger = flow_run_logger(flow_run_id=flow_run_id).getChild("observer")
            fr_logger.log(
                logging.ERROR if diagnosis.level.value == "error" else logging.WARNING,
                "%s: %s Resolution: %s",
                diagnosis.summary,
                diagnosis.detail,
                diagnosis.resolution,
            )
    elif not diagnosis:
        _last_diagnosis_cache.pop(uid, None)

    resource = {
        "prefect.resource.id": f"prefect.kubernetes.pod.{uid}",
        "prefect.resource.name": name,
        "kubernetes.namespace": namespace,
    }
    # Add eviction reason if the pod was evicted for debugging purposes
    if event_type == "MODIFIED" and phase == "Failed":
        for container_status in status.get("containerStatuses", []):
            if (
                terminated := container_status.get("state", {}).get("terminated", {})
            ) and (reason := terminated.get("reason")):
                phase = "evicted"
                resource["kubernetes.reason"] = reason
                break

    # Create the Prefect event, using the K8s event timestamp as the occurred time if available
    prefect_event = Event(
        event=f"prefect.kubernetes.pod.{phase.lower()}",
        resource=Resource.model_validate(resource),
        id=event_id,
        related=_related_resources_from_labels(labels),
    )

    if (prev_event := _last_event_cache.get(uid)) is not None:
        # This check replicates a similar check in `emit_event` in `prefect.events.utilities`
        if (
            -timedelta(minutes=5)
            < (prefect_event.occurred - prev_event.occurred)
            < timedelta(minutes=5)
        ):
            prefect_event.follows = prev_event.id
    if events_client is None:
        raise RuntimeError("Events client not initialized")
    await events_client.emit(event=prefect_event)
    _last_event_cache[uid] = prefect_event


if settings.observer.replicate_pod_events:
    kopf.on.event(
        "pods",
        labels={
            "prefect.io/flow-run-id": kopf.PRESENT,
            **settings.observer.additional_label_filters,
        },
    )(_replicate_pod_event)  # type: ignore


@dataclasses.dataclass(frozen=True)
class _ContainerLogEntry:
    """A batch of log lines from a single container."""

    pod_name: str
    container_name: str
    container_type: str  # "container" or "init container"
    lines: list[str]


async def _fetch_crashed_pod_logs(
    flow_run_id: str,
    job_name: str,
    namespace: str,
    logger: logging.Logger,
) -> list[_ContainerLogEntry] | None:
    """Fetch container logs from crashed pods belonging to a specific job.

    Only fetches logs from pods owned by *job_name* (via the `job-name`
    label that Kubernetes adds automatically), so retries/reschedules that
    create new jobs for the same flow run don't pollute the output.

    Within each pod the primary flow-run container is prioritised.  Logs
    from other containers (sidecars, init containers) are only included
    when the primary container produced no output.

    Returns a list of per-container log entries, or None if fetching is
    disabled, no pods are found, or an error occurs.  The caller is
    responsible for forwarding the entries via `_send_crashed_pod_logs`.
    """
    if not settings.observer.forward_crashed_run_logs:
        return None

    tail_lines = settings.observer.forward_crashed_run_logs_tail_lines
    entries: list[_ContainerLogEntry] = []

    try:
        client = await _get_kubernetes_client()
        core_client = CoreV1Api(client)
        try:
            pods = await core_client.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"job-name={job_name}",
            )
            # Exclude pods that completed successfully — their logs are
            # not crash diagnostics.  We keep Failed pods (restartPolicy:
            # Never) *and* Running/Pending pods because with restartPolicy:
            # OnFailure the pod stays Running while containers crash inside
            # it, and the Job can hit its backoffLimit without the pod ever
            # reaching phase Failed.
            candidate_pods = [
                p for p in pods.items if getattr(p.status, "phase", None) != "Succeeded"
            ]
            # Sort pods newest-first so the final retry attempt's logs
            # appear first and survive truncation.
            sorted_pods = sorted(
                candidate_pods,
                key=lambda p: p.metadata.creation_timestamp or "",
                reverse=True,
            )
            for pod in sorted_pods:
                pod_name = pod.metadata.name
                pod_entries = _fetch_pod_container_logs_ordered(
                    pod,
                    pod_name,
                    namespace,
                    tail_lines,
                    core_client,
                    logger,
                )
                entries.extend([entry async for entry in pod_entries])
        finally:
            await client.close()
    except Exception:
        logger.debug(
            f"Failed to fetch crashed pod logs for flow run {flow_run_id}",
            exc_info=True,
        )

    return entries if entries else None


async def _fetch_pod_container_logs_ordered(
    pod: Any,
    pod_name: str,
    namespace: str,
    tail_lines: int,
    core_client: CoreV1Api,
    logger: logging.Logger,
):
    """Yield log entries for a pod, prioritising the primary flow container.

    The primary container is identified using a best-effort heuristic:
    1. If there is only one regular container it must be the flow container.
    2. Otherwise, prefer the container named `prefect-job` (the default
       name used by the Prefect Kubernetes worker).
    3. If neither applies (custom job manifest with a renamed container and
       injected sidecars), treat the first container in the spec as primary
       — sidecars injected by admission webhooks are appended after the
       containers defined in the original manifest.

    If the primary container produces non-empty logs, those are yielded and
    other containers are skipped to avoid noise consuming the size budget.
    Otherwise, all containers are returned as a fallback so the user still
    gets *something* to diagnose the failure.
    """
    # Identify the primary container
    primary: list[tuple[str, str]] = []
    others: list[tuple[str, str]] = []

    containers = pod.spec.containers or []
    if len(containers) == 1:
        # Only one container — it must be the flow container
        primary.append((containers[0].name, "container"))
    else:
        # Multiple containers: prefer prefect-job, else first in spec
        prefect_job_found = False
        for c in containers:
            if c.name == "prefect-job":
                primary.append((c.name, "container"))
                prefect_job_found = True
            else:
                others.append((c.name, "container"))
        if not prefect_job_found and containers:
            # Custom manifest — treat first container as primary
            first = others.pop(0)
            primary.append(first)

    init_containers: list[tuple[str, str]] = []
    if pod.spec.init_containers:
        init_containers = [(c.name, "init container") for c in pod.spec.init_containers]

    # Try the primary container first
    for container_name, container_type in primary:
        entry = await _read_container_log(
            core_client,
            pod_name,
            namespace,
            container_name,
            container_type,
            tail_lines,
            logger,
        )
        if entry:
            yield entry
            return  # primary container had output — skip sidecars

    # Primary container was empty or missing — fall back to all others
    for container_name, container_type in init_containers + others:
        entry = await _read_container_log(
            core_client,
            pod_name,
            namespace,
            container_name,
            container_type,
            tail_lines,
            logger,
        )
        if entry:
            yield entry


async def _read_container_log(
    core_client: CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    container_type: str,
    tail_lines: int,
    logger: logging.Logger,
) -> _ContainerLogEntry | None:
    """Read logs from a single container, returning a structured entry or None.

    Tries the previous (crashed) container instance first, then falls back
    to the current instance.  This matters for restartPolicy: OnFailure
    where the pod stays Running while the container is restarted — the
    current instance may be a fresh restart with no useful output, while
    the previous instance holds the actual crash traceback.
    """
    log_text: str | None = None

    # Try previous container instance first (the one that crashed).
    try:
        prev = await core_client.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container_name,
            tail_lines=tail_lines,
            previous=True,
        )
        if prev and prev.strip():
            log_text = prev
    except Exception:
        # No previous instance (never restarted, or already GC'd) — that's fine.
        pass

    # Fall back to current container logs.
    if not log_text:
        try:
            current = await core_client.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=tail_lines,
            )
            if current and current.strip():
                log_text = current
        except Exception as e:
            logger.debug(
                f"Could not fetch logs for {container_type} "
                f"{container_name!r} in pod {pod_name!r}: {e}"
            )

    if not log_text:
        return None

    lines = [line for line in log_text.splitlines() if line.strip()]
    if not lines:
        return None

    return _ContainerLogEntry(
        pod_name=pod_name,
        container_name=container_name,
        container_type=container_type,
        lines=lines,
    )


def _send_crashed_pod_logs(flow_run_id: str, entries: list[_ContainerLogEntry]) -> None:
    """Forward previously-fetched pod logs as individual flow-run log entries."""
    max_size = PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value()
    fr_logger = flow_run_logger(flow_run_id=uuid.UUID(flow_run_id)).getChild("observer")

    for entry in entries:
        header = (
            f"Container logs from {entry.container_type} {entry.container_name!r} "
            f"in pod {entry.pod_name!r}:"
        )
        fr_logger.error(header)
        for line in entry.lines:
            if len(line) > max_size:
                line = line[: max_size - len("... [truncated]")] + "... [truncated]"
            fr_logger.error(line)


async def _get_kubernetes_client() -> ApiClient:
    """Get a configured Kubernetes client.

    Returns:
        ApiClient: A configured Kubernetes API client
    """
    try:
        # Try to load in-cluster configuration
        config.load_incluster_config()  # type: ignore
        client = ApiClient()
    except config.ConfigException:
        # If in-cluster config fails, load the local kubeconfig
        client = await config.new_client_from_config()  # type: ignore
    return client


async def _get_k8s_jobs(
    flow_run_id: str, namespace: str, logger: kopf.Logger
) -> list[V1Job]:
    """Get all jobs from the k8s API with the given flow run id as a label.

    Uses kubernetes-asyncio to list jobs.
    """
    try:
        client = await _get_kubernetes_client()
        batch_client = BatchV1Api(client)
        jobs = await batch_client.list_namespaced_job(  # type: ignore
            namespace=namespace, label_selector=f"prefect.io/flow-run-id={flow_run_id}"
        )
        return jobs.items  # type: ignore
    except Exception as e:
        logger.error(f"Failed to get jobs for flow run {flow_run_id}: {e}")
        return []
    finally:
        await client.close()  # type: ignore


@kopf.on.event(
    "jobs",
    labels={
        "prefect.io/flow-run-id": kopf.PRESENT,
        **settings.observer.additional_label_filters,
    },
)  # type: ignore
async def _mark_flow_run_as_crashed(  # pyright: ignore[reportUnusedFunction]
    event: kopf.RawEvent,
    name: str,
    labels: kopf.Labels,
    status: kopf.Status,
    logger: logging.Logger,
    spec: kopf.Spec,
    **kwargs: Any,
):
    """
    Marks a flow run as crashed if the corresponding job has failed and no other active jobs exist.
    """
    global orchestration_client
    if not (flow_run_id := labels.get("prefect.io/flow-run-id")):
        return

    logger.debug(
        f"Job event received - name: {name}, flow_run_id: {flow_run_id}, status: {status}"
    )
    backoff_limit = spec.get("backoffLimit", 6)

    # Check current job status from the event
    current_job_failed = status.get("failed", 0) > backoff_limit

    # If the job is still active or has succeeded, don't mark as crashed
    if not current_job_failed:
        logger.debug(f"Job {name} is still active or has succeeded, skipping")
        return

    # Get the flow run to check its state
    try:
        if orchestration_client is None:
            raise RuntimeError("Orchestration client not initialized")
        flow_run = await orchestration_client.read_flow_run(
            flow_run_id=uuid.UUID(flow_run_id)
        )
    except ObjectNotFound:
        logger.debug(f"Flow run {flow_run_id} not found, skipping")
        return

    assert flow_run.state is not None, "Expected flow run state to be set"

    # Exit early for terminal/final/scheduled/paused states
    if (
        flow_run.state.is_final()
        or flow_run.state.is_scheduled()
        or flow_run.state.is_paused()
    ):
        logger.debug(
            f"Flow run {flow_run_id} is in final, scheduled, or paused state, skipping"
        )
        return

    # Eagerly fetch pod logs while the flow run is still in a pre-connectivity
    # state (Pending / InfrastructurePending).  We capture them *before* the
    # 30-second reschedule-wait loop below because cluster GC (e.g.
    # ttlSecondsAfterFinished) may delete the failed pods in the meantime.
    # The captured logs are only forwarded later if we actually mark the run
    # as crashed (i.e. no replacement job appears).
    captured_pod_logs: list[_ContainerLogEntry] | None = None
    if flow_run.state.is_pending():
        captured_pod_logs = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name=name,
            namespace=kwargs["namespace"],
            logger=logger,
        )

    # In the case where a flow run is rescheduled due to a SIGTERM, it will show up as another active job if the
    # rescheduling was successful. If this is the case, we want to find the other active job so that we don't mark
    # the flow run as crashed.
    #
    # If the flow run is PENDING, it's possible that the job hasn't been created yet, so we'll wait and query new state
    # to make a determination.
    has_other_active_job = False
    with anyio.move_on_after(30):
        while True:
            # Check if there are any other jobs with this flow run label
            k8s_jobs = await _get_k8s_jobs(
                flow_run_id, namespace=kwargs["namespace"], logger=logger
            )

            # Filter out the current job from the list
            other_jobs = [job for job in k8s_jobs if job.metadata.name != name]  # type: ignore

            # Check if any other job is completed or running
            has_other_active_job = any(
                (job.status and job.status.succeeded)  # type: ignore
                or (job.status and job.status.active and job.status.active > 0)  # type: ignore
                for job in other_jobs
            )
            logger.debug(
                f"Other jobs status - count: {len(other_jobs)}, has_active: {has_other_active_job}"
            )

            flow_run = await orchestration_client.read_flow_run(
                flow_run_id=uuid.UUID(flow_run_id)
            )
            assert flow_run.state is not None, "Expected flow run state to be set"
            if not flow_run.state.is_pending() or has_other_active_job:
                break

            logger.info(
                f"Flow run {flow_run_id} in state {flow_run.state!r} with no other active jobs, waiting for 5 seconds before checking again"
            )
            await anyio.sleep(5)

    if not has_other_active_job:
        logger.warning(
            f"Job {name} has failed and no other active jobs found for flow run {flow_run_id}, marking as crashed"
        )

        result_state = await propose_state(
            client=orchestration_client,
            state=Crashed(message="No active or succeeded pods found for any job"),
            flow_run_id=uuid.UUID(flow_run_id),
        )

        # Only forward pod logs if the crash transition was accepted.
        # If the run advanced beyond Pending (e.g. to Running) during the
        # wait loop, propose_state will be rejected and we must not attach
        # stale crash logs to a live run.
        if captured_pod_logs and result_state.is_crashed():
            _send_crashed_pod_logs(
                flow_run_id=flow_run_id,
                entries=captured_pod_logs,
            )


def _related_resources_from_labels(labels: kopf.Labels) -> list[RelatedResource]:
    """Convert labels to related resources"""
    related: list[RelatedResource] = []
    if flow_run_id := labels.get("prefect.io/flow-run-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": labels.get("prefect.io/flow-run-name"),
                }
            )
        )
    if deployment_id := labels.get("prefect.io/deployment-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.deployment.{deployment_id}",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": labels.get("prefect.io/deployment-name"),
                }
            )
        )
    if flow_id := labels.get("prefect.io/flow-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow.{flow_id}",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": labels.get("prefect.io/flow-name"),
                }
            )
        )
    if work_pool_id := labels.get("prefect.io/work-pool-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool_id}",
                    "prefect.resource.role": "work-pool",
                    "prefect.resource.name": labels.get("prefect.io/work-pool-name"),
                }
            )
        )
    if worker_name := labels.get("prefect.io/worker-name"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.worker.kubernetes.{slugify(worker_name)}",
                    "prefect.resource.role": "worker",
                    "prefect.resource.name": worker_name,
                    "prefect.worker-type": "kubernetes",
                    "prefect.version": __version__,
                }
            )
        )
    return related


_observer_thread: threading.Thread | None = None
_stop_flag: threading.Event | None = None
_ready_flag: threading.Event | None = None


def _observer_thread_entry():
    global _stop_flag
    global _ready_flag
    _stop_flag = threading.Event()
    _ready_flag = threading.Event()

    namespaces = settings.observer.namespaces

    if namespaces:
        asyncio.run(
            kopf.operator(
                namespaces=namespaces,
                stop_flag=_stop_flag,
                ready_flag=_ready_flag,
                standalone=True,
                identity=uuid.uuid4().hex,
            )
        )
    else:
        asyncio.run(
            kopf.operator(
                clusterwide=True,
                stop_flag=_stop_flag,
                ready_flag=_ready_flag,
                standalone=True,
                identity=uuid.uuid4().hex,
            )
        )


def start_observer():
    """
    Start the observer in a separate thread.
    """
    global _observer_thread
    global _ready_flag

    # Suppress the warning about running the observer in a non-main thread. The starter of the observer
    # will handle the OS signals.
    class ThreadWarningFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return (
                "OS signals are ignored: running not in the main thread"
                not in record.getMessage()
            )

    logging.getLogger("kopf._core.reactor.running").addFilter(ThreadWarningFilter())

    # Configure kopf logging to match Prefect's logging format
    from prefect.logging.configuration import PROCESS_LOGGING_CONFIG

    if PROCESS_LOGGING_CONFIG:
        console_formatter = (
            PROCESS_LOGGING_CONFIG.get("handlers", {})
            .get("console", {})
            .get("formatter")
        )
        if console_formatter == "json":
            # Configure kopf to use its own JSON formatter instead of Prefect's
            # which cannot serialize kopf internal objects
            from prefect_kubernetes._logging import KopfObjectJsonFormatter

            kopf_logger = logging.getLogger("kopf")
            kopf_handler = logging.StreamHandler(sys.stderr)
            kopf_handler.setFormatter(KopfObjectJsonFormatter())
            kopf_logger.addHandler(kopf_handler)
            # Turn off propagation to prevent kopf logs from being propagated to Prefect's JSON formatter
            # which cannot serialize kopf internal objects
            kopf_logger.propagate = False

    if _observer_thread is not None:
        return
    _observer_thread = threading.Thread(
        target=_observer_thread_entry, name="prefect-kubernetes-observer", daemon=True
    )
    _observer_thread.start()
    if _ready_flag:
        _ready_flag.wait()
        _ready_flag = None


def stop_observer():
    """
    Stop the observer thread.
    """
    global _stop_flag
    global _observer_thread
    if _stop_flag:
        _stop_flag.set()
    if _observer_thread:
        _observer_thread.join()
    _observer_thread = None
    _stop_flag = None
