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

    # Flow and deployment context - try to get from context first, fall back to env vars
    # Import here to avoid circular imports
    from prefect.context import FlowRunContext

    flow_run_ctx = FlowRunContext.get()

    if flow_run_ctx and flow_run_ctx.flow_run:
        flow_run = flow_run_ctx.flow_run

        # Flow info (use getattr for safety with mock/minimal FlowRun objects)
        if flow_id := getattr(flow_run, "flow_id", None):
            headers["X-Prefect-Flow-Id"] = str(flow_id)
        if flow_run_ctx.flow and getattr(flow_run_ctx.flow, "name", None):
            headers["X-Prefect-Flow-Name"] = flow_run_ctx.flow.name

        # Deployment info from flow run
        if deployment_id := getattr(flow_run, "deployment_id", None):
            headers["X-Prefect-Deployment-Id"] = str(deployment_id)
        # Deployment name is not on FlowRun, fall back to env var
        if deployment_name := os.environ.get("PREFECT__DEPLOYMENT_NAME"):
            headers["X-Prefect-Deployment-Name"] = deployment_name
    else:
        # Fall back to environment variables
        if flow_id := os.environ.get("PREFECT__FLOW_ID"):
            headers["X-Prefect-Flow-Id"] = flow_id
        if flow_name := os.environ.get("PREFECT__FLOW_NAME"):
            headers["X-Prefect-Flow-Name"] = flow_name
        if deployment_id := os.environ.get("PREFECT__DEPLOYMENT_ID"):
            headers["X-Prefect-Deployment-Id"] = deployment_id
        if deployment_name := os.environ.get("PREFECT__DEPLOYMENT_NAME"):
            headers["X-Prefect-Deployment-Name"] = deployment_name

    return headers
