"""Runs a flow run in a forked child process and reports the child's crashes."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from types import FrameType
from typing import NoReturn
from uuid import UUID

# These imports stay at module level so that they are loaded at startup and are
# in the MicroVM snapshot, taken after `/ready`.
from prefect._internal.control_listener import configure_from_env
from prefect._internal.metrics import RunMetrics
from prefect.client.orchestration import SyncPrefectClient, get_client
from prefect.context import refresh_global_settings_context
from prefect.engine import _drive_run_flow_result, handle_engine_signals
from prefect.events.worker import EventsWorker
from prefect.exceptions import Abort, Pause
from prefect.flow_engine import (
    _run_flow_from_runtime_entrypoint,
    flow_run_logger,
    load_flow,
    load_flow_run,
    run_flow,
)
from prefect.logging import get_logger
from prefect.logging.configuration import setup_logging
from prefect.logging.handlers import APILogWorker
from prefect.states import Crashed
from prefect.utilities.engine import propose_state_sync
from prefect_aws.microvm.payload import RunHookPayload

logger = get_logger("prefect_aws.microvm")

CHILD_OOM_SCORE_ADJ = 1000
OOM_SCORE_ADJ_PATH = Path("/proc/self/oom_score_adj")
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

    # The same sequence as `python -m prefect.engine`.
    configure_from_env()
    with handle_engine_signals(payload.flow_run_id):
        flow_run = load_flow_run(flow_run_id=payload.flow_run_id)
        run_logger = flow_run_logger(flow_run=flow_run)
        try:
            flow = load_flow(flow_run)
        except Exception:
            run_logger.exception(
                "Unexpected exception encountered when trying to load flow"
            )
            raise
        with RunMetrics(flow_run, flow):
            run_result = run_flow(flow, flow_run=flow_run, error_logger=run_logger)
            # `run_flow` returns an unstarted coroutine or generator for async
            # and generator flows; this runs it.
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
        # The parent blocks SIGTERM across the fork; the flow run gets the
        # default disposition, whatever handler the parent had.
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
        # Logging was configured at import time, before `/run` set the
        # environment. A fresh setup also replaces the console handler, whose
        # rich console lock a parent thread writing a log line at the fork may
        # still hold.
        setup_logging(incremental=False)
        _make_preferred_oom_victim()
        exit_code = _flow_run_exit_code(payload)
        _drain_api_workers()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        # `os._exit` keeps the child from running the parent's exit handlers.
        os._exit(exit_code)


def supervise_flow_run(
    payload: RunHookPayload, restored_signal_mask: set[signal.Signals] | None = None
) -> int:
    """
    Run the flow run in a forked child and wait for the child to exit.

    If the child exits nonzero or is killed by a signal, `Crashed` is proposed
    for the flow run. SIGTERM sent to this process is forwarded to the child.
    Call this from the main thread, after refreshing the global settings
    context from the environment that `/run` set; the child inherits those
    settings.

    Args:
        payload: The flow run to execute.
        restored_signal_mask: The signal mask to set once SIGTERM is forwarded
            to the child. Defaults to the mask when this is called. A SIGTERM
            that is pending when the mask is set is forwarded to the child.

    Returns:
        The exit code for this process: 0 if the child exited 0, otherwise 1.
    """
    # Blocked across the fork so a SIGTERM that arrives before the forwarding
    # handler is installed waits for it instead of being lost. A hook handler still
    # running past `stop_serving`'s wait, one trickling bytes, could take it instead.
    signal_mask_on_entry = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    if restored_signal_mask is None:
        restored_signal_mask = signal_mask_on_entry
    try:
        child_pid = os.fork()
    except BaseException:
        signal.pthread_sigmask(signal.SIG_SETMASK, restored_signal_mask)
        raise
    if child_pid == 0:
        run_child(payload)

    def forward_sigterm(signum: int, frame: FrameType | None) -> None:
        try:
            os.kill(child_pid, signum)
        except ProcessLookupError:
            pass

    # As PID 1 in the MicroVM, this process ignores any signal it has no
    # handler for, so SIGTERM would otherwise never reach the flow run.
    try:
        previous_sigterm_handler = signal.signal(signal.SIGTERM, forward_sigterm)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, restored_signal_mask)
    try:
        wait_status = _reap_until_collected(child_pid)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)

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
    Propose `Crashed` for a flow run. A flow run in a final state keeps it.

    Args:
        flow_run_id: The ID of the flow run.
        crash_reason: How the flow run's process ended, for the state message.
    """
    # When the settings from the `/run` environment fail to load, the crash is
    # still reported, with the API URL and credentials read directly from the
    # environment and the import-time settings for everything else.
    try:
        refresh_global_settings_context()
    except Exception:  # noqa: BLE001
        logger.warning(
            "Could not load the settings to report flow run %s as crashed. Using "
            "PREFECT_API_URL, PREFECT_API_KEY, and PREFECT_API_AUTH_STRING from "
            "the environment.",
            flow_run_id,
        )
        api_url = os.environ.get("PREFECT_API_URL")
        if not api_url:
            logger.error(
                "Could not report flow run %s as crashed because PREFECT_API_URL "
                "is not set.",
                flow_run_id,
            )
            return
        client = SyncPrefectClient(
            api_url,
            auth_string=os.environ.get("PREFECT_API_AUTH_STRING"),
            api_key=os.environ.get("PREFECT_API_KEY"),
        )
    else:
        client = get_client(sync_client=True)
    with client:
        try:
            state = propose_state_sync(
                client,
                Crashed(message=f"Flow run process {crash_reason}."),
                flow_run_id=flow_run_id,
            )
        except (Abort, Pause) as exc:
            logger.info(
                "Flow run %s keeps its state; Crashed was not accepted: %s",
                flow_run_id,
                exc,
            )
            return
        logger.info("Flow run %s is now %s.", flow_run_id, state.type.value)


def _reap_until_collected(child_pid: int) -> int:
    # Orphaned grandchildren are reparented to PID 1, so this reaps them too.
    while True:
        pid, wait_status = os.waitpid(-1, 0)
        if pid == child_pid:
            return wait_status


def _flow_run_exit_code(payload: RunHookPayload) -> int:
    try:
        execute_flow_run(payload)
    except SystemExit as exc:
        # The engine's signal handling calls `exit()` for aborts, pauses, and
        # unexpected exceptions.
        if exc.code is None:
            return 0
        exit_code = exc.code if isinstance(exc.code, int) else 1
        # The OS keeps only the low 8 bits, so 256 would read as success.
        return exit_code if 0 <= exit_code <= 255 else 1
    except BaseException:
        logger.exception("Flow run %s raised an exception.", payload.flow_run_id)
        return 1
    return 0


def _make_preferred_oom_victim() -> None:
    # Under memory pressure the kernel then kills this child before the parent,
    # which is the process that reports the crash.
    try:
        OOM_SCORE_ADJ_PATH.write_text(str(CHILD_OOM_SCORE_ADJ))
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
