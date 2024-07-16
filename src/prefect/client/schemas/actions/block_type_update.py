from typing import Optional

from pydantic import Field

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import ActionBaseModel
from prefect.utilities.pydantic import get_class_fields_only


class BlockTypeUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block type."""

    logo_url: Optional[objects.HttpUrl] = Field(None)
    documentation_url: Optional[objects.HttpUrl] = Field(None)
    description: Optional[str] = Field(None)
    code_example: Optional[str] = Field(None)

    @classmethod
    def updatable_fields(cls) -> set:
        return get_class_fields_only(cls)
