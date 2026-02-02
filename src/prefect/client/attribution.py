"""
Attribution context for API requests.

This module provides functions to gather attribution headers that identify
the source of API requests (flow runs, deployments, workers) for usage tracking
and rate limit debugging.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def get_attribution_headers() -> dict[str, str]:
    """
    Gather attribution headers from the current execution context.

    These headers help Cloud track which flow runs, deployments, and workers
    are generating API requests for usage attribution and rate limit debugging.

    Headers are only included when values are available. All headers are optional.

    Returns:
        A dictionary of attribution headers to include in API requests.
    """
    headers: dict[str, str] = {}

    # Worker context (passed via environment variables from worker to flow run process)
    if worker_id := os.environ.get("PREFECT__WORKER_ID"):
        headers["X-Prefect-Worker-Id"] = worker_id
    if worker_name := os.environ.get("PREFECT__WORKER_NAME"):
        headers["X-Prefect-Worker-Name"] = worker_name

    # Flow run context - try to get from context first, fall back to env vars
    # Import here to avoid circular imports
    from prefect.context import FlowRunContext

    flow_run_ctx = FlowRunContext.get()

    if flow_run_ctx and flow_run_ctx.flow_run:
        flow_run = flow_run_ctx.flow_run
        headers["X-Prefect-Flow-Run-Id"] = str(flow_run.id)
        headers["X-Prefect-Flow-Run-Name"] = flow_run.name

        # Deployment info from flow run
        if flow_run.deployment_id:
            headers["X-Prefect-Deployment-Id"] = str(flow_run.deployment_id)
    else:
        # Fall back to environment variable for flow run ID
        if flow_run_id := os.environ.get("PREFECT__FLOW_RUN_ID"):
            headers["X-Prefect-Flow-Run-Id"] = flow_run_id

    # Note: We intentionally don't look up deployment name here to avoid:
    # 1. Potential circular imports
    # 2. API calls that could slow down every request
    # 3. Complexity with caching
    # The deployment_id is sufficient for Cloud to resolve the name.

    return headers
