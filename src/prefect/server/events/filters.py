from typing import List, Optional

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.server.database.interface import PrefectDBInterface

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect.server.schemas.filters import (
    PrefectFilterBaseModel,
    PrefectOperatorFilterBaseModel,
)
from prefect.server.utilities.schemas.fields import DateTimeTZ


class AutomationFilterCreated(PrefectFilterBaseModel):
    """Filter by `Automatio.created`."""

    before_: Optional[DateTimeTZ] = Field(
        default=None,
        description="Only include automations created before this datetime",
    )

    def _get_filter_list(self, db: PrefectDBInterface) -> list:
        filters = []
        if self.before_ is not None:
            filters.append(db.Automation.created <= self.before_)
        return filters


class AutomationFilter(PrefectOperatorFilterBaseModel):
    created: Optional[AutomationFilterCreated] = Field(
        default=None, description="Filter criteria for `Automation.created`"
    )

    def _get_filter_list(self, db: PrefectDBInterface) -> List:
        filters = []

        if self.created is not None:
            filters.append(self.created.as_sql_filter(db))

        return filters
