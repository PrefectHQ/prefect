from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from typing import Any

import kopf
from cachetools import LRUCache

from prefect import __version__, get_client
from prefect.events import Event, RelatedResource, emit_event
from prefect.events.filters import EventFilter, EventNameFilter, EventResourceFilter
from prefect.utilities.slugify import slugify

_last_event_cache: LRUCache[str, Event] = LRUCache(maxsize=1000)


@kopf.on.event("pods", labels={"prefect.io/flow-run-id": kopf.PRESENT})
def _replicate_pod_event(  # pyright: ignore[reportUnusedFunction]
    event: kopf.RawEvent,
    uid: str,
    name: str,
    namespace: str,
    labels: kopf.Labels,
    status: kopf.Status,
    **kwargs: Any,
):
    """
    Replicates a pod event to the Prefect event system.

    This handler is resilient to restarts of the operator and allows
    multiple instances of the operator to coexist without duplicate events.
    """
    event_type = event["type"]
    phase = status["phase"]

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
    # This handles the case where the operator is restarted and we don't want to emit duplicate events
    # and the case where you're moving from an older version of the worker without the operator to a newer version with the operator.
    if event_type is None:
        with get_client(sync_client=True) as client:
            response = client.request(
                "POST",
                "/events/filter",
                json=EventFilter(
                    event=EventNameFilter(
                        name=[f"prefect.kubernetes.pod.{phase.lower()}"]
                    ),
                    resource=EventResourceFilter(
                        id=[f"prefect.kubernetes.pod.{uid}"],
                    ),
                ).model_dump(exclude_unset=True),
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

    emitted_event = emit_event(
        event=f"prefect.kubernetes.pod.{phase.lower()}",
        resource=resource,
        id=event_id,
        related=_related_resources_from_labels(labels),
        follows=_last_event_cache.get(uid),
    )
    if emitted_event is not None:
        _last_event_cache[uid] = emitted_event


EVICTED_REASONS = {
    "OOMKilled",
    "CrashLoopBackoff",
    "Error",
    "Completed",
    "DeadlineExceeded",
    "ImageGCFailed",
    "NodeLost",
    "NodeOutOfDisk",
}


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


_operator_thread: threading.Thread | None = None
_stop_flag: threading.Event | None = None
_ready_flag: threading.Event | None = None


def _operator_thread_entry():
    global _stop_flag
    global _ready_flag
    _stop_flag = threading.Event()
    _ready_flag = threading.Event()

    asyncio.run(
        kopf.operator(clusterwide=True, stop_flag=_stop_flag, ready_flag=_ready_flag)
    )


def start_operator():
    """
    Start the operator in a separate thread.
    """
    global _operator_thread
    global _ready_flag

    # Suppress the warning about running the operator in a non-main thread. The starter of the operator
    # will handle the OS signals.
    class ThreadWarningFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return (
                "OS signals are ignored: running not in the main thread"
                not in record.getMessage()
            )

    logging.getLogger("kopf._core.reactor.running").addFilter(ThreadWarningFilter())

    if _operator_thread is not None:
        return
    _operator_thread = threading.Thread(
        target=_operator_thread_entry, name="prefect-kubernetes-operator", daemon=True
    )
    _operator_thread.start()
    if _ready_flag:
        _ready_flag.wait()
        _ready_flag = None


def stop_operator():
    """
    Stop the operator thread.
    """
    global _stop_flag
    global _operator_thread
    if _stop_flag:
        _stop_flag.set()
    if _operator_thread:
        _operator_thread.join()
    _operator_thread = None
    _stop_flag = None
