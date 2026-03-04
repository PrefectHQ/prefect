"""Centralized registry of process exit code explanations and resolution hints.

Consumed by the worker and runner to emit actionable log messages when flow run
infrastructure exits with a non-zero status code.
"""

import logging
from dataclasses import dataclass


@dataclass(frozen=True)
class ExitCodeInfo:
    """Human-readable explanation and resolution for a process exit code."""

    explanation: str
    resolution: str
    log_level: int = logging.ERROR


EXIT_CODE_HINTS: dict[int, ExitCodeInfo] = {
    0: ExitCodeInfo(
        explanation="Process exited cleanly.",
        resolution="No action needed.",
        log_level=logging.INFO,
    ),
    -9: ExitCodeInfo(
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
    -15: ExitCodeInfo(
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
    1: ExitCodeInfo(
        explanation="Process exited with a general error.",
        resolution=(
            "Check the flow run logs for an unhandled exception or assertion error."
        ),
    ),
    125: ExitCodeInfo(
        explanation="Container failed to run (Docker/OCI exit code 125).",
        resolution=(
            "Verify the container image exists, the entrypoint is correct, and"
            " the container runtime is healthy."
        ),
    ),
    126: ExitCodeInfo(
        explanation="Command found but not executable (permission denied).",
        resolution=(
            "Check file permissions on the entrypoint script or binary. Ensure the"
            " file has the executable bit set."
        ),
    ),
    127: ExitCodeInfo(
        explanation="Command not found.",
        resolution=(
            "Verify that the entrypoint command or script is installed in the"
            " execution environment. Check your PATH and container image contents."
        ),
    ),
    137: ExitCodeInfo(
        explanation="Process was killed, likely due to an out-of-memory (OOM) condition.",
        resolution=(
            "Increase the memory allocation for the flow run infrastructure."
            " In Kubernetes, raise the memory limit in the job template."
            " In ECS, increase the task memory."
        ),
    ),
    143: ExitCodeInfo(
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
    247: ExitCodeInfo(
        explanation="Process was terminated due to high memory usage.",
        resolution=(
            "Increase the memory allocation for the flow run infrastructure."
            " Consider profiling memory usage to find the source of consumption."
        ),
    ),
}


def get_exit_code_info(code: int) -> ExitCodeInfo:
    """Return the `ExitCodeInfo` for *code*.

    Known codes return a specific explanation and resolution. Unknown non-zero
    codes return a generic entry. Code 0 always returns the "exited cleanly"
    entry.
    """
    try:
        return EXIT_CODE_HINTS[code]
    except KeyError:
        return ExitCodeInfo(
            explanation=f"Process exited with unexpected status code {code}.",
            resolution=(
                "Check the flow run logs and infrastructure logs for more details."
            ),
        )
