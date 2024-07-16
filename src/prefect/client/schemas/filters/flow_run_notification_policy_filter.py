from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .flow_run_notification_policy_filter_is_active import (
    FlowRunNotificationPolicyFilterIsActive,
)


class FlowRunNotificationPolicyFilter(PrefectBaseModel):
    """Filter FlowRunNotificationPolicies."""

    is_active: Optional[FlowRunNotificationPolicyFilterIsActive] = Field(
        default=FlowRunNotificationPolicyFilterIsActive(eq_=False),
        description="Filter criteria for `FlowRunNotificationPolicy.is_active`. ",
    )
