from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    from .artifact_collection_filter import ArtifactCollectionFilter
    from .artifact_collection_filter_flow_run_id import (
        ArtifactCollectionFilterFlowRunId,
    )
    from .artifact_collection_filter_key import ArtifactCollectionFilterKey
    from .artifact_collection_filter_latest_id import ArtifactCollectionFilterLatestId
    from .artifact_collection_filter_task_run_id import (
        ArtifactCollectionFilterTaskRunId,
    )
    from .artifact_collection_filter_type import ArtifactCollectionFilterType
    from .artifact_filter import ArtifactFilter
    from .artifact_filter_flow_run_id import ArtifactFilterFlowRunId
    from .artifact_filter_id import ArtifactFilterId
    from .artifact_filter_key import ArtifactFilterKey
    from .artifact_filter_task_run_id import ArtifactFilterTaskRunId
    from .artifact_filter_type import ArtifactFilterType
    from .block_document_filter import BlockDocumentFilter
    from .block_document_filter_block_type_id import BlockDocumentFilterBlockTypeId
    from .block_document_filter_id import BlockDocumentFilterId
    from .block_document_filter_is_anonymous import BlockDocumentFilterIsAnonymous
    from .block_document_filter_name import BlockDocumentFilterName
    from .block_schema_filter import BlockSchemaFilter
    from .block_schema_filter_block_type_id import BlockSchemaFilterBlockTypeId
    from .block_schema_filter_capabilities import BlockSchemaFilterCapabilities
    from .block_schema_filter_id import BlockSchemaFilterId
    from .block_schema_filter_version import BlockSchemaFilterVersion
    from .block_type_filter import BlockTypeFilter
    from .block_type_filter_name import BlockTypeFilterName
    from .block_type_filter_slug import BlockTypeFilterSlug
    from .deployment_filter import DeploymentFilter
    from .deployment_filter_id import DeploymentFilterId
    from .deployment_filter_is_schedule_active import DeploymentFilterIsScheduleActive
    from .deployment_filter_name import DeploymentFilterName
    from .deployment_filter_tags import DeploymentFilterTags
    from .deployment_filter_work_queue_name import DeploymentFilterWorkQueueName
    from .filter_set import FilterSet
    from .flow_filter import FlowFilter
    from .flow_filter_id import FlowFilterId
    from .flow_filter_name import FlowFilterName
    from .flow_filter_tags import FlowFilterTags
    from .flow_run_filter import FlowRunFilter
    from .flow_run_filter_deployment_id import FlowRunFilterDeploymentId
    from .flow_run_filter_expected_start_time import FlowRunFilterExpectedStartTime
    from .flow_run_filter_flow_version import FlowRunFilterFlowVersion
    from .flow_run_filter_id import FlowRunFilterId
    from .flow_run_filter_idempotency_key import FlowRunFilterIdempotencyKey
    from .flow_run_filter_name import FlowRunFilterName
    from .flow_run_filter_next_scheduled_start_time import (
        FlowRunFilterNextScheduledStartTime,
    )
    from .flow_run_filter_parent_flow_run_id import FlowRunFilterParentFlowRunId
    from .flow_run_filter_parent_task_run_id import FlowRunFilterParentTaskRunId
    from .flow_run_filter_start_time import FlowRunFilterStartTime
    from .flow_run_filter_state import FlowRunFilterState
    from .flow_run_filter_state_name import FlowRunFilterStateName
    from .flow_run_filter_state_type import FlowRunFilterStateType
    from .flow_run_filter_tags import FlowRunFilterTags
    from .flow_run_filter_work_queue_name import FlowRunFilterWorkQueueName
    from .flow_run_notification_policy_filter import FlowRunNotificationPolicyFilter
    from .flow_run_notification_policy_filter_is_active import (
        FlowRunNotificationPolicyFilterIsActive,
    )
    from .log_filter import LogFilter
    from .log_filter_flow_run_id import LogFilterFlowRunId
    from .log_filter_level import LogFilterLevel
    from .log_filter_name import LogFilterName
    from .log_filter_task_run_id import LogFilterTaskRunId
    from .log_filter_timestamp import LogFilterTimestamp
    from .operator import Operator
    from .operator_mixin import OperatorMixin
    from .task_run_filter import TaskRunFilter
    from .task_run_filter_flow_run_id import TaskRunFilterFlowRunId
    from .task_run_filter_id import TaskRunFilterId
    from .task_run_filter_name import TaskRunFilterName
    from .task_run_filter_start_time import TaskRunFilterStartTime
    from .task_run_filter_state import TaskRunFilterState
    from .task_run_filter_state_name import TaskRunFilterStateName
    from .task_run_filter_state_type import TaskRunFilterStateType
    from .task_run_filter_sub_flow_runs import TaskRunFilterSubFlowRuns
    from .task_run_filter_tags import TaskRunFilterTags
    from .variable_filter import VariableFilter
    from .variable_filter_id import VariableFilterId
    from .variable_filter_name import VariableFilterName
    from .variable_filter_tags import VariableFilterTags
    from .work_pool_filter import WorkPoolFilter
    from .work_pool_filter_id import WorkPoolFilterId
    from .work_pool_filter_name import WorkPoolFilterName
    from .work_pool_filter_type import WorkPoolFilterType
    from .work_queue_filter import WorkQueueFilter
    from .work_queue_filter_id import WorkQueueFilterId
    from .work_queue_filter_name import WorkQueueFilterName
    from .worker_filter import WorkerFilter
    from .worker_filter_last_heartbeat_time import WorkerFilterLastHeartbeatTime
    from .worker_filter_work_pool_id import WorkerFilterWorkPoolId


_public_api: dict[str, tuple[str, str]] = {
    "ArtifactCollectionFilter": (__spec__.parent, ".artifact_collection_filter"),
    "ArtifactCollectionFilterFlowRunId": (
        __spec__.parent,
        ".artifact_collection_filter_flow_run_id",
    ),
    "ArtifactCollectionFilterKey": (__spec__.parent, ".artifact_collection_filter_key"),
    "ArtifactCollectionFilterLatestId": (
        __spec__.parent,
        ".artifact_collection_filter_latest_id",
    ),
    "ArtifactCollectionFilterTaskRunId": (
        __spec__.parent,
        ".artifact_collection_filter_task_run_id",
    ),
    "ArtifactCollectionFilterType": (
        __spec__.parent,
        ".artifact_collection_filter_type",
    ),
    "ArtifactFilter": (__spec__.parent, ".artifact_filter"),
    "ArtifactFilterFlowRunId": (__spec__.parent, ".artifact_filter_flow_run_id"),
    "ArtifactFilterId": (__spec__.parent, ".artifact_filter_id"),
    "ArtifactFilterKey": (__spec__.parent, ".artifact_filter_key"),
    "ArtifactFilterTaskRunId": (__spec__.parent, ".artifact_filter_task_run_id"),
    "ArtifactFilterType": (__spec__.parent, ".artifact_filter_type"),
    "BlockDocumentFilter": (__spec__.parent, ".block_document_filter"),
    "BlockDocumentFilterBlockTypeId": (
        __spec__.parent,
        ".block_document_filter_block_type_id",
    ),
    "BlockDocumentFilterId": (__spec__.parent, ".block_document_filter_id"),
    "BlockDocumentFilterIsAnonymous": (
        __spec__.parent,
        ".block_document_filter_is_anonymous",
    ),
    "BlockDocumentFilterName": (__spec__.parent, ".block_document_filter_name"),
    "BlockSchemaFilter": (__spec__.parent, ".block_schema_filter"),
    "BlockSchemaFilterBlockTypeId": (
        __spec__.parent,
        ".block_schema_filter_block_type_id",
    ),
    "BlockSchemaFilterCapabilities": (
        __spec__.parent,
        ".block_schema_filter_capabilities",
    ),
    "BlockSchemaFilterId": (__spec__.parent, ".block_schema_filter_id"),
    "BlockSchemaFilterVersion": (__spec__.parent, ".block_schema_filter_version"),
    "BlockTypeFilter": (__spec__.parent, ".block_type_filter"),
    "BlockTypeFilterName": (__spec__.parent, ".block_type_filter_name"),
    "BlockTypeFilterSlug": (__spec__.parent, ".block_type_filter_slug"),
    "DeploymentFilter": (__spec__.parent, ".deployment_filter"),
    "DeploymentFilterId": (__spec__.parent, ".deployment_filter_id"),
    "DeploymentFilterIsScheduleActive": (
        __spec__.parent,
        ".deployment_filter_is_schedule_active",
    ),
    "DeploymentFilterName": (__spec__.parent, ".deployment_filter_name"),
    "DeploymentFilterTags": (__spec__.parent, ".deployment_filter_tags"),
    "DeploymentFilterWorkQueueName": (
        __spec__.parent,
        ".deployment_filter_work_queue_name",
    ),
    "FilterSet": (__spec__.parent, ".filter_set"),
    "FlowFilter": (__spec__.parent, ".flow_filter"),
    "FlowFilterId": (__spec__.parent, ".flow_filter_id"),
    "FlowFilterName": (__spec__.parent, ".flow_filter_name"),
    "FlowFilterTags": (__spec__.parent, ".flow_filter_tags"),
    "FlowRunFilter": (__spec__.parent, ".flow_run_filter"),
    "FlowRunFilterDeploymentId": (__spec__.parent, ".flow_run_filter_deployment_id"),
    "FlowRunFilterExpectedStartTime": (
        __spec__.parent,
        ".flow_run_filter_expected_start_time",
    ),
    "FlowRunFilterFlowVersion": (__spec__.parent, ".flow_run_filter_flow_version"),
    "FlowRunFilterId": (__spec__.parent, ".flow_run_filter_id"),
    "FlowRunFilterIdempotencyKey": (
        __spec__.parent,
        ".flow_run_filter_idempotency_key",
    ),
    "FlowRunFilterName": (__spec__.parent, ".flow_run_filter_name"),
    "FlowRunFilterNextScheduledStartTime": (
        __spec__.parent,
        ".flow_run_filter_next_scheduled_start_time",
    ),
    "FlowRunFilterParentFlowRunId": (
        __spec__.parent,
        ".flow_run_filter_parent_flow_run_id",
    ),
    "FlowRunFilterParentTaskRunId": (
        __spec__.parent,
        ".flow_run_filter_parent_task_run_id",
    ),
    "FlowRunFilterStartTime": (__spec__.parent, ".flow_run_filter_start_time"),
    "FlowRunFilterState": (__spec__.parent, ".flow_run_filter_state"),
    "FlowRunFilterStateName": (__spec__.parent, ".flow_run_filter_state_name"),
    "FlowRunFilterStateType": (__spec__.parent, ".flow_run_filter_state_type"),
    "FlowRunFilterTags": (__spec__.parent, ".flow_run_filter_tags"),
    "FlowRunFilterWorkQueueName": (__spec__.parent, ".flow_run_filter_work_queue_name"),
    "FlowRunNotificationPolicyFilter": (
        __spec__.parent,
        ".flow_run_notification_policy_filter",
    ),
    "FlowRunNotificationPolicyFilterIsActive": (
        __spec__.parent,
        ".flow_run_notification_policy_filter_is_active",
    ),
    "LogFilter": (__spec__.parent, ".log_filter"),
    "LogFilterFlowRunId": (__spec__.parent, ".log_filter_flow_run_id"),
    "LogFilterLevel": (__spec__.parent, ".log_filter_level"),
    "LogFilterName": (__spec__.parent, ".log_filter_name"),
    "LogFilterTaskRunId": (__spec__.parent, ".log_filter_task_run_id"),
    "LogFilterTimestamp": (__spec__.parent, ".log_filter_timestamp"),
    "Operator": (__spec__.parent, ".operator"),
    "OperatorMixin": (__spec__.parent, ".operator_mixin"),
    "TaskRunFilter": (__spec__.parent, ".task_run_filter"),
    "TaskRunFilterFlowRunId": (__spec__.parent, ".task_run_filter_flow_run_id"),
    "TaskRunFilterId": (__spec__.parent, ".task_run_filter_id"),
    "TaskRunFilterName": (__spec__.parent, ".task_run_filter_name"),
    "TaskRunFilterStartTime": (__spec__.parent, ".task_run_filter_start_time"),
    "TaskRunFilterState": (__spec__.parent, ".task_run_filter_state"),
    "TaskRunFilterStateName": (__spec__.parent, ".task_run_filter_state_name"),
    "TaskRunFilterStateType": (__spec__.parent, ".task_run_filter_state_type"),
    "TaskRunFilterSubFlowRuns": (__spec__.parent, ".task_run_filter_sub_flow_runs"),
    "TaskRunFilterTags": (__spec__.parent, ".task_run_filter_tags"),
    "VariableFilter": (__spec__.parent, ".variable_filter"),
    "VariableFilterId": (__spec__.parent, ".variable_filter_id"),
    "VariableFilterName": (__spec__.parent, ".variable_filter_name"),
    "VariableFilterTags": (__spec__.parent, ".variable_filter_tags"),
    "WorkPoolFilter": (__spec__.parent, ".work_pool_filter"),
    "WorkPoolFilterId": (__spec__.parent, ".work_pool_filter_id"),
    "WorkPoolFilterName": (__spec__.parent, ".work_pool_filter_name"),
    "WorkPoolFilterType": (__spec__.parent, ".work_pool_filter_type"),
    "WorkQueueFilter": (__spec__.parent, ".work_queue_filter"),
    "WorkQueueFilterId": (__spec__.parent, ".work_queue_filter_id"),
    "WorkQueueFilterName": (__spec__.parent, ".work_queue_filter_name"),
    "WorkerFilter": (__spec__.parent, ".worker_filter"),
    "WorkerFilterLastHeartbeatTime": (
        __spec__.parent,
        ".worker_filter_last_heartbeat_time",
    ),
    "WorkerFilterWorkPoolId": (__spec__.parent, ".worker_filter_work_pool_id"),
}

__all__ = [
    "ArtifactCollectionFilter",
    "ArtifactCollectionFilterFlowRunId",
    "ArtifactCollectionFilterKey",
    "ArtifactCollectionFilterLatestId",
    "ArtifactCollectionFilterTaskRunId",
    "ArtifactCollectionFilterType",
    "ArtifactFilter",
    "ArtifactFilterFlowRunId",
    "ArtifactFilterId",
    "ArtifactFilterKey",
    "ArtifactFilterTaskRunId",
    "ArtifactFilterType",
    "BlockDocumentFilter",
    "BlockDocumentFilterBlockTypeId",
    "BlockDocumentFilterId",
    "BlockDocumentFilterIsAnonymous",
    "BlockDocumentFilterName",
    "BlockSchemaFilter",
    "BlockSchemaFilterBlockTypeId",
    "BlockSchemaFilterCapabilities",
    "BlockSchemaFilterId",
    "BlockSchemaFilterVersion",
    "BlockTypeFilter",
    "BlockTypeFilterName",
    "BlockTypeFilterSlug",
    "DeploymentFilter",
    "DeploymentFilterId",
    "DeploymentFilterIsScheduleActive",
    "DeploymentFilterName",
    "DeploymentFilterTags",
    "DeploymentFilterWorkQueueName",
    "FilterSet",
    "FlowFilter",
    "FlowFilterId",
    "FlowFilterName",
    "FlowFilterTags",
    "FlowRunFilter",
    "FlowRunFilterDeploymentId",
    "FlowRunFilterExpectedStartTime",
    "FlowRunFilterFlowVersion",
    "FlowRunFilterId",
    "FlowRunFilterIdempotencyKey",
    "FlowRunFilterName",
    "FlowRunFilterNextScheduledStartTime",
    "FlowRunFilterParentFlowRunId",
    "FlowRunFilterParentTaskRunId",
    "FlowRunFilterStartTime",
    "FlowRunFilterState",
    "FlowRunFilterStateName",
    "FlowRunFilterStateType",
    "FlowRunFilterTags",
    "FlowRunFilterWorkQueueName",
    "FlowRunNotificationPolicyFilter",
    "FlowRunNotificationPolicyFilterIsActive",
    "LogFilter",
    "LogFilterFlowRunId",
    "LogFilterLevel",
    "LogFilterName",
    "LogFilterTaskRunId",
    "LogFilterTimestamp",
    "Operator",
    "OperatorMixin",
    "TaskRunFilter",
    "TaskRunFilterFlowRunId",
    "TaskRunFilterId",
    "TaskRunFilterName",
    "TaskRunFilterStartTime",
    "TaskRunFilterState",
    "TaskRunFilterStateName",
    "TaskRunFilterStateType",
    "TaskRunFilterSubFlowRuns",
    "TaskRunFilterTags",
    "VariableFilter",
    "VariableFilterId",
    "VariableFilterName",
    "VariableFilterTags",
    "WorkPoolFilter",
    "WorkPoolFilterId",
    "WorkPoolFilterName",
    "WorkPoolFilterType",
    "WorkQueueFilter",
    "WorkQueueFilterId",
    "WorkQueueFilterName",
    "WorkerFilter",
    "WorkerFilterLastHeartbeatTime",
    "WorkerFilterWorkPoolId",
]


def __getattr__(attr_name: str) -> object:
    dynamic_attr = _public_api.get(attr_name)
    if dynamic_attr is None:
        return importlib.import_module(f".{attr_name}", package=__name__)

    package, module_name = dynamic_attr

    from importlib import import_module

    if module_name == "__module__":
        return import_module(f".{attr_name}", package=package)
    else:
        module = import_module(module_name, package=package)
        return getattr(module, attr_name)
