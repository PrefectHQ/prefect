from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    from .agent import Agent
    from .artifact import Artifact
    from .artifact_collection import ArtifactCollection
    from .block_document import BlockDocument
    from .block_document_reference import BlockDocumentReference
    from .block_schema import (
        BlockSchema,
        DEFAULT_BLOCK_SCHEMA_VERSION,
        DEFAULT_AGENT_WORK_POOL_NAME,
    )
    from .block_schema_reference import BlockSchemaReference
    from .block_type import BlockType
    from .concurrency_limit import ConcurrencyLimit
    from .configuration import Configuration
    from .constant import Constant
    from .csrf_token import CsrfToken
    from .deployment import Deployment
    from .deployment_schedule import DeploymentSchedule
    from .deployment_status import DeploymentStatus
    from .flow import Flow
    from .flow_run import FlowRun
    from .flow_run_input import FlowRunInput
    from .flow_run_notification_policy import FlowRunNotificationPolicy
    from .flow_run_policy import FlowRunPolicy
    from .global_concurrency_limit import GlobalConcurrencyLimit
    from .log import Log
    from .parameter import Parameter
    from .queue_filter import QueueFilter
    from .saved_search import SavedSearch
    from .saved_search_filter import SavedSearchFilter
    from .state import State, TERMINAL_STATES
    from .state_details import StateDetails
    from .state_type import StateType
    from .task_run import TaskRun
    from .task_run_input import TaskRunInput
    from .task_run_policy import TaskRunPolicy
    from .task_run_result import TaskRunResult
    from .variable import Variable
    from .work_pool import WorkPool
    from .work_pool_status import WorkPoolStatus
    from .work_queue import WorkQueue
    from .work_queue_health_policy import WorkQueueHealthPolicy
    from .work_queue_status import WorkQueueStatus
    from .work_queue_status_detail import WorkQueueStatusDetail
    from .worker import Worker
    from .worker_status import WorkerStatus
    from .workspace import Workspace


_public_api: dict[str, tuple[str, str]] = {
    "Agent": (__spec__.parent, ".agent"),
    "Artifact": (__spec__.parent, ".artifact"),
    "ArtifactCollection": (__spec__.parent, ".artifact_collection"),
    "BlockDocument": (__spec__.parent, ".block_document"),
    "BlockDocumentReference": (__spec__.parent, ".block_document_reference"),
    "BlockSchema": (__spec__.parent, ".block_schema"),
    "BlockSchemaReference": (__spec__.parent, ".block_schema_reference"),
    "BlockType": (__spec__.parent, ".block_type"),
    "ConcurrencyLimit": (__spec__.parent, ".concurrency_limit"),
    "Configuration": (__spec__.parent, ".configuration"),
    "Constant": (__spec__.parent, ".constant"),
    "CsrfToken": (__spec__.parent, ".csrf_token"),
    "Deployment": (__spec__.parent, ".deployment"),
    "DEFAULT_BLOCK_SCHEMA_VERSION": (__spec__.parent, ".block_schema"),
    "DEFAULT_AGENT_WORK_POOL_NAME": (__spec__.parent, ".block_schema"),
    "DeploymentSchedule": (__spec__.parent, ".deployment_schedule"),
    "DeploymentStatus": (__spec__.parent, ".deployment_status"),
    "Flow": (__spec__.parent, ".flow"),
    "FlowRun": (__spec__.parent, ".flow_run"),
    "FlowRunInput": (__spec__.parent, ".flow_run_input"),
    "FlowRunNotificationPolicy": (__spec__.parent, ".flow_run_notification_policy"),
    "FlowRunPolicy": (__spec__.parent, ".flow_run_policy"),
    "GlobalConcurrencyLimit": (__spec__.parent, ".global_concurrency_limit"),
    "Log": (__spec__.parent, ".log"),
    "Parameter": (__spec__.parent, ".parameter"),
    "QueueFilter": (__spec__.parent, ".queue_filter"),
    "SavedSearch": (__spec__.parent, ".saved_search"),
    "SavedSearchFilter": (__spec__.parent, ".saved_search_filter"),
    "State": (__spec__.parent, ".state"),
    "StateDetails": (__spec__.parent, ".state_details"),
    "StateType": (__spec__.parent, ".state_type"),
    "TaskRun": (__spec__.parent, ".task_run"),
    "TaskRunInput": (__spec__.parent, ".task_run_input"),
    "TaskRunPolicy": (__spec__.parent, ".task_run_policy"),
    "TaskRunResult": (__spec__.parent, ".task_run_result"),
    "TERMINAL_STATES": (__spec__.parent, ".state"),
    "Variable": (__spec__.parent, ".variable"),
    "WorkPool": (__spec__.parent, ".work_pool"),
    "WorkPoolStatus": (__spec__.parent, ".work_pool_status"),
    "WorkQueue": (__spec__.parent, ".work_queue"),
    "WorkQueueHealthPolicy": (__spec__.parent, ".work_queue_health_policy"),
    "WorkQueueStatus": (__spec__.parent, ".work_queue_status"),
    "WorkQueueStatusDetail": (__spec__.parent, ".work_queue_status_detail"),
    "Worker": (__spec__.parent, ".worker"),
    "WorkerStatus": (__spec__.parent, ".worker_status"),
    "Workspace": (__spec__.parent, ".workspace"),
}

__all__ = [
    "Agent",
    "Artifact",
    "ArtifactCollection",
    "BlockDocument",
    "BlockDocumentReference",
    "BlockSchema",
    "BlockSchemaReference",
    "BlockType",
    "ConcurrencyLimit",
    "Configuration",
    "Constant",
    "CsrfToken",
    "DEFAULT_BLOCK_SCHEMA_VERSION",
    "DEFAULT_AGENT_WORK_POOL_NAME",
    "Deployment",
    "DeploymentSchedule",
    "DeploymentStatus",
    "Flow",
    "FlowRun",
    "FlowRunInput",
    "FlowRunNotificationPolicy",
    "FlowRunPolicy",
    "GlobalConcurrencyLimit",
    "Log",
    "Parameter",
    "QueueFilter",
    "SavedSearch",
    "SavedSearchFilter",
    "State",
    "StateDetails",
    "StateType",
    "TaskRun",
    "TaskRunInput",
    "TaskRunPolicy",
    "TaskRunResult",
    "TERMINAL_STATES",
    "Variable",
    "WorkPool",
    "WorkPoolStatus",
    "WorkQueue",
    "WorkQueueHealthPolicy",
    "WorkQueueStatus",
    "WorkQueueStatusDetail",
    "Worker",
    "WorkerStatus",
    "Workspace",
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
