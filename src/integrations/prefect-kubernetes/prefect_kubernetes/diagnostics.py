"""Kubernetes pod failure diagnostics.

Pattern-matches pod status into structured failure diagnoses with
actionable resolution hints. Designed to consume the kopf `status`
parameter directly — no extra K8s API calls required.
"""

from __future__ import annotations

import dataclasses
import enum
import re
from typing import Any


class DiagnosisLevel(str, enum.Enum):
    """Severity level for an infrastructure diagnosis."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiagnosisCategory(str, enum.Enum):
    """Stable, machine-matchable category for a pod-failure diagnosis.

    These values are emitted as the `kubernetes.diagnosis` label on
    replicated pod events, so automations can match on a specific failure
    mode. Treat the values as a stable contract — do not rename them.
    """

    IMAGE_PULL_ERROR = "ImagePullError"
    CRASH_LOOP_BACKOFF = "CrashLoopBackOff"
    OOM_KILLED = "OOMKilled"
    EVICTED = "Evicted"
    UNSCHEDULABLE = "Unschedulable"
    UNSCHEDULABLE_INSUFFICIENT_RESOURCES = "Unschedulable.InsufficientResources"
    UNSCHEDULABLE_NODE_AFFINITY = "Unschedulable.NodeAffinity"
    UNSCHEDULABLE_TAINT = "Unschedulable.Taint"


_NODE_SUMMARY_PATTERN = re.compile(r"\d+/\d+ nodes are available:")
_LEADING_COUNT_PATTERN = re.compile(r"^\d+\s+")
_REASON_BOUNDARY_PATTERN = re.compile(r",\s+(?=\d+\s+)")
_DEFAULT_PREEMPTION_PREFIX = "preemption:"
_NODE_DECLARED_FEATURES_PREFIX = (
    "node declared features check failed - unsatisfied requirements:"
)

_UNSCHEDULABLE_CATEGORIES = frozenset(
    {
        DiagnosisCategory.UNSCHEDULABLE,
        DiagnosisCategory.UNSCHEDULABLE_INSUFFICIENT_RESOURCES,
        DiagnosisCategory.UNSCHEDULABLE_NODE_AFFINITY,
        DiagnosisCategory.UNSCHEDULABLE_TAINT,
    }
)


def _normalize_scheduler_reason(reason: str) -> str:
    """Canonicalize scheduler-owned ordering within one filter reason."""
    prefix, separator, requirements = reason.partition(_NODE_DECLARED_FEATURES_PREFIX)
    if not separator:
        return reason

    normalized_requirements = ", ".join(
        sorted(requirement.strip() for requirement in requirements.split(","))
    )
    return f"{prefix}{separator} {normalized_requirements}"


def _split_default_preemption(post_filter: str) -> tuple[str | None, str | None]:
    """Separate a default-preemption summary from earlier post-filter output."""
    if post_filter.startswith(_DEFAULT_PREEMPTION_PREFIX):
        general_post_filter = None
        preemption_detail = post_filter.removeprefix(
            _DEFAULT_PREEMPTION_PREFIX
        ).lstrip()
    else:
        marker = f", {_DEFAULT_PREEMPTION_PREFIX}"
        marker_index = post_filter.find(marker)
        if marker_index == -1:
            return None, None
        general_post_filter = post_filter[:marker_index]
        preemption_detail = post_filter[marker_index + len(marker) :].lstrip()

    if not _NODE_SUMMARY_PATTERN.search(preemption_detail):
        return None, None
    return general_post_filter, preemption_detail


def _normalize_post_filter(post_filter: str) -> list[tuple[str, str]]:
    """Preserve post-filter output, normalizing default-preemption summaries."""
    general_post_filter, preemption_detail = _split_default_preemption(post_filter)
    if preemption_detail is not None:
        normalized = []
        if general_post_filter:
            normalized.append(("postfilter", general_post_filter))
        normalized.extend(
            (f"postfilter/preemption/{section}", reason)
            for section, reason in _parse_scheduler_message(preemption_detail)
        )
        return normalized
    return [("postfilter", post_filter)]


def _parse_scheduler_message(message: str) -> list[tuple[str, str]]:
    """Parse scheduler output into tagged prefilter, filter, and postfilter data."""
    if node_summary := _NODE_SUMMARY_PATTERN.search(message):
        payload = message[node_summary.end() :].lstrip()
    else:
        payload = message

    first_section, separator, post_filter = payload.partition(". ")
    if not _LEADING_COUNT_PATTERN.match(payload):
        _, preemption_detail = _split_default_preemption(payload)
        if preemption_detail is not None:
            return _normalize_post_filter(payload)

        normalized = [("prefilter", first_section.rstrip("."))]
        if separator:
            normalized.extend(_normalize_post_filter(post_filter))
        return normalized

    filter_reasons = first_section
    parts = _REASON_BOUNDARY_PATTERN.split(filter_reasons)
    if not separator:
        parts[-1] = parts[-1].rstrip(".")

    normalized: list[tuple[str, str]] = []
    for part in parts:
        reason = _LEADING_COUNT_PATTERN.sub("", part.strip())
        if reason:
            normalized.append(("filter", _normalize_scheduler_reason(reason)))
    if separator:
        normalized.extend(_normalize_post_filter(post_filter))
    return normalized


def _normalize_scheduler_reasons(detail: str) -> tuple[str, ...]:
    """Return stable, tagged scheduler reasons without volatile node counts.

    Filter histograms are split only where Kubernetes starts the next counted
    reason, keeping commas within a reason intact. Prefilter, filter, and
    postfilter sections are tagged so identical text in different scheduler
    stages remains distinct. General postfilter output is preserved exactly;
    default-preemption node summaries are parsed recursively because their node
    counts and reason order are volatile too.
    """
    return tuple(
        sorted(
            f"{section}: {reason}"
            for section, reason in _parse_scheduler_message(detail)
            if reason
        )
    )


@dataclasses.dataclass(frozen=True)
class InfrastructureDiagnosis:
    """A structured diagnosis of a Kubernetes pod failure."""

    level: DiagnosisLevel
    category: DiagnosisCategory
    summary: str
    detail: str
    resolution: str

    def _dedupe_key(self) -> tuple[str, ...]:
        """Return a key identifying this diagnosis by its normalized causes.

        Node and reason counts in scheduler messages (e.g. `0/3 nodes are
        available: 3 Insufficient cpu`) change as cluster capacity fluctuates
        without the underlying cause changing, so they are removed and the
        reasons are sorted for `Unschedulable` diagnoses. Distinct causes
        (e.g. `Insufficient cpu` vs `Insufficient ephemeral-storage`) still
        produce distinct keys. Other categories compare exactly, so failures
        that differ only in a number (e.g. a container name or image tag) are
        not collapsed.
        """
        if self.category in _UNSCHEDULABLE_CATEGORIES:
            return (
                self.category.value,
                self.summary,
                *_normalize_scheduler_reasons(self.detail),
            )
        return (self.category.value, self.summary, self.detail)


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
                category=DiagnosisCategory.IMAGE_PULL_ERROR,
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
                category=DiagnosisCategory.CRASH_LOOP_BACKOFF,
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
                category=DiagnosisCategory.OOM_KILLED,
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
                category=DiagnosisCategory.EVICTED,
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


def _categorize_unschedulable(message: str) -> DiagnosisCategory:
    """Map a scheduler `Unschedulable` message to a specific category.

    The cause only appears in the human-readable condition message, so this
    matches on substrings and is intentionally tolerant of wording changes.
    Falls back to the generic `UNSCHEDULABLE` when the cause is unknown or
    the message is empty.
    """
    text = message.lower()
    if "taint" in text:
        return DiagnosisCategory.UNSCHEDULABLE_TAINT
    # Match affinity/selector wording explicitly rather than a generic
    # "didn't match", which would also catch unrelated reasons such as
    # "didn't match pod topology spread constraints".
    if "affinity" in text or "node selector" in text:
        return DiagnosisCategory.UNSCHEDULABLE_NODE_AFFINITY
    if "insufficient" in text:
        return DiagnosisCategory.UNSCHEDULABLE_INSUFFICIENT_RESOURCES
    return DiagnosisCategory.UNSCHEDULABLE


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
                category=_categorize_unschedulable(message),
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
            category=DiagnosisCategory.EVICTED,
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
