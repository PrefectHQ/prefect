"""Schemas for UI endpoints."""

from typing import Optional

from pydantic import BaseModel, Field

from prefect.server.schemas.core import TaskRun as CoreTaskRun


class UITaskRun(CoreTaskRun):
    """A task run with additional details for display in the UI."""

    flow_run_name: Optional[str] = None


class UISettings(BaseModel):
    """Runtime UI configuration returned by /ui-settings endpoint."""

    api_url: str = Field(description="The base URL for API requests.")
    csrf_enabled: bool = Field(description="Whether CSRF protection is enabled.")
    auth: Optional[str] = Field(
        description="Authentication method (e.g., 'BASIC') or null if disabled."
    )
    flags: list[str] = Field(
        default_factory=list, description="List of enabled feature flags."
    )
