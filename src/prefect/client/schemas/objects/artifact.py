from typing import (
    Any,
    Dict,
    Optional,
    Union,
)
from uuid import UUID

from pydantic import (
    Field,
    field_validator,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    validate_max_metadata_length,
)


class Artifact(ObjectBaseModel):
    key: Optional[str] = Field(
        default=None, description="An optional unique reference key for this artifact."
    )
    type: Optional[str] = Field(
        default=None,
        description=(
            "An identifier that describes the shape of the data field. e.g. 'result',"
            " 'table', 'markdown'"
        ),
    )
    description: Optional[str] = Field(
        default=None, description="A markdown-enabled description of the artifact."
    )
    # data will eventually be typed as `Optional[Union[Result, Any]]`
    data: Optional[Union[Dict[str, Any], Any]] = Field(
        default=None,
        description=(
            "Data associated with the artifact, e.g. a result.; structure depends on"
            " the artifact type."
        ),
    )
    metadata_: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "User-defined artifact metadata. Content must be string key and value"
            " pairs."
        ),
    )
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run associated with the artifact."
    )
    task_run_id: Optional[UUID] = Field(
        default=None, description="The task run associated with the artifact."
    )

    @field_validator("metadata_")
    @classmethod
    def validate_metadata_length(cls, v):
        return validate_max_metadata_length(v)
