from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import Field, field_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    validate_artifact_key,
)


class ArtifactCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create an artifact."""

    key: Optional[str] = Field(None)
    type: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    data: Optional[Union[Dict[str, Any], Any]] = Field(None)
    metadata_: Optional[Dict[str, str]] = Field(None)
    flow_run_id: Optional[UUID] = Field(None)
    task_run_id: Optional[UUID] = Field(None)

    _validate_artifact_format = field_validator("key")(validate_artifact_key)
