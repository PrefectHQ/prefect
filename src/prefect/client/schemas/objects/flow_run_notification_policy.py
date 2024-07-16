from typing import (
    List,
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
    field_validator,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    validate_message_template_variables,
)
from prefect.utilities.collections import listrepr

DEFAULT_AGENT_WORK_POOL_NAME = "default-agent-pool"
FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS = [
    "flow_run_notification_policy_id",
    "flow_id",
    "flow_name",
    "flow_run_url",
    "flow_run_id",
    "flow_run_name",
    "flow_run_parameters",
    "flow_run_state_type",
    "flow_run_state_name",
    "flow_run_state_timestamp",
    "flow_run_state_message",
]


class FlowRunNotificationPolicy(ObjectBaseModel):
    """An ORM representation of a flow run notification."""

    is_active: bool = Field(
        default=True, description="Whether the policy is currently active"
    )
    state_names: List[str] = Field(
        default=..., description="The flow run states that trigger notifications"
    )
    tags: List[str] = Field(
        default=...,
        description="The flow run tags that trigger notifications (set [] to disable)",
    )
    block_document_id: UUID = Field(
        default=..., description="The block document ID used for sending notifications"
    )
    message_template: Optional[str] = Field(
        default=None,
        description=(
            "A templatable notification message. Use {braces} to add variables."
            " Valid variables include:"
            f" {listrepr(sorted(FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS), sep=', ')}"
        ),
        examples=[
            "Flow run {flow_run_name} with id {flow_run_id} entered state"
            " {flow_run_state_name}."
        ],
    )

    @field_validator("message_template")
    @classmethod
    def validate_message_template_variables(cls, v):
        return validate_message_template_variables(v)
