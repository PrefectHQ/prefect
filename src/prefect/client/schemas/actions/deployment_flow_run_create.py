from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.client.schemas.objects import FlowRunPolicy

from .state_create import StateCreate


class DeploymentFlowRunCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run from a deployment."""

    # FlowRunCreate states must be provided as StateCreate objects
    state: Optional[StateCreate] = Field(
        default=None, description="The state of the flow run to create"
    )

    name: Optional[str] = Field(default=None, description="The name of the flow run.")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="The parameters for the flow run."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="The context for the flow run."
    )
    infrastructure_document_id: Optional[UUID] = Field(None)
    empirical_policy: FlowRunPolicy = Field(default_factory=FlowRunPolicy)
    tags: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)
    parent_task_run_id: Optional[UUID] = Field(None)
    work_queue_name: Optional[str] = Field(None)
    job_variables: Optional[dict] = Field(None)
