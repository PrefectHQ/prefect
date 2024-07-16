from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    from .artifact_create import ArtifactCreate
    from .artifact_update import ArtifactUpdate
    from .block_document_create import BlockDocumentCreate
    from .block_document_reference_create import BlockDocumentReferenceCreate
    from .block_document_update import BlockDocumentUpdate
    from .block_schema_create import BlockSchemaCreate
    from .block_type_create import BlockTypeCreate
    from .block_type_update import BlockTypeUpdate
    from .concurrency_limit_create import ConcurrencyLimitCreate
    from .concurrency_limit_v2_create import ConcurrencyLimitV2Create
    from .concurrency_limit_v2_update import ConcurrencyLimitV2Update
    from .deployment_create import DeploymentCreate
    from .deployment_flow_run_create import DeploymentFlowRunCreate
    from .deployment_schedule_create import DeploymentScheduleCreate
    from .deployment_schedule_update import DeploymentScheduleUpdate
    from .deployment_update import DeploymentUpdate
    from .flow_create import FlowCreate
    from .flow_run_create import FlowRunCreate
    from .flow_run_notification_policy_create import FlowRunNotificationPolicyCreate
    from .flow_run_notification_policy_update import FlowRunNotificationPolicyUpdate
    from .flow_run_update import FlowRunUpdate
    from .flow_update import FlowUpdate
    from .global_concurrency_limit_create import GlobalConcurrencyLimitCreate
    from .global_concurrency_limit_update import GlobalConcurrencyLimitUpdate
    from .log_create import LogCreate
    from .saved_search_create import SavedSearchCreate
    from .state_create import StateCreate
    from .task_run_create import TaskRunCreate
    from .task_run_update import TaskRunUpdate
    from .variable_create import VariableCreate
    from .variable_update import VariableUpdate
    from .work_pool_create import WorkPoolCreate
    from .work_pool_update import WorkPoolUpdate
    from .work_queue_create import WorkQueueCreate
    from .work_queue_update import WorkQueueUpdate
    

_public_api: dict[str, tuple[str, str]] = {
    "ArtifactCreate": (__spec__.parent, ".artifact_create"),
    "ArtifactUpdate": (__spec__.parent, ".artifact_update"),
    "BlockDocumentCreate": (__spec__.parent, ".block_document_create"),
    "BlockDocumentReferenceCreate": (__spec__.parent, ".block_document_reference_create"),
    "BlockDocumentUpdate": (__spec__.parent, ".block_document_update"),
    "BlockSchemaCreate": (__spec__.parent, ".block_schema_create"),
    "BlockTypeCreate": (__spec__.parent, ".block_type_create"),
    "BlockTypeUpdate": (__spec__.parent, ".block_type_update"),
    "ConcurrencyLimitCreate": (__spec__.parent, ".concurrency_limit_create"),
    "ConcurrencyLimitV2Create": (__spec__.parent, ".concurrency_limit_v2_create"),
    "ConcurrencyLimitV2Update": (__spec__.parent, ".concurrency_limit_v2_update"),
    "DeploymentCreate": (__spec__.parent, ".deployment_create"),
    "DeploymentFlowRunCreate": (__spec__.parent, ".deployment_flow_run_create"),
    "DeploymentScheduleCreate": (__spec__.parent, ".deployment_schedule_create"),
    "DeploymentScheduleUpdate": (__spec__.parent, ".deployment_schedule_update"),
    "DeploymentUpdate": (__spec__.parent, ".deployment_update"),
    "FlowCreate": (__spec__.parent, ".flow_create"),
    "FlowRunCreate": (__spec__.parent, ".flow_run_create"),
    "FlowRunNotificationPolicyCreate": (__spec__.parent, ".flow_run_notification_policy_create"),
    "FlowRunNotificationPolicyUpdate": (__spec__.parent, ".flow_run_notification_policy_update"),
    "FlowRunUpdate": (__spec__.parent, ".flow_run_update"),
    "FlowUpdate": (__spec__.parent, ".flow_update"),
    "GlobalConcurrencyLimitCreate": (__spec__.parent, ".global_concurrency_limit_create"),
    "GlobalConcurrencyLimitUpdate": (__spec__.parent, ".global_concurrency_limit_update"),
    "LogCreate": (__spec__.parent, ".log_create"),
    "SavedSearchCreate": (__spec__.parent, ".saved_search_create"),
    "StateCreate": (__spec__.parent, ".state_create"),
    "TaskRunCreate": (__spec__.parent, ".task_run_create"),
    "TaskRunUpdate": (__spec__.parent, ".task_run_update"),
    "VariableCreate": (__spec__.parent, ".variable_create"),
    "VariableUpdate": (__spec__.parent, ".variable_update"),
    "WorkPoolCreate": (__spec__.parent, ".work_pool_create"),
    "WorkPoolUpdate": (__spec__.parent, ".work_pool_update"),
    "WorkQueueCreate": (__spec__.parent, ".work_queue_create"),
    "WorkQueueUpdate": (__spec__.parent, ".work_queue_update"),
    
    }

__all__ = [
    "ArtifactCreate",
    "ArtifactUpdate",
    "BlockDocumentCreate",
    "BlockDocumentReferenceCreate",
    "BlockDocumentUpdate",
    "BlockSchemaCreate",
    "BlockTypeCreate",
    "BlockTypeUpdate",
    "ConcurrencyLimitCreate",
    "ConcurrencyLimitV2Create",
    "ConcurrencyLimitV2Update",
    "DeploymentCreate",
    "DeploymentFlowRunCreate",
    "DeploymentScheduleCreate",
    "DeploymentScheduleUpdate",
    "DeploymentUpdate",
    "FlowCreate",
    "FlowRunCreate",
    "FlowRunNotificationPolicyCreate",
    "FlowRunNotificationPolicyUpdate",
    "FlowRunUpdate",
    "FlowUpdate",
    "GlobalConcurrencyLimitCreate",
    "GlobalConcurrencyLimitUpdate",
    "LogCreate",
    "SavedSearchCreate",
    "StateCreate",
    "TaskRunCreate",
    "TaskRunUpdate",
    "VariableCreate",
    "VariableUpdate",
    "WorkPoolCreate",
    "WorkPoolUpdate",
    "WorkQueueCreate",
    "WorkQueueUpdate",
      
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