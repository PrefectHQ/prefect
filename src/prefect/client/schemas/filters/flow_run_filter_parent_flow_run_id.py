from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin


class FlowRunFilterParentFlowRunId(PrefectBaseModel, OperatorMixin):
    """Filter for subflows of the given flow runs"""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run parents to include"
    )