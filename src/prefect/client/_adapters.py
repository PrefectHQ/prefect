"""Creating type adapters to avoid recreation of the pydantic core schemas when possible."""

from typing import TYPE_CHECKING

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

# Create the adapters with forward refs
BlockTypeAdapter: TypeAdapter["BlockType"] = TypeAdapter(
    "BlockType", config=defer_build_cfg
)
BlockSchemaAdapter: TypeAdapter[list["BlockSchema"]] = TypeAdapter(
    list["BlockSchema"], config=defer_build_cfg
)
ConcurrencyLimitAdapter: TypeAdapter["ConcurrencyLimit"] = TypeAdapter(
    "ConcurrencyLimit", config=defer_build_cfg
)
ConcurrencyLimitListAdapter: TypeAdapter[list["ConcurrencyLimit"]] = TypeAdapter(
    list["ConcurrencyLimit"], config=defer_build_cfg
)
FlowAdapter: TypeAdapter["Flow"] = TypeAdapter("Flow", config=defer_build_cfg)
FlowRunAdapter: TypeAdapter["FlowRun"] = TypeAdapter("FlowRun", config=defer_build_cfg)
ArtifactListAdapter: TypeAdapter[list["Artifact"]] = TypeAdapter(
    list["Artifact"], config=defer_build_cfg
)
ArtifactCollectionListAdapter: TypeAdapter[list["ArtifactCollection"]] = TypeAdapter(
    list["ArtifactCollection"], config=defer_build_cfg
)
AutomationListAdapter: TypeAdapter[list["Automation"]] = TypeAdapter(
    list["Automation"], config=defer_build_cfg
)
BlockDocumentListAdapter: TypeAdapter[list["BlockDocument"]] = TypeAdapter(
    list["BlockDocument"], config=defer_build_cfg
)
BlockSchemaListAdapter: TypeAdapter[list["BlockSchema"]] = TypeAdapter(
    list["BlockSchema"], config=defer_build_cfg
)
BlockTypeListAdapter: TypeAdapter[list["BlockType"]] = TypeAdapter(
    list["BlockType"], config=defer_build_cfg
)
DeploymentResponseListAdapter: TypeAdapter[list["DeploymentResponse"]] = TypeAdapter(
    list["DeploymentResponse"], config=defer_build_cfg
)
DeploymentScheduleListAdapter: TypeAdapter[list["DeploymentSchedule"]] = TypeAdapter(
    list["DeploymentSchedule"], config=defer_build_cfg
)
FlowListAdapter: TypeAdapter[list["Flow"]] = TypeAdapter(
    list["Flow"], config=defer_build_cfg
)
FlowRunListAdapter: TypeAdapter[list["FlowRun"]] = TypeAdapter(
    list["FlowRun"], config=defer_build_cfg
)
FlowRunInputListAdapter: TypeAdapter[list["FlowRunInput"]] = TypeAdapter(
    list["FlowRunInput"], config=defer_build_cfg
)
FlowRunNotificationPolicyListAdapter: TypeAdapter[
    list["FlowRunNotificationPolicy"]
] = TypeAdapter(list["FlowRunNotificationPolicy"], config=defer_build_cfg)
FlowRunResponseListAdapter: TypeAdapter[list["FlowRunResponse"]] = TypeAdapter(
    list["FlowRunResponse"], config=defer_build_cfg
)
GlobalConcurrencyLimitListAdapter = TypeAdapter(
    list["GlobalConcurrencyLimit"], config=defer_build_cfg
)
GlobalConcurrencyLimitResponseListAdapter: TypeAdapter[
    list["GlobalConcurrencyLimitResponse"]
] = TypeAdapter(list["GlobalConcurrencyLimitResponse"], config=defer_build_cfg)
LogListAdapter: TypeAdapter[list["Log"]] = TypeAdapter(
    list["Log"], config=defer_build_cfg
)
StateListAdapter: TypeAdapter[list["State"]] = TypeAdapter(
    list["State"], config=defer_build_cfg
)
TaskRunListAdapter: TypeAdapter[list["TaskRun"]] = TypeAdapter(
    list["TaskRun"], config=defer_build_cfg
)
WorkerListAdapter: TypeAdapter[list["Worker"]] = TypeAdapter(
    list["Worker"], config=defer_build_cfg
)
WorkPoolListAdapter: TypeAdapter[list["WorkPool"]] = TypeAdapter(
    list["WorkPool"], config=defer_build_cfg
)
WorkQueueListAdapter: TypeAdapter[list["WorkQueue"]] = TypeAdapter(
    list["WorkQueue"], config=defer_build_cfg
)
WorkerFlowRunResponseListAdapter: TypeAdapter[
    list["WorkerFlowRunResponse"]
] = TypeAdapter(list["WorkerFlowRunResponse"], config=defer_build_cfg)
VariableListAdapter: TypeAdapter[list["Variable"]] = TypeAdapter(
    list["Variable"], config=defer_build_cfg
)
StateAdapter: TypeAdapter["State"] = TypeAdapter("State", config=defer_build_cfg)
