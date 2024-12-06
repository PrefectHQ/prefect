"""Creating type adapters to avoid recreation of the pydantic core schemas when possible."""

from typing import List

from pydantic import TypeAdapter

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

BlockTypeAdapter = TypeAdapter(BlockType)
BlockSchemaAdapter = TypeAdapter(List[BlockSchema])
ConcurrencyLimitAdapter = TypeAdapter(ConcurrencyLimit)
ConcurrencyLimitListAdapter = TypeAdapter(List[ConcurrencyLimit])
FlowAdapter = TypeAdapter(Flow)
FlowRunAdapter = TypeAdapter(FlowRun)
ArtifactListAdapter = TypeAdapter(List[Artifact])
ArtifactCollectionListAdapter = TypeAdapter(List[ArtifactCollection])
AutomationListAdapter = TypeAdapter(List[Automation])
BlockDocumentListAdapter = TypeAdapter(List[BlockDocument])
BlockSchemaListAdapter = TypeAdapter(List[BlockSchema])
BlockTypeListAdapter = TypeAdapter(List[BlockType])
ConcurrencyLimitListAdapter = TypeAdapter(List[ConcurrencyLimit])
DeploymentResponseListAdapter = TypeAdapter(List[DeploymentResponse])
DeploymentScheduleListAdapter = TypeAdapter(List[DeploymentSchedule])
FlowListAdapter = TypeAdapter(List[Flow])
FlowRunListAdapter = TypeAdapter(List[FlowRun])
FlowRunInputListAdapter = TypeAdapter(List[FlowRunInput])
FlowRunNotificationPolicyListAdapter = TypeAdapter(List[FlowRunNotificationPolicy])
FlowRunResponseListAdapter = TypeAdapter(List[FlowRunResponse])
GlobalConcurrencyLimitListAdapter = TypeAdapter(List[GlobalConcurrencyLimit])
GlobalConcurrencyLimitResponseListAdapter = TypeAdapter(
    List[GlobalConcurrencyLimitResponse]
)
LogListAdapter = TypeAdapter(List[Log])
StateListAdapter = TypeAdapter(List[State])
TaskRunListAdapter = TypeAdapter(List[TaskRun])
WorkerListAdapter = TypeAdapter(List[Worker])
WorkPoolListAdapter = TypeAdapter(List[WorkPool])
WorkQueueListAdapter = TypeAdapter(List[WorkQueue])
WorkerFlowRunResponseListAdapter = TypeAdapter(List[WorkerFlowRunResponse])
VariableListAdapter = TypeAdapter(List[Variable])
StateAdapter = TypeAdapter(State)
