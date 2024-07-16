from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunNotificationPolicyFilterIsActive(PrefectBaseModel):
    """Filter by `FlowRunNotificationPolicy.is_active`."""

    eq_: Optional[bool] = Field(
        default=None,
        description=(
            "Filter notification policies for only those that are or are not active."
        ),
    )