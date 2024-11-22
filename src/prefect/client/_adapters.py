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

block_type_adapter = TypeAdapter(BlockType)
block_schema_adapter = TypeAdapter(List[BlockSchema])
concurrency_limit_adapter = TypeAdapter(List[ConcurrencyLimit])
flow_adapter = TypeAdapter(Flow)
flow_run_adapter = TypeAdapter(FlowRun)
list_of_artifacts_adapter = TypeAdapter(List[Artifact])
list_of_artifact_collections_adapter = TypeAdapter(List[ArtifactCollection])
list_of_automations_adapter = TypeAdapter(List[Automation])
list_of_block_documents_adapter = TypeAdapter(List[BlockDocument])
list_of_block_types_adapter = TypeAdapter(List[BlockType])
list_of_concurrency_limits_adapter = TypeAdapter(List[ConcurrencyLimit])
list_of_deployment_responses_adapter = TypeAdapter(List[DeploymentResponse])
list_of_deployment_schedules_adapter = TypeAdapter(List[DeploymentSchedule])
list_of_flows_adapter = TypeAdapter(List[Flow])
list_of_flow_runs_adapter = TypeAdapter(List[FlowRun])
list_of_flow_run_inputs_adapter = TypeAdapter(List[FlowRunInput])
list_of_flow_run_notification_policies_adapter = TypeAdapter(
    List[FlowRunNotificationPolicy]
)
list_of_flow_run_responses_adapter = TypeAdapter(List[FlowRunResponse])
list_of_global_concurrency_limits_adapter = TypeAdapter(List[GlobalConcurrencyLimit])
list_of_global_concurrency_limits_response_adapter = TypeAdapter(
    List[GlobalConcurrencyLimitResponse]
)
list_of_logs_adapter = TypeAdapter(List[Log])
list_of_states_adapter = TypeAdapter(List[State])
list_of_task_runs_adapter = TypeAdapter(List[TaskRun])
list_of_workers_adapter = TypeAdapter(List[Worker])
list_of_work_pools_adapter = TypeAdapter(List[WorkPool])
list_of_work_queues_adapter = TypeAdapter(List[WorkQueue])
list_of_worker_flow_run_responses_adapter = TypeAdapter(List[WorkerFlowRunResponse])
list_of_variables_adapter = TypeAdapter(List[Variable])
state_adapter = TypeAdapter(State)
