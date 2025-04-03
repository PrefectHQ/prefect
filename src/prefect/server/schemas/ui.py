"""Schemas for UI endpoints."""

from typing import Optional

from prefect.server.schemas.core import TaskRun as CoreTaskRun


class UITaskRun(CoreTaskRun):
    """A task run with additional details for display in the UI."""

    flow_run_name: Optional[str] = None
