"""Schemas for UI endpoints."""

from prefect.server.schemas.core import TaskRun as CoreTaskRun


class TaskRun(CoreTaskRun):
    """A task run with additional details for display in the UI."""

    flow_run_name: str | None = None
