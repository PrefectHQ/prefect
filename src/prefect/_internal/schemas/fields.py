from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreatedBy(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the creator of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the creator of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the creator."
    )


class UpdatedBy(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the updater of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the updater of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the updater."
    )
