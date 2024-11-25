"""Creating type adapters to avoid recreation of the pydantic core schemas when possible."""

from typing import TYPE_CHECKING, List

from pydantic import ConfigDict, TypeAdapter

if TYPE_CHECKING:
    from prefect.client.schemas.objects import (
        Artifact,
        ArtifactCollection,
        BlockDocument,
        BlockSchema,
        BlockType,
        ConcurrencyLimit,
        DeploymentSchedule,
        Flow,
        FlowRun,
        FlowRunInput,
        FlowRunNotificationPolicy,
        GlobalConcurrencyLimit,
        Log,
        State,
        TaskRun,
        Variable,
        Worker,
        WorkPool,
        WorkQueue,
    )
    from prefect.client.schemas.responses import (
        DeploymentResponse,
        FlowRunResponse,
        GlobalConcurrencyLimitResponse,
        WorkerFlowRunResponse,
    )
    from prefect.events.schemas.automations import Automation


defer_build_cfg = ConfigDict(defer_build=True)

BlockTypeAdapter = TypeAdapter("BlockType", config=defer_build_cfg)
BlockSchemaAdapter = TypeAdapter(List["BlockSchema"], config=defer_build_cfg)
ConcurrencyLimitAdapter = TypeAdapter("ConcurrencyLimit", config=defer_build_cfg)
ConcurrencyLimitListAdapter = TypeAdapter(
    List["ConcurrencyLimit"], config=defer_build_cfg
)
FlowAdapter = TypeAdapter("Flow", config=defer_build_cfg)
FlowRunAdapter = TypeAdapter("FlowRun", config=defer_build_cfg)
ArtifactListAdapter = TypeAdapter(List["Artifact"], config=defer_build_cfg)
ArtifactCollectionListAdapter = TypeAdapter(
    List["ArtifactCollection"], config=defer_build_cfg
)
AutomationListAdapter = TypeAdapter(List["Automation"], config=defer_build_cfg)
BlockDocumentListAdapter = TypeAdapter(List["BlockDocument"], config=defer_build_cfg)
BlockSchemaListAdapter = TypeAdapter(List["BlockSchema"], config=defer_build_cfg)
BlockTypeListAdapter = TypeAdapter(List["BlockType"], config=defer_build_cfg)
ConcurrencyLimitListAdapter = TypeAdapter(
    List["ConcurrencyLimit"], config=defer_build_cfg
)
DeploymentResponseListAdapter = TypeAdapter(
    List["DeploymentResponse"], config=defer_build_cfg
)
DeploymentScheduleListAdapter = TypeAdapter(
    List["DeploymentSchedule"], config=defer_build_cfg
)
FlowListAdapter = TypeAdapter(List["Flow"], config=defer_build_cfg)
FlowRunListAdapter = TypeAdapter(List["FlowRun"], config=defer_build_cfg)
FlowRunInputListAdapter = TypeAdapter(List["FlowRunInput"], config=defer_build_cfg)
FlowRunNotificationPolicyListAdapter = TypeAdapter(
    List["FlowRunNotificationPolicy"], config=defer_build_cfg
)
FlowRunResponseListAdapter = TypeAdapter(
    List["FlowRunResponse"], config=defer_build_cfg
)
GlobalConcurrencyLimitListAdapter = TypeAdapter(
    List["GlobalConcurrencyLimit"], config=defer_build_cfg
)
GlobalConcurrencyLimitResponseListAdapter = TypeAdapter(
    List["GlobalConcurrencyLimitResponse"], config=defer_build_cfg
)
LogListAdapter = TypeAdapter(List["Log"], config=defer_build_cfg)
StateListAdapter = TypeAdapter(List["State"], config=defer_build_cfg)
TaskRunListAdapter = TypeAdapter(List["TaskRun"], config=defer_build_cfg)
WorkerListAdapter = TypeAdapter(List["Worker"], config=defer_build_cfg)
WorkPoolListAdapter = TypeAdapter(List["WorkPool"], config=defer_build_cfg)
WorkQueueListAdapter = TypeAdapter(List["WorkQueue"], config=defer_build_cfg)
WorkerFlowRunResponseListAdapter = TypeAdapter(
    List["WorkerFlowRunResponse"], config=defer_build_cfg
)
VariableListAdapter = TypeAdapter(List["Variable"], config=defer_build_cfg)
StateAdapter = TypeAdapter("State", config=defer_build_cfg)
