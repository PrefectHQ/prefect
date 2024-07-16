from typing import (
    Any,
    Dict,
)

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel


class Configuration(ObjectBaseModel):
    """An ORM representation of account info."""

    key: str = Field(default=..., description="Account info key")
    value: Dict[str, Any] = Field(default=..., description="Account info")
