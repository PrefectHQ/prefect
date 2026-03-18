"""Diagnostic functions for ECS task failures.

Pattern-matches ECS task EventBridge event details into structured failure
diagnoses with actionable resolution hints.  All diagnosis is performed from
the event payload alone — no additional AWS API calls are made.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InfrastructureDiagnosis:
    """Structured diagnosis of an infrastructure failure."""

    level: int
    summary: str
    detail: str
    resolution: str


def diagnose_ecs_task(
    event_detail: dict[str, Any],
) -> InfrastructureDiagnosis | None:
    """Diagnose an ECS task failure from an EventBridge event `detail`.

    Returns an `InfrastructureDiagnosis` for `STOPPED` tasks, or `None` if
    the task has not stopped or no actionable diagnosis can be produced.
    """
    if event_detail.get("lastStatus") != "STOPPED":
        return None

    stopped_reason: str = event_detail.get("stoppedReason") or ""
    stop_code: str = event_detail.get("stopCode") or ""

    # --- CannotPullContainerError (stoppedReason) --------------------------
    if "CannotPullContainerError" in stopped_reason:
        return InfrastructureDiagnosis(
            level=logging.ERROR,
            summary="Container image pull failed",
            detail=stopped_reason,
            resolution=(
                "Verify that the container image exists and the URI is correct."
                " If the image is in a private registry, ensure the task execution"
                " role has permissions to pull from it and that a repository"
                " authentication configuration is attached to the container definition."
            ),
        )

    # --- TaskFailedToStart (stopCode) --------------------------------------
    if stop_code == "TaskFailedToStart":
        return InfrastructureDiagnosis(
            level=logging.ERROR,
            summary="ECS task failed to start",
            detail=stopped_reason or "Task failed to start (no additional detail).",
            resolution=(
                "Check the stopped reason for specifics. Common causes include"
                " resource limits, missing IAM permissions, or networking"
                " misconfigurations. Review the ECS task and execution role policies."
            ),
        )

    # --- EssentialContainerExited (stopCode) --------------------------------
    if stop_code == "EssentialContainerExited":
        return _diagnose_container_exit_codes(event_detail, essential_exited=True)

    # --- Container exit code analysis (non-zero or null) -------------------
    containers: list[dict[str, Any]] = event_detail.get("containers", [])
    if containers:
        has_failure = any(
            c.get("exitCode") is None or c.get("exitCode") != 0 for c in containers
        )
        if has_failure:
            return _diagnose_container_exit_codes(event_detail)

    return None


def _diagnose_container_exit_codes(
    event_detail: dict[str, Any],
    *,
    essential_exited: bool = False,
) -> InfrastructureDiagnosis:
    """Build a diagnosis from container exit codes in the event detail."""
    containers: list[dict[str, Any]] = event_detail.get("containers", [])

    null_exit: list[str] = []
    nonzero_exit: list[tuple[str, int]] = []

    for container in containers:
        name = container.get("name", "<unknown>")
        exit_code = container.get("exitCode")
        if exit_code is None:
            null_exit.append(name)
        elif exit_code != 0:
            nonzero_exit.append((name, exit_code))

    parts: list[str] = []
    if nonzero_exit:
        for name, code in nonzero_exit:
            parts.append(f"Container {name!r} exited with code {code}.")
    if null_exit:
        names = ", ".join(repr(n) for n in null_exit)
        parts.append(
            f"Container(s) {names} had no exit code, indicating the task"
            " was terminated by ECS or the underlying infrastructure."
        )

    detail = " ".join(parts) if parts else "No container exit code details available."

    if essential_exited:
        summary = "Essential container exited"
        resolution = (
            "An essential container in the task exited, causing the task to"
            " stop. Check the container logs for errors. If the exit was due"
            " to an application error, fix the underlying issue. If the"
            " container was killed by the infrastructure, consider increasing"
            " memory or CPU limits."
        )
    elif null_exit and not nonzero_exit:
        summary = "Task terminated by infrastructure"
        resolution = (
            "The task was stopped without container exit codes, which typically"
            " means ECS or the underlying infrastructure killed the task."
            " Common causes include spot instance interruptions, scaling"
            " events, or manual stops. Check CloudTrail and ECS service events"
            " for more context."
        )
    else:
        summary = "Container exited with non-zero exit code"
        resolution = (
            "One or more containers exited with a non-zero status code."
            " Check the container logs in CloudWatch for error details."
            " Exit code 137 often indicates an out-of-memory condition —"
            " consider increasing the task memory allocation."
        )

    level = logging.WARNING if (null_exit and not nonzero_exit) else logging.ERROR
    return InfrastructureDiagnosis(
        level=level,
        summary=summary,
        detail=detail,
        resolution=resolution,
    )
