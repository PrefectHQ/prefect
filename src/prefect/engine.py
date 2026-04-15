from __future__ import annotations

import asyncio
import inspect
import os
import sys
from contextlib import contextmanager
from types import GeneratorType
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

from prefect._internal.compatibility.migration import getattr_migration
from prefect._internal.control_listener import (
    clear_intent,
    configure_from_env,
    get_intent,
)
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


def _drive_run_flow_result(flow: Any, run_result: object) -> None:
    """Execute deferred work for generator flows returned by `run_flow()`."""
    if getattr(flow, "isasync", False) and getattr(flow, "isgenerator", False):
        if not inspect.isasyncgen(run_result):
            return

        async def _consume_asyncgen() -> None:
            async for _ in run_result:
                pass

        asyncio.run(_consume_asyncgen())
        return

    if not getattr(flow, "isasync", False) and getattr(flow, "isgenerator", False):
        if not isinstance(run_result, GeneratorType):
            return
        for _ in run_result:
            pass
        return

    if getattr(flow, "isasync", False) and not getattr(flow, "isgenerator", False):
        if not asyncio.iscoroutine(run_result):
            return
        asyncio.run(run_result)


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
        # A TerminationSignal can mean either:
        # - an expected runner-driven control action (today: cancel intent),
        # - or a raw external termination with no runner intent attached.
        #
        # Only the first case should translate to a clean process exit.
        if get_intent() == "cancel":
            if flow_run_id:
                msg = f"Execution of flow run '{flow_run_id}' was cancelled."
            else:
                msg = "Execution was cancelled."
            engine_logger.info(msg)
            clear_intent()
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

    # Consume the runner control-channel bootstrap env before loading any
    # flow code, but do not connect yet. The actual socket connection is
    # established only while `capture_sigterm()` is active inside the flow
    # engine; cancels that land before then fall back to the existing
    # crash-style termination path.
    configure_from_env()

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
            _drive_run_flow_result(flow, _run_result)


__getattr__: Callable[[str], Any] = getattr_migration(__name__)
