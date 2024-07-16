from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterFlowVersion(PrefectBaseModel):
    """Filter by `FlowRun.flow_version`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run flow_versions to include"
    )