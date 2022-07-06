import pydantic

from prefect.utilities.pydantic import add_type_dispatch


@add_type_dispatch
class Infrastructure(pydantic.BaseModel):
    type: str
