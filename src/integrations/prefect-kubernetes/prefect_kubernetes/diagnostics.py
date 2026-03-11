"""Kubernetes pod failure diagnostics.

Pattern-matches pod status into structured failure diagnoses with
actionable resolution hints. Designed to consume the kopf `status`
parameter directly — no extra K8s API calls required.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


class DiagnosisLevel(str, enum.Enum):
    """Severity level for an infrastructure diagnosis."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclasses.dataclass(frozen=True)
class InfrastructureDiagnosis:
    """A structured diagnosis of a Kubernetes pod failure."""

    level: DiagnosisLevel
    summary: str
    detail: str
    resolution: str


def diagnose_k8s_pod(status: dict[str, Any]) -> InfrastructureDiagnosis | None:
    """Inspect a pod's `status` dict and return a diagnosis for known failure conditions.

    Returns `None` when the pod is healthy or in a state that does not
    require user intervention.

    Args:
        status: The `status` field from a Kubernetes pod object (the
            same dict kopf passes as the *status* parameter).
    """
    diagnosis = (
        _check_container_waiting(status)
        or _check_container_terminated(status)
        or _check_unschedulable(status)
        or _check_evicted(status)
    )
    return diagnosis


def _iter_container_statuses(
    status: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all container status entries (init + regular)."""
    entries: list[dict[str, Any]] = []
    for key in ("initContainerStatuses", "containerStatuses"):
        entries.extend(status.get(key) or [])
    return entries


def _check_container_waiting(
    status: dict[str, Any],
) -> InfrastructureDiagnosis | None:
    """Detect ImagePullBackOff, ErrImagePull, and CrashLoopBackOff."""
    for cs in _iter_container_statuses(status):
        waiting = (cs.get("state") or {}).get("waiting") or {}
        reason = waiting.get("reason", "")
        message = waiting.get("message", "")
        container_name = cs.get("name", "<unknown>")

        if reason in ("ImagePullBackOff", "ErrImagePull"):
            return InfrastructureDiagnosis(
                level=DiagnosisLevel.ERROR,
                summary=f"Image pull failed for container '{container_name}'",
                detail=(
                    f"Kubernetes cannot pull the container image. "
                    f"Reason: {reason}. {message}".strip()
                ),
                resolution=(
                    "Verify the image name and tag are correct. "
                    "Ensure the image exists in the registry and that "
                    "image pull secrets are configured if the registry "
                    "is private."
                ),
            )

        if reason == "CrashLoopBackOff":
            return InfrastructureDiagnosis(
                level=DiagnosisLevel.ERROR,
                summary=(f"Container '{container_name}' is crash-looping"),
                detail=(
                    f"The container repeatedly crashes after starting. "
                    f"{message}".strip()
                ),
                resolution=(
                    "Check the container logs for the root cause "
                    "(e.g. unhandled exceptions, missing config). "
                    "Verify the entrypoint command, environment "
                    "variables, and any mounted volumes."
                ),
            )

    return None


def _check_container_terminated(
    status: dict[str, Any],
) -> InfrastructureDiagnosis | None:
    """Detect OOMKilled and eviction via terminated reason."""
    for cs in _iter_container_statuses(status):
        terminated = (cs.get("state") or {}).get("terminated") or {}
        reason = terminated.get("reason", "")
        container_name = cs.get("name", "<unknown>")

        if reason == "OOMKilled":
            return InfrastructureDiagnosis(
                level=DiagnosisLevel.ERROR,
                summary=(
                    f"Container '{container_name}' was killed due to "
                    f"out-of-memory (OOMKilled)"
                ),
                detail=(
                    "The container exceeded its memory limit and was "
                    "terminated by the kernel OOM killer."
                ),
                resolution=(
                    "Increase the container's memory limit in the job "
                    "manifest, or reduce the memory footprint of the "
                    "workload. Check for memory leaks if usage grows "
                    "unboundedly."
                ),
            )

        if reason == "Evicted":
            return InfrastructureDiagnosis(
                level=DiagnosisLevel.WARNING,
                summary=f"Container '{container_name}' was evicted",
                detail=(
                    "The pod was evicted, likely due to node resource "
                    "pressure (disk, memory, or PID exhaustion)."
                ),
                resolution=(
                    "Check node conditions for resource pressure. "
                    "Consider increasing resource requests so the pod "
                    "is scheduled on a node with sufficient capacity, "
                    "or add tolerations for eviction taints."
                ),
            )

    return None


def _check_unschedulable(
    status: dict[str, Any],
) -> InfrastructureDiagnosis | None:
    """Detect Unschedulable from pod conditions."""
    for condition in status.get("conditions") or []:
        if (
            condition.get("type") == "PodScheduled"
            and condition.get("reason") == "Unschedulable"
        ):
            message = condition.get("message", "")
            return InfrastructureDiagnosis(
                level=DiagnosisLevel.WARNING,
                summary="Pod is unschedulable",
                detail=(
                    f"Kubernetes cannot find a suitable node to run "
                    f"this pod. {message}".strip()
                ),
                resolution=(
                    "Check that the cluster has nodes with sufficient "
                    "resources, matching node selectors, and "
                    "tolerations. Consider scaling up the cluster or "
                    "adjusting the pod's resource requests."
                ),
            )

    return None


def _check_evicted(
    status: dict[str, Any],
) -> InfrastructureDiagnosis | None:
    """Detect pod-level eviction from status.reason."""
    if status.get("reason") == "Evicted":
        message = status.get("message", "")
        return InfrastructureDiagnosis(
            level=DiagnosisLevel.WARNING,
            summary="Pod was evicted",
            detail=(f"The pod was evicted from its node. {message}".strip()),
            resolution=(
                "Check node conditions for resource pressure. "
                "Consider increasing resource requests so the pod "
                "is scheduled on a node with sufficient capacity, "
                "or add tolerations for eviction taints."
            ),
        )

    return None
