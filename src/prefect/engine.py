from __future__ import annotations

import asyncio
import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

from prefect._internal.compatibility.migration import getattr_migration
from prefect.exceptions import (
    Abort,
    Pause,
    TerminationSignal,
)
from prefect.logging.loggers import get_logger

if TYPE_CHECKING:
    import logging

    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow
    from prefect.logging.loggers import LoggingAdapter

engine_logger: "logging.Logger" = get_logger("engine")


@contextmanager
def handle_engine_signals(flow_run_id: UUID | None = None):
    """
    Handle signals from the orchestrator to abort or pause the flow run or otherwise
    handle unexpected exceptions.

    This context manager will handle exiting the process depending on the signal received.

    Args:
        flow_run_id: The ID of the flow run to handle signals for.

    Example:
        ```python
        from prefect import flow
        from prefect.engine import handle_engine_signals
        from prefect.flow_engine import run_flow

        @flow
        def my_flow():
            print("Hello, world!")

        with handle_engine_signals():
            run_flow(my_flow)
        ```
    """
    try:
        yield
    except Abort:
        if flow_run_id:
            msg = f"Execution of flow run '{flow_run_id}' aborted by orchestrator."
        else:
            msg = "Execution aborted by orchestrator."
        engine_logger.info(msg)
        exit(0)
    except Pause:
        if flow_run_id:
            msg = f"Execution of flow run '{flow_run_id}' is paused."
        else:
            msg = "Execution is paused."
        engine_logger.info(msg)
        exit(0)
    except TerminationSignal:
        from prefect._internal import control_listener

        # A TerminationSignal can mean either:
        # - an expected runner-driven control action (today: cancel intent),
        # - or a raw external termination with no runner intent attached.
        #
        # Only the first case should translate to a clean process exit.
        if control_listener.get_intent() == "cancel":
            if flow_run_id:
                msg = f"Execution of flow run '{flow_run_id}' was cancelled."
            else:
                msg = "Execution was cancelled."
            engine_logger.info(msg)
            exit(0)
        raise
    except Exception:
        if flow_run_id:
            msg = f"Execution of flow run '{flow_run_id}' exited with unexpected exception"
        else:
            msg = "Execution exited with unexpected exception"
        engine_logger.error(msg, exc_info=True)
        exit(1)
    except BaseException:
        if flow_run_id:
            msg = f"Execution of flow run '{flow_run_id}' interrupted by base exception"
        else:
            msg = "Execution interrupted by base exception"
        engine_logger.error(msg, exc_info=True)
        # Let the exit code be determined by the base exception type
        raise


if __name__ == "__main__":
    try:
        flow_run_id: UUID = UUID(
            sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PREFECT__FLOW_RUN_ID")
        )
    except Exception:
        engine_logger.error(
            f"Invalid flow run id. Received arguments: {sys.argv}", exc_info=True
        )
        exit(1)

    # Connect back to the runner's control channel before running any
    # flow code. The listener will not ack a control intent until
    # `capture_sigterm()` installs Prefect's SIGTERM handler, so startup-time
    # cancels cannot be acknowledged before the engine is ready to consume
    # the synthetic signal. No-op if PREFECT__CONTROL_PORT/TOKEN are absent.
    from prefect._internal.control_listener import (
        start as _start_control_listener,
    )

    _start_control_listener()

    with handle_engine_signals(flow_run_id):
        from prefect.flow_engine import (
            flow_run_logger,
            load_flow,
            load_flow_run,
            run_flow,
        )
        from prefect.telemetry._metrics import RunMetrics

        flow_run: "FlowRun" = load_flow_run(flow_run_id=flow_run_id)
        run_logger: "LoggingAdapter" = flow_run_logger(flow_run=flow_run)

        try:
            flow: "Flow[..., Any]" = load_flow(flow_run)
        except Exception:
            run_logger.error(
                "Unexpected exception encountered when trying to load flow",
                exc_info=True,
            )
            raise

        # Run async flows on a main-thread event loop in this subprocess so
        # `capture_sigterm()` can install Prefect's SIGTERM bridge. Using the
        # shared run-sync loop here moves execution off the main thread, which
        # prevents graceful cancellation from ever becoming ready.
        with RunMetrics(flow_run, flow):
            _run_result: object = run_flow(
                flow, flow_run=flow_run, error_logger=run_logger
            )
            if asyncio.iscoroutine(_run_result):
                asyncio.run(_run_result)


__getattr__: Callable[[str], Any] = getattr_migration(__name__)
