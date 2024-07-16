from typing import Any, Dict, List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.client.schemas.objects import FlowRunPolicy


class FlowRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run."""

    name: Optional[str] = Field(None)
    flow_version: Optional[str] = Field(None)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    empirical_policy: FlowRunPolicy = Field(default_factory=FlowRunPolicy)
    tags: List[str] = Field(default_factory=list)
    infrastructure_pid: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(None)
