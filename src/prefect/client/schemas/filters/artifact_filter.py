from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .artifact_filter_flow_run_id import ArtifactFilterFlowRunId
from .artifact_filter_id import ArtifactFilterId
from .artifact_filter_key import ArtifactFilterKey
from .artifact_filter_task_run_id import ArtifactFilterTaskRunId
from .artifact_filter_type import ArtifactFilterType
from .operator_mixin import OperatorMixin


class ArtifactFilter(PrefectBaseModel, OperatorMixin):
    """Filter artifacts. Only artifacts matching all criteria will be returned"""

    id: Optional[ArtifactFilterId] = Field(
        default=None, description="Filter criteria for `Artifact.id`"
    )
    key: Optional[ArtifactFilterKey] = Field(
        default=None, description="Filter criteria for `Artifact.key`"
    )
    flow_run_id: Optional[ArtifactFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `Artifact.flow_run_id`"
    )
    task_run_id: Optional[ArtifactFilterTaskRunId] = Field(
        default=None, description="Filter criteria for `Artifact.task_run_id`"
    )
    type: Optional[ArtifactFilterType] = Field(
        default=None, description="Filter criteria for `Artifact.type`"
    )
