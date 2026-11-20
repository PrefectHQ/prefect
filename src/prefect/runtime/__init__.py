"""
Module for easily accessing dynamic attributes for a given run, especially those generated from deployments.

Example usage:
    ```python
    from prefect.runtime import deployment

    print(f"This script is running from deployment {deployment.id} with parameters {deployment.parameters}")
    ```
"""

from logging import Logger

import prefect
from prefect.exceptions import MissingContextError
from prefect.logging import get_logger as _get_logger
from prefect.logging import get_run_logger as _get_run_logger
from prefect.logging.loggers import LoggingAdapter

from . import deployment, flow_run, task_run

# Keep `prefect` available to result-storage key templates.
__all__ = ["deployment", "flow_run", "get_logger", "prefect", "task_run"]


def get_logger() -> Logger | LoggingAdapter:
    """Get a logger for code that runs both inside and outside Prefect runs.

    Call this function where you log so it can use the current task or flow
    run. If no run is active, it falls back to the standard Prefect logger,
    which does not send logs to the Prefect API by default.
    """
    try:
        return _get_run_logger()
    except MissingContextError:
        return _get_logger()
