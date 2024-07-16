from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class FlowRunNotificationPolicyUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a flow run notification policy."""

    is_active: Optional[bool] = Field(None)
    state_names: Optional[List[str]] = Field(None)
    tags: Optional[List[str]] = Field(None)
    block_document_id: Optional[UUID] = Field(None)
    message_template: Optional[str] = Field(None)
