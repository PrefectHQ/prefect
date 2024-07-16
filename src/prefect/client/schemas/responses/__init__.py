from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    from .deployment_response import DeploymentResponse
    from .flow_run_response import FlowRunResponse
    from .global_concurrency_limit_response import GlobalConcurrencyLimitResponse
    from .history_response import HistoryResponse
    from .history_response_state import HistoryResponseState
    from .minimal_concurrency_limit_response import MinimalConcurrencyLimitResponse
    from .orchestration_result import OrchestrationResult
    from .set_state_status import SetStateStatus
    from .state_abort_details import StateAbortDetails
    from .state_accept_details import StateAcceptDetails
    from .state_reject_details import StateRejectDetails
    from .state_wait_details import StateWaitDetails
    from .worker_flow_run_response import WorkerFlowRunResponse


_public_api: dict[str, tuple[str, str]] = {
    "DeploymentResponse": (__spec__.parent, ".deployment_response"),
    "FlowRunResponse": (__spec__.parent, ".flow_run_response"),
    "GlobalConcurrencyLimitResponse": (
        __spec__.parent,
        ".global_concurrency_limit_response",
    ),
    "HistoryResponse": (__spec__.parent, ".history_response"),
    "HistoryResponseState": (__spec__.parent, ".history_response_state"),
    "MinimalConcurrencyLimitResponse": (
        __spec__.parent,
        ".minimal_concurrency_limit_response",
    ),
    "OrchestrationResult": (__spec__.parent, ".orchestration_result"),
    "SetStateStatus": (__spec__.parent, ".set_state_status"),
    "StateAbortDetails": (__spec__.parent, ".state_abort_details"),
    "StateAcceptDetails": (__spec__.parent, ".state_accept_details"),
    "StateRejectDetails": (__spec__.parent, ".state_reject_details"),
    "StateWaitDetails": (__spec__.parent, ".state_wait_details"),
    "WorkerFlowRunResponse": (__spec__.parent, ".worker_flow_run_response"),
}

__all__ = [
    "DeploymentResponse",
    "FlowRunResponse",
    "GlobalConcurrencyLimitResponse",
    "HistoryResponse",
    "HistoryResponseState",
    "MinimalConcurrencyLimitResponse",
    "OrchestrationResult",
    "SetStateStatus",
    "StateAbortDetails",
    "StateAcceptDetails",
    "StateRejectDetails",
    "StateWaitDetails",
    "WorkerFlowRunResponse",
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
