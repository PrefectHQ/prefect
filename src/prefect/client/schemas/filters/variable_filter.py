from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin
from .variable_filter_id import VariableFilterId
from .variable_filter_name import VariableFilterName
from .variable_filter_tags import VariableFilterTags


class VariableFilter(PrefectBaseModel, OperatorMixin):
    """Filter variables. Only variables matching all criteria will be returned"""

    id: Optional[VariableFilterId] = Field(
        default=None, description="Filter criteria for `Variable.id`"
    )
    name: Optional[VariableFilterName] = Field(
        default=None, description="Filter criteria for `Variable.name`"
    )
    tags: Optional[VariableFilterTags] = Field(
        default=None, description="Filter criteria for `Variable.tags`"
    )