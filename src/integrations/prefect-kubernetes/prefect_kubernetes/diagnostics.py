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


_UNSCHEDULABLE_DETAIL_PREFIX = (
    "Kubernetes cannot find a suitable node to run this pod. "
)
_NODE_SUMMARY_PATTERN = re.compile(r"^0/\d+ nodes are available:")
_COUNTED_REASON_PATTERN = re.compile(r"^\d+ (?P<reason>\S.*)$")
_REASON_BOUNDARY_PATTERN = re.compile(r", (?=\d+ )")
_DEFAULT_PREEMPTION_PREFIX = "preemption:"
_NODE_DECLARED_FEATURES_PATTERN = re.compile(
    r"^node declared features check failed - unsatisfied requirements: "
    r"(?P<requirements>[^,]+(?:, [^,]+)*)$"
)
_PREFILTER_PATTERN = re.compile(r"^Node\(s\) failed PreFilter plugin \S+$")
_KNOWN_FILTER_REASON_PATTERNS = (
    re.compile(r"^[Ii]nsufficient [A-Za-z0-9./_-]+$"),
    re.compile(r"^node\(s\) had untolerated taint(?: \{[^{}]*\})?$"),
    re.compile(r"^node\(s\) didn't match Pod's node affinity/selector$"),
    re.compile(r"^node\(s\) had volume node affinity conflict$"),
    re.compile(r"^node\(s\) didn't match pod topology spread constraints$"),
    re.compile(r"^cannot allocate all claims$"),
    re.compile(r"^Preemption is not helpful for scheduling$"),
    re.compile(r"^No preemption victims found for incoming pod$"),
)

_UNSCHEDULABLE_CATEGORIES = frozenset(
    {
        DiagnosisCategory.UNSCHEDULABLE,
        DiagnosisCategory.UNSCHEDULABLE_INSUFFICIENT_RESOURCES,
        DiagnosisCategory.UNSCHEDULABLE_NODE_AFFINITY,
        DiagnosisCategory.UNSCHEDULABLE_TAINT,
    }
)


def _normalize_scheduler_reason(reason: str) -> str | None:
    """Canonicalize one recognized Kubernetes-owned filter reason."""
    if match := _NODE_DECLARED_FEATURES_PATTERN.fullmatch(reason):
        requirements = match.group("requirements").split(", ")
        if any(requirement != requirement.strip() for requirement in requirements):
            return None
        return (
            "node declared features check failed - unsatisfied requirements: "
            + ", ".join(sorted(requirements))
        )

    if any(pattern.fullmatch(reason) for pattern in _KNOWN_FILTER_REASON_PATTERNS):
        return reason
    return None


def _split_default_preemption(post_filter: str) -> tuple[str | None, str] | None:
    """Separate a default-preemption summary from earlier post-filter output."""
    prefix = f"{_DEFAULT_PREEMPTION_PREFIX} "
    if post_filter.startswith(prefix):
        general_post_filter = None
        preemption_detail = post_filter.removeprefix(prefix)
    else:
        marker = f", {_DEFAULT_PREEMPTION_PREFIX} "
        marker_index = post_filter.find(marker)
        if marker_index <= 0:
            return None
        if post_filter.find(marker, marker_index + len(marker)) != -1:
            return None
        general_post_filter = post_filter[:marker_index]
        preemption_detail = post_filter[marker_index + len(marker) :]

    return general_post_filter, preemption_detail


def _normalize_post_filter(post_filter: str) -> list[tuple[str, str]] | None:
    """Preserve post-filter output, normalizing default-preemption summaries."""
    preemption = _split_default_preemption(post_filter)
    if preemption is None:
        if _DEFAULT_PREEMPTION_PREFIX in post_filter:
            return None
        return [("postfilter", post_filter)]

    general_post_filter, preemption_detail = preemption
    parsed_preemption = _parse_scheduler_message(preemption_detail)
    if not parsed_preemption or any(
        section != "filter" for section, _ in parsed_preemption
    ):
        return None

    normalized = []
    if general_post_filter:
        normalized.append(("postfilter", general_post_filter))
    normalized.extend(
        (f"postfilter/preemption/{section}", reason)
        for section, reason in parsed_preemption
    )
    return normalized


def _parse_scheduler_message(message: str) -> list[tuple[str, str]] | None:
    """Parse one complete, recognized Kubernetes scheduler message."""
    node_summary = _NODE_SUMMARY_PATTERN.match(message)
    if node_summary is None:
        return None

    remainder = message[node_summary.end() :]
    if not remainder:
        return []
    if not remainder.startswith(" ") or remainder.startswith("  "):
        return None
    payload = remainder.removeprefix(" ")
    if not payload:
        return None

    if payload.startswith(_DEFAULT_PREEMPTION_PREFIX):
        if not payload.startswith(f"{_DEFAULT_PREEMPTION_PREFIX} "):
            return None
        return _normalize_post_filter(payload)

    if ". " in payload:
        first_section, post_filter = payload.split(". ", 1)
        if not post_filter:
            return None
    elif payload.endswith("."):
        first_section = payload.removesuffix(".")
        post_filter = None
    else:
        return None

    if not first_section:
        return None

    normalized: list[tuple[str, str]] = []
    if first_section[0].isdigit():
        for part in _REASON_BOUNDARY_PATTERN.split(first_section):
            counted_reason = _COUNTED_REASON_PATTERN.fullmatch(part)
            if counted_reason is None:
                return None
            reason = _normalize_scheduler_reason(counted_reason.group("reason"))
            if reason is None:
                return None
            normalized.append(("filter", reason))
    elif _PREFILTER_PATTERN.fullmatch(first_section):
        normalized.append(("prefilter", first_section))
    else:
        return None

    if post_filter is not None:
        normalized_post_filter = _normalize_post_filter(post_filter)
        if normalized_post_filter is None:
            return None
        normalized.extend(normalized_post_filter)
    return normalized


def _scheduler_dedupe_key(detail: str) -> tuple[str, ...]:
    """Return a conservative key for recognized Kubernetes scheduler output.

    Unknown or malformed formats retain their exact text. This deliberately
    prefers an occasional duplicate log after an upstream format change over
    suppressing a meaningfully different diagnosis.
    """
    if not detail.startswith(_UNSCHEDULABLE_DETAIL_PREFIX):
        return ("scheduler/raw", detail)

    parsed = _parse_scheduler_message(detail.removeprefix(_UNSCHEDULABLE_DETAIL_PREFIX))
    if parsed is None:
        return ("scheduler/raw", detail)
    return (
        "scheduler/normalized",
        *(sorted(f"{section}: {reason}" for section, reason in parsed if reason)),
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

        Counts and ordering are normalized only for recognized Kubernetes
        scheduler formats. Unfamiliar scheduler output and all other diagnosis
        categories compare exactly, so upstream format changes or meaningful
        failures that differ only in a number are not collapsed.
        """
        if self.category in _UNSCHEDULABLE_CATEGORIES:
            return (
                self.category.value,
                self.summary,
                *_scheduler_dedupe_key(self.detail),
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
                detail=f"{_UNSCHEDULABLE_DETAIL_PREFIX}{message}".strip(),
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
