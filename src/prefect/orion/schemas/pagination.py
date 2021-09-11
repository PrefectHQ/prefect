from fastapi import Body
import prefect
from pydantic import conint
from prefect.orion.utilities.schemas import PrefectBaseModel


class Pagination(PrefectBaseModel):
    limit: conint(
        ge=0, le=prefect.settings.orion.api.default_limit
    ) = prefect.settings.orion.api.default_limit
    offset: conint(ge=0) = 0
