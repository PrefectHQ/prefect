import asyncio
import json
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


def _pod_as_resource(uid: str, name: str, namespace: str) -> dict[str, str]:
    """Convert a pod to a resource dictionary"""
    return {
        "prefect.resource.id": f"prefect.kubernetes.pod.{uid}",
        "prefect.resource.name": name,
        "kubernetes.namespace": namespace,
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


@kopf.on.event("pods", labels={"prefect.io/flow-run-id": kopf.PRESENT})
def on_pod_event(
    event: kopf.RawEvent,
    uid: str,
    name: str,
    namespace: str,
    labels: kopf.Labels,
    status: kopf.Status,
    **kwargs: Any,
):
    resource = _pod_as_resource(uid, name, namespace)
    phase = status["phase"]

    event_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        json.dumps({"uid": uid, "status": dict(status)}, sort_keys=True).encode(),
    )

    if event["type"] is None:
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
            if response.json()["events"]:
                return

    emitted_event = emit_event(
        event=f"prefect.kubernetes.pod.{phase.lower()}",
        resource=resource,
        id=event_id,
        related=_related_resources_from_labels(labels),
        follows=_last_event_cache.get(uid),
    )
    if emitted_event is not None:
        _last_event_cache[uid] = emitted_event


_operator_task: asyncio.Task[None] | None = None
_operator_thread: threading.Thread | None = None


def _operator_thread_entry():
    global _operator_task, _operator_thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _operator_task = loop.create_task(kopf.operator(clusterwide=True))
    try:
        loop.run_until_complete(_operator_task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()


def start_operator():
    global _operator_thread
    _operator_thread = threading.Thread(
        target=_operator_thread_entry, name="prefect-kubernetes-operator"
    )
    _operator_thread.start()


def stop_operator():
    global _operator_task
    global _operator_thread
    if _operator_task:
        _operator_task.cancel()
        _operator_task = None
    if _operator_thread:
        _operator_thread.join()
        _operator_thread = None
