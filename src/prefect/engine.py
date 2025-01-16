import os
import sys
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

from prefect._internal.compatibility.migration import getattr_migration
from prefect.exceptions import (
    Abort,
    Pause,
)
from prefect.logging.loggers import (
    get_logger,
)
from prefect.utilities.asyncutils import (
    run_coro_as_sync,
)

if TYPE_CHECKING:
    import logging

    from prefect.flow_engine import FlowRun
    from prefect.flows import Flow
    from prefect.logging.loggers import LoggingAdapter

engine_logger: "logging.Logger" = get_logger("engine")


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

    try:
        from prefect.flow_engine import (
            flow_run_logger,
            load_flow,
            load_flow_run,
            run_flow,
        )

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

        # run the flow
        if flow.isasync:
            run_coro_as_sync(run_flow(flow, flow_run=flow_run, error_logger=run_logger))
        else:
            run_flow(flow, flow_run=flow_run, error_logger=run_logger)

    except Abort as abort_signal:
        abort_signal: Abort
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' aborted by orchestrator:"
            f" {abort_signal}"
        )
        exit(0)
    except Pause as pause_signal:
        pause_signal: Pause
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' is paused: {pause_signal}"
        )
        exit(0)
    except Exception:
        engine_logger.error(
            (
                f"Engine execution of flow run '{flow_run_id}' exited with unexpected "
                "exception"
            ),
            exc_info=True,
        )
        exit(1)
    except BaseException:
        engine_logger.error(
            (
                f"Engine execution of flow run '{flow_run_id}' interrupted by base "
                "exception"
            ),
            exc_info=True,
        )
        # Let the exit code be determined by the base exception type
        raise

__getattr__: Callable[[str], Any] = getattr_migration(__name__)
