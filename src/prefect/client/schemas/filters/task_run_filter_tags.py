from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin


class TaskRunFilterTags(PrefectBaseModel, OperatorMixin):
    """Filter by `TaskRun.tags`."""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Task runs will be returned only if their tags are a"
            " superset of the list"
        ),
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include task runs without tags"
    )