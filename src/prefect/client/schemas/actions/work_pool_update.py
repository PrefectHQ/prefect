from typing import Any, Dict, Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class WorkPoolUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work pool."""

    description: Optional[str] = Field(None)
    is_paused: Optional[bool] = Field(None)
    base_job_template: Optional[Dict[str, Any]] = Field(None)
    concurrency_limit: Optional[int] = Field(None)