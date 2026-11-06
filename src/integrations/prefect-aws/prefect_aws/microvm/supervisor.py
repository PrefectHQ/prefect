"""Runs a flow run in a forked child process and reports the child's crashes."""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import SetStateStatus
from prefect.context import refresh_global_settings_context
from prefect.engine import _drive_run_flow_result, handle_engine_signals
from prefect.events.worker import EventsWorker
from prefect.flow_engine import (
    _run_flow_from_runtime_entrypoint,
    flow_run_logger,
    load_flow_and_flow_run,
    run_flow,
)
from prefect.logging import get_logger
from prefect.logging.handlers import APILogWorker
from prefect.states import Crashed
from prefect_aws.microvm.payload import RunHookPayload

logger = get_logger("prefect_aws.microvm")

CHILD_OOM_SCORE_ADJ = 1000
WORKER_DRAIN_TIMEOUT_SECONDS = 5


def execute_flow_run(payload: RunHookPayload) -> None:
    """
    Run the flow run described by `payload` in the current process.

    Args:
        payload: The flow run to execute. If it has an `entrypoint`, the flow is
            loaded from that entrypoint, relative to `working_dir` when one is
            given. Otherwise the flow is loaded from the flow run's deployment.
    """
    if payload.entrypoint:
        if payload.working_dir:
            os.chdir(payload.working_dir)
        _run_flow_from_runtime_entrypoint(payload.flow_run_id, payload.entrypoint)
        return

    with handle_engine_signals(payload.flow_run_id):
        flow_run, flow = load_flow_and_flow_run(payload.flow_run_id)
        run_result = run_flow(
            flow, flow_run=flow_run, error_logger=flow_run_logger(flow_run=flow_run)
        )
        # `run_flow` returns an unstarted coroutine or generator for async and
        # generator flows; this runs it.
        _drive_run_flow_result(flow, run_result)


def run_child(payload: RunHookPayload) -> NoReturn:
    """
    Run the flow run in a forked child process, then exit the process.

    The exit code is 0 when the flow run finishes without raising and nonzero
    otherwise.

    Args:
        payload: The flow run to execute.
    """
    exit_code = 1
    try:
        # A process restored from a snapshot shares its random state with every
        # other process restored from the same snapshot.
        random.seed(os.urandom(32))
        _make_preferred_oom_victim()
        # Settings were resolved at import time, before `/run` set the environment.
        refresh_global_settings_context()
        exit_code = _flow_run_exit_code(payload)
        _drain_api_workers()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        # `os._exit` keeps the child from running the parent's exit handlers.
        os._exit(exit_code)


def supervise_flow_run(payload: RunHookPayload) -> int:
    """
    Run the flow run in a forked child and wait for the child to exit.

    If the child exits nonzero or is killed by a signal, and the flow run is not
    already in a final state, the flow run is moved to `Crashed`.

    Args:
        payload: The flow run to execute.

    Returns:
        The exit code for this process: 0 if the child exited 0, otherwise 1.
    """
    child_pid = os.fork()
    if child_pid == 0:
        run_child(payload)

    _, wait_status = os.waitpid(child_pid, 0)
    crash_reason = describe_child_exit(wait_status)
    if crash_reason is None:
        return 0

    logger.error(
        "Flow run %s child process %s %s.",
        payload.flow_run_id,
        child_pid,
        crash_reason,
    )
    try:
        report_crash(payload.flow_run_id, crash_reason)
    except Exception:
        logger.exception(
            "Could not report flow run %s as crashed.", payload.flow_run_id
        )
    return 1


def describe_child_exit(wait_status: int) -> str | None:
    """
    Describe how a child process ended, from its `os.waitpid` status.

    Args:
        wait_status: The status returned by `os.waitpid`.

    Returns:
        None if the child exited 0, otherwise a phrase such as
        `"was killed by signal 9"` or `"exited with code 1"`.
    """
    if os.WIFSIGNALED(wait_status):
        return f"was killed by signal {os.WTERMSIG(wait_status)}"
    exit_code = os.waitstatus_to_exitcode(wait_status)
    if exit_code == 0:
        return None
    return f"exited with code {exit_code}"


def report_crash(flow_run_id: UUID, crash_reason: str) -> None:
    """
    Move a flow run to `Crashed` unless it is already in a final state.

    The state is proposed without `force` first. `force` is used only if the
    plain proposal is not accepted.

    Args:
        flow_run_id: The ID of the flow run.
        crash_reason: How the flow run's process ended, for the state message.
    """
    # This process resolved its settings before `/run` set the API URL and key.
    refresh_global_settings_context()
    with get_client(sync_client=True) as client:
        flow_run = client.read_flow_run(flow_run_id)
        if flow_run.state is not None and flow_run.state.is_final():
            logger.info(
                "Flow run %s is already %s; not reporting a crash.",
                flow_run_id,
                flow_run.state.type.value,
            )
            return

        crashed = Crashed(message=f"Flow run process {crash_reason}.")
        result = client.set_flow_run_state(flow_run_id, crashed)
        if result.status != SetStateStatus.ACCEPT:
            result = client.set_flow_run_state(flow_run_id, crashed, force=True)
        logger.info(
            "Proposed Crashed for flow run %s: %s.", flow_run_id, result.status.value
        )


def _flow_run_exit_code(payload: RunHookPayload) -> int:
    try:
        execute_flow_run(payload)
    except SystemExit as exc:
        # The engine's signal handling calls `exit()` for aborts, pauses, and
        # unexpected exceptions.
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    except BaseException:
        logger.exception("Flow run %s raised an exception.", payload.flow_run_id)
        return 1
    return 0


def _make_preferred_oom_victim() -> None:
    # Under memory pressure the kernel then kills this child before the parent,
    # which is the process that reports the crash.
    try:
        Path("/proc/self/oom_score_adj").write_text(str(CHILD_OOM_SCORE_ADJ))
    except OSError:
        logger.warning("Could not set the flow run process's oom_score_adj.")


def _drain_api_workers() -> None:
    # `os._exit` skips the exit handlers that would otherwise send queued logs
    # and events.
    try:
        APILogWorker.drain_all(timeout=WORKER_DRAIN_TIMEOUT_SECONDS)
        EventsWorker.drain_all(timeout=WORKER_DRAIN_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("Could not send queued logs and events.")
