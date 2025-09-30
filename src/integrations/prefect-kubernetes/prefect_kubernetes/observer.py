from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import anyio
import kopf
from cachetools import TTLCache
from kubernetes_asyncio import config
from kubernetes_asyncio.client import ApiClient, BatchV1Api, V1Job

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
from prefect.exceptions import ObjectNotFound
from prefect.states import Crashed
from prefect.types import DateTime
from prefect.utilities.engine import propose_state
from prefect.utilities.slugify import slugify
from prefect_kubernetes.settings import KubernetesSettings

# Cache used to keep track of the last event for a pod. This is used populate the `follows` field
# on events to get correct event ordering. We only hold each pod's last event for 5 minutes to avoid
# holding onto too much memory and 5 minutes is the same as the `TIGHT_TIMING` in `prefect.events.utilities`.
_last_event_cache: TTLCache[str, Event] = TTLCache(
    maxsize=1000, ttl=60 * 5
)  # 5 minutes

settings = KubernetesSettings()

events_client: EventsClient | None = None
orchestration_client: PrefectClient | None = None


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.scanning.disabled = True


@kopf.on.startup()
async def initialize_clients(logger: kopf.Logger, **kwargs: Any):
    logger.info("Initializing clients")
    global events_client
    global orchestration_client
    orchestration_client = await get_client().__aenter__()
    events_client = await get_events_client().__aenter__()
    logger.info("Clients successfully initialized")


@kopf.on.cleanup()
async def cleanup_fn(logger: kopf.Logger, **kwargs: Any):
    logger.info("Cleaning up clients")
    await events_client.__aexit__(None, None, None)
    await orchestration_client.__aexit__(None, None, None)
    logger.info("Clients successfully cleaned up")


@kopf.on.event(
    "pods",
    labels={
        "prefect.io/flow-run-id": kopf.PRESENT,
        **settings.observer.additional_label_filters,
    },
)  # type: ignore
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
                "restart_count": status.get("restart_count", 0),
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
            json=event_filter.model_dump(exclude_unset=True, mode="json"),
        )
        # If the event already exists, we don't need to emit a new one.
        if response.json()["events"]:
            return

    resource = {
        "prefect.resource.id": f"prefect.kubernetes.pod.{uid}",
        "prefect.resource.name": name,
        "kubernetes.namespace": namespace,
    }
    # Add eviction reason if the pod was evicted for debugging purposes
    if event_type == "MODIFIED" and phase == "Failed":
        for container_status in status.get("container_statuses", []):
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

    # Exit early for terminal/final/scheduled states
    if flow_run.state.is_final() or flow_run.state.is_scheduled():
        logger.debug(f"Flow run {flow_run_id} is in final or scheduled state, skipping")
        return

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
        await propose_state(
            client=orchestration_client,
            state=Crashed(message="No active or succeeded pods found for any job"),
            flow_run_id=uuid.UUID(flow_run_id),
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
