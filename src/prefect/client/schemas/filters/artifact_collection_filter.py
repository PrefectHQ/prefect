from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .artifact_collection_filter_flow_run_id import ArtifactCollectionFilterFlowRunId
from .artifact_collection_filter_key import ArtifactCollectionFilterKey
from .artifact_collection_filter_latest_id import ArtifactCollectionFilterLatestId
from .artifact_collection_filter_task_run_id import ArtifactCollectionFilterTaskRunId
from .artifact_collection_filter_type import ArtifactCollectionFilterType
from .operator_mixin import OperatorMixin


class ArtifactCollectionFilter(PrefectBaseModel, OperatorMixin):
    """Filter artifact collections. Only artifact collections matching all criteria will be returned"""

    latest_id: Optional[ArtifactCollectionFilterLatestId] = Field(
        default=None, description="Filter criteria for `Artifact.id`"
    )
    key: Optional[ArtifactCollectionFilterKey] = Field(
        default=None, description="Filter criteria for `Artifact.key`"
    )
    flow_run_id: Optional[ArtifactCollectionFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `Artifact.flow_run_id`"
    )
    task_run_id: Optional[ArtifactCollectionFilterTaskRunId] = Field(
        default=None, description="Filter criteria for `Artifact.task_run_id`"
    )
    type: Optional[ArtifactCollectionFilterType] = Field(
        default=None, description="Filter criteria for `Artifact.type`"
    )
