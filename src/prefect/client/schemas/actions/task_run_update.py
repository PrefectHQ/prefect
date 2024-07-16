from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class TaskRunUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a task run"""

    name: Optional[str] = Field(None)