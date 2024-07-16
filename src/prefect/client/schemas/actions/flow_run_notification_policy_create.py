from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    validate_message_template_variables,
)
from prefect.client.schemas.objects.flow_run_notification_policy import (
    FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS,
)
from prefect.utilities.collections import listrepr


class FlowRunNotificationPolicyCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow run notification policy."""

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
