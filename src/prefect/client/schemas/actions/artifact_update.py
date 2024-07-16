from typing import Any, Dict, Optional, Union

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class ArtifactUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update an artifact."""

    data: Optional[Union[Dict[str, Any], Any]] = Field(None)
    description: Optional[str] = Field(None)
    metadata_: Optional[Dict[str, str]] = Field(None)