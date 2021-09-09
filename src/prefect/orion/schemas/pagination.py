from pydantic import conint
from prefect.orion.utilities.schemas import PrefectBaseModel


class Pagination(PrefectBaseModel):
    # max limit is 200
    limit: conint(ge=0, le=200) = 200
    offset: conint(ge=0) = 0
