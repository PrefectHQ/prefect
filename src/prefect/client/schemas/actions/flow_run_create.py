from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import ActionBaseModel

from .state_create import StateCreate


class FlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    deployment_id: Optional[UUID] = Field(None)
    flow_version: Optional[str] = Field(None)
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="The context for the flow run."
    )
    parent_task_run_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy
    )
    tags: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)