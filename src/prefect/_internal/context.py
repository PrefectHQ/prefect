"""
Run context from environment variables for infrastructure code.

This module provides context management for code that runs before flow execution
begins (pull steps, workers, deployment phases). It enables structured logging
and error handling with proper flow run association when FlowRunContext isn't
available yet.
"""

import os
from contextvars import ContextVar
from logging import Logger
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from prefect.context import ContextModel

if TYPE_CHECKING:
    from logging import LoggerAdapter


class _EnvironmentRunContext(ContextModel):
    """
    Run context created from environment variables for infrastructure code.

    Provides structured access to flow run, deployment, and work pool information
    during pre-execution phases when FlowRunContext isn't available yet. Created
    from environment variables set by workers/runners.

    This is an internal context used by infrastructure code (pull steps, workers,
    runners) that executes before the flow run begins.

    Attributes:
        flow_run_id: ID of the flow run being prepared
        deployment_id: ID of the deployment being executed
        work_pool_name: Name of the work pool executing the deployment

    Example:
        ```python
        # In pull steps or worker code
        ctx = _EnvironmentRunContext.from_environment()
        if ctx:
            with ctx:
                logger = ctx.get_logger(__name__)
                logger.info("Running pull step")
        ```
    """

    flow_run_id: UUID | None = None
    deployment_id: UUID | None = None
    work_pool_name: str | None = None

    __var__: ClassVar[ContextVar["_EnvironmentRunContext"]] = ContextVar(
        "environment_run_context"
    )

    @classmethod
    def from_environment(cls) -> "_EnvironmentRunContext | None":
        """
        Create an _EnvironmentRunContext from environment variables if available.

        Reads PREFECT__FLOW_RUN_ID and other deployment-related environment
        variables set by workers/runners. Returns None if no flow run context
        is available in the environment.

        Returns:
            _EnvironmentRunContext if environment variables are set, None otherwise
        """
        flow_run_id_str = os.getenv("PREFECT__FLOW_RUN_ID")
        if not flow_run_id_str:
            return None

        deployment_id_str = os.getenv("PREFECT__DEPLOYMENT_ID")
        work_pool_name = os.getenv("PREFECT__WORK_POOL_NAME")

        return cls(
            flow_run_id=UUID(flow_run_id_str),
            deployment_id=UUID(deployment_id_str) if deployment_id_str else None,
            work_pool_name=work_pool_name,
        )

    def get_logger(self, name: str) -> "LoggerAdapter[Logger]":
        """
        Get a logger with run context attached.

        Creates a logger that will include flow run ID and other metadata
        in log records, enabling proper association in the API even when
        FlowRunContext isn't available.

        Args:
            name: Logger name (typically __name__)

        Returns:
            PrefectLogAdapter with context metadata attached
        """
        from prefect.logging.loggers import PrefectLogAdapter, get_logger

        logger = get_logger(name)
        extra: dict[str, str] = {}

        if self.flow_run_id:
            extra["flow_run_id"] = str(self.flow_run_id)
        if self.deployment_id:
            extra["deployment_id"] = str(self.deployment_id)
        if self.work_pool_name:
            extra["work_pool_name"] = self.work_pool_name

        return PrefectLogAdapter(logger, extra=extra)
