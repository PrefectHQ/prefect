import atexit
import threading
from typing import TYPE_CHECKING, Dict, List, Optional

from prefect.events import Event, RelatedResource, emit_event
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    import kubernetes
    import kubernetes.client
    import kubernetes.watch
    from kubernetes.client import ApiClient, V1Pod
else:
    kubernetes = lazy_import("kubernetes")

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

FINAL_PHASES = {"Succeeded", "Failed"}


class KubernetesEventsReplicator:
    """Replicates Kubernetes pod events to Prefect events."""

    def __init__(
        self,
        client: "ApiClient",
        job_name: str,
        namespace: str,
        worker_resource: Dict[str, str],
        related_resources: List[RelatedResource],
        timeout_seconds: int,
    ):
        self._client = client
        self._job_name = job_name
        self._namespace = namespace
        self._timeout_seconds = timeout_seconds

        # All events emitted by this replicator have the pod itself as the
        # resource. The `worker_resource` is what the worker uses when it's
        # the primary resource, so here it's turned into a related resource
        # instead.
        worker_resource["prefect.resource.role"] = "worker"
        worker_related_resource = RelatedResource(__root__=worker_resource)
        self._related_resources = related_resources + [worker_related_resource]

        self._watch = kubernetes.watch.Watch()
        self._thread = threading.Thread(target=self._replicate_pod_events)

        self._state = "READY"

        atexit.register(self.stop)

    def __enter__(self):
        """Start the replicator thread."""
        self._thread.start()
        self._state = "STARTED"

    def __exit__(self, *args, **kwargs):
        """Stop the replicator thread."""
        self.stop()

    def stop(self):
        """Stop watching for pod events and stop thread."""
        if self._thread.is_alive():
            self._watch.stop()
            self._thread.join()
            self._state = "STOPPED"

    def _pod_as_resource(self, pod: "V1Pod") -> Dict[str, str]:
        """Convert a pod to a resource dictionary"""
        return {
            "prefect.resource.id": f"prefect.kubernetes.pod.{pod.metadata.uid}",
            "prefect.resource.name": pod.metadata.name,
            "kubernetes.namespace": pod.metadata.namespace,
        }

    def _replicate_pod_events(self):
        """Replicate Kubernetes pod events as Prefect Events."""
        seen_phases = set()
        last_event = None

        try:
            core_client = kubernetes.client.CoreV1Api(api_client=self._client)
            for event in self._watch.stream(
                func=core_client.list_namespaced_pod,
                namespace=self._namespace,
                label_selector=f"job-name={self._job_name}",
                timeout_seconds=self._timeout_seconds,
            ):
                phase = event["object"].status.phase

                if phase not in seen_phases:
                    last_event = self._emit_pod_event(event, last_event=last_event)
                    seen_phases.add(phase)
                    if phase in FINAL_PHASES:
                        self._watch.stop()
        finally:
            self._client.rest_client.pool_manager.clear()

    def _emit_pod_event(
        self,
        pod_event: Dict,
        last_event: Optional[Event] = None,
    ) -> Event:
        """Emit a Prefect event for a Kubernetes pod event."""
        pod_event_type = pod_event["type"]
        pod: "V1Pod" = pod_event["object"]
        pod_phase = pod.status.phase

        resource = self._pod_as_resource(pod)

        if pod_event_type == "MODIFIED" and pod_phase == "Failed":
            for container_status in pod.status.container_statuses:
                if container_status.state.terminated.reason in EVICTED_REASONS:
                    pod_phase = "evicted"
                    resource[
                        "kubernetes.reason"
                    ] = container_status.state.terminated.reason
                    break

        return emit_event(
            event=f"prefect.kubernetes.pod.{pod_phase.lower()}",
            resource=resource,
            related=self._related_resources,
            follows=last_event,
        )
