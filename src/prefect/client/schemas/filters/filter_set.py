from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .deployment_filter import DeploymentFilter
from .flow_filter import FlowFilter
from .flow_run_filter import FlowRunFilter
from .task_run_filter import TaskRunFilter


class FilterSet(PrefectBaseModel):
    """A collection of filters for common objects"""

    flows: FlowFilter = Field(
        default_factory=FlowFilter, description="Filters that apply to flows"
    )
    flow_runs: FlowRunFilter = Field(
        default_factory=FlowRunFilter, description="Filters that apply to flow runs"
    )
    task_runs: TaskRunFilter = Field(
        default_factory=TaskRunFilter, description="Filters that apply to task runs"
    )
    deployments: DeploymentFilter = Field(
        default_factory=DeploymentFilter,
        description="Filters that apply to deployments",
    )