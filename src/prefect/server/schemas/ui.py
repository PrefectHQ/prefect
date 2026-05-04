"""Schemas for UI endpoints."""

from typing import Literal, Optional

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
    default_ui: Literal["v1", "v2"] = Field(
        description="The default UI used for neutral entry points when the browser has no saved UI preference."
    )
    available_uis: list[Literal["v1", "v2"]] = Field(
        default_factory=list,
        description="List of UI bundles currently available to this server.",
    )
    v1_base_url: Optional[str] = Field(
        default=None,
        description="The base URL for the legacy V1 UI, or null when unavailable.",
    )
    v2_base_url: Optional[str] = Field(
        default=None,
        description="The base URL for the V2 UI, or null when unavailable.",
    )
