import datetime

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel


class CsrfToken(ObjectBaseModel):
    token: str = Field(
        default=...,
        description="The CSRF token",
    )
    client: str = Field(
        default=..., description="The client id associated with the CSRF token"
    )
    expiration: datetime.datetime = Field(
        default=..., description="The expiration time of the CSRF token"
    )
