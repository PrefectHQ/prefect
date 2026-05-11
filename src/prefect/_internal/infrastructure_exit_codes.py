"""Centralized registry of infrastructure process exit code explanations and
resolution hints.

Consumed by the worker and runner to emit actionable log messages when flow run
infrastructure exits with a non-zero status code.
"""

import logging
from dataclasses import dataclass


@dataclass(frozen=True)
class InfrastructureExitInfo:
    """Human-readable explanation and resolution for an infrastructure process exit code."""

    explanation: str
    resolution: str
    log_level: int = logging.ERROR


INFRASTRUCTURE_EXIT_HINTS: dict[int, InfrastructureExitInfo] = {
    0: InfrastructureExitInfo(
        explanation="Process exited cleanly.",
        resolution="No action needed.",
        log_level=logging.INFO,
    ),
    -9: InfrastructureExitInfo(
        explanation=(
            "Process exited due to a SIGKILL signal. Typically caused by the"
            " operating system terminating the process for exceeding memory limits,"
            " or by manual cancellation."
        ),
        resolution=(
            "Check whether the flow run exceeded its memory allocation. If running"
            " in a container, increase the memory limit. If this was intentional"
            " cancellation, no action is needed."
        ),
        log_level=logging.INFO,
    ),
    -15: InfrastructureExitInfo(
        explanation=(
            "Process exited due to a SIGTERM signal. Typically caused by graceful"
            " shutdown or manual cancellation."
        ),
        resolution=(
            "If this was caused by cancellation, no action is needed. Otherwise,"
            " check for infrastructure scaling events or deployment rollovers."
        ),
        log_level=logging.INFO,
    ),
    1: InfrastructureExitInfo(
        explanation="Process exited with a general error.",
        resolution=(
            "Check the flow run logs for an unhandled exception or assertion error."
        ),
    ),
    125: InfrastructureExitInfo(
        explanation="Container failed to run (Docker/OCI exit code 125).",
        resolution=(
            "Verify the container image exists, the entrypoint is correct, and"
            " the container runtime is healthy."
        ),
    ),
    126: InfrastructureExitInfo(
        explanation="Command found but not executable (permission denied).",
        resolution=(
            "Check file permissions on the entrypoint script or binary. Ensure the"
            " file has the executable bit set."
        ),
    ),
    127: InfrastructureExitInfo(
        explanation="Command not found.",
        resolution=(
            "Verify that the entrypoint command or script is installed in the"
            " execution environment. Check your PATH and container image contents."
        ),
    ),
    137: InfrastructureExitInfo(
        explanation="Process was killed, likely due to an out-of-memory (OOM) condition.",
        resolution=(
            "Increase the memory allocation for the flow run infrastructure."
            " In Kubernetes, raise the memory limit in the job template."
            " In ECS, increase the task memory."
        ),
    ),
    143: InfrastructureExitInfo(
        explanation=(
            "Process received SIGTERM via the container runtime. This is the"
            " containerized equivalent of exit code -15."
        ),
        resolution=(
            "If this was caused by cancellation or a scaling event, no action is"
            " needed. Otherwise, check for pod evictions or ECS task stops."
        ),
        log_level=logging.INFO,
    ),
    247: InfrastructureExitInfo(
        explanation="Process was terminated due to high memory usage.",
        resolution=(
            "Increase the memory allocation for the flow run infrastructure."
            " Consider profiling memory usage to find the source of consumption."
        ),
    ),
    # Windows Ctrl+C / Ctrl+Break (STATUS_CONTROL_C_EXIT)
    0xC000013A: InfrastructureExitInfo(
        explanation=(
            "Process was terminated due to a Ctrl+C or Ctrl+Break signal."
            " Typically caused by manual cancellation."
        ),
        resolution="If this was intentional cancellation, no action is needed.",
        log_level=logging.INFO,
    ),
}


def get_infrastructure_exit_info(code: int) -> InfrastructureExitInfo:
    """Return the `InfrastructureExitInfo` for *code*.

    Known codes return a specific explanation and resolution. Unknown non-zero
    codes return a generic entry. Code 0 always returns the "exited cleanly"
    entry.
    """
    try:
        return INFRASTRUCTURE_EXIT_HINTS[code]
    except KeyError:
        return InfrastructureExitInfo(
            explanation="Process exited with an unexpected status code.",
            resolution=(
                "Check the flow run logs and infrastructure logs for more details."
            ),
        )
