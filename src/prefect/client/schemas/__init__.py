import importlib
import sys
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .actions import BlockTypeUpdate, StateCreate
    from .objects import (
        DEFAULT_BLOCK_SCHEMA_VERSION,
        BlockDocument,
        BlockSchema,
        BlockType,
        FlowRun,
        FlowRunPolicy,
        FlowRunResult,
        State,
        StateDetails,
        StateType,
        TaskRun,
        RunInput,
        TaskRunPolicy,
        TaskRunResult,
        Workspace,
    )
    from .pending_claims import (
        PENDING_CLAIM_CONTRACT,
        BindExecutionRequest,
        ClaimInfrastructureRequest,
        ExecutionLineage,
        PendingClaim,
        PendingClaimCreate,
        PendingClaimReference,
    )
    from .responses import (
        OrchestrationResult,
        SetStateStatus,
        StateAbortDetails,
        StateAcceptDetails,
        StateRejectDetails,
    )

_public_api = {
    "BlockDocument": (__package__, ".objects"),
    "BlockSchema": (__package__, ".objects"),
    "BlockType": (__package__, ".objects"),
    "BlockTypeUpdate": (__package__, ".actions"),
    "BindExecutionRequest": (__package__, ".pending_claims"),
    "ClaimInfrastructureRequest": (__package__, ".pending_claims"),
    "DEFAULT_BLOCK_SCHEMA_VERSION": (__package__, ".objects"),
    "FlowRun": (__package__, ".objects"),
    "FlowRunPolicy": (__package__, ".objects"),
    "FlowRunResult": (__package__, ".objects"),
    "ExecutionLineage": (__package__, ".pending_claims"),
    "OrchestrationResult": (__package__, ".responses"),
    "PENDING_CLAIM_CONTRACT": (__package__, ".pending_claims"),
    "PendingClaim": (__package__, ".pending_claims"),
    "PendingClaimCreate": (__package__, ".pending_claims"),
    "PendingClaimReference": (__package__, ".pending_claims"),
    "SetStateStatus": (__package__, ".responses"),
    "State": (__package__, ".objects"),
    "StateAbortDetails": (__package__, ".responses"),
    "StateAcceptDetails": (__package__, ".responses"),
    "StateCreate": (__package__, ".actions"),
    "StateDetails": (__package__, ".objects"),
    "StateRejectDetails": (__package__, ".responses"),
    "StateType": (__package__, ".objects"),
    "TaskRun": (__package__, ".objects"),
    "TaskRunInput": (__package__, ".objects"),
    "TaskRunPolicy": (__package__, ".objects"),
    "TaskRunResult": (__package__, ".objects"),
    "Workspace": (__package__, ".objects"),
}

__all__ = [
    "BlockDocument",
    "BlockSchema",
    "BlockType",
    "BlockTypeUpdate",
    "BindExecutionRequest",
    "ClaimInfrastructureRequest",
    "DEFAULT_BLOCK_SCHEMA_VERSION",
    "FlowRun",
    "FlowRunPolicy",
    "FlowRunResult",
    "ExecutionLineage",
    "OrchestrationResult",
    "PENDING_CLAIM_CONTRACT",
    "PendingClaim",
    "PendingClaimCreate",
    "PendingClaimReference",
    "SetStateStatus",
    "State",
    "StateAbortDetails",
    "StateAcceptDetails",
    "StateCreate",
    "StateDetails",
    "StateRejectDetails",
    "StateType",
    "TaskRun",
    "RunInput",
    "TaskRunPolicy",
    "TaskRunResult",
    "Workspace",
]


def __getattr__(attr_name: str) -> Any:
    try:
        if (dynamic_attr := _public_api.get(attr_name)) is None:
            raise AttributeError(f"module {__name__} has no attribute {attr_name}")

        package, mname = dynamic_attr
        module = importlib.import_module(mname, package=package)
        return getattr(module, attr_name)
    except ModuleNotFoundError as ex:
        mname, _, attr = (ex.name or "").rpartition(".")
        ctx = {"name": mname, "obj": attr} if sys.version_info >= (3, 10) else {}
        raise AttributeError(f"module {mname} has no attribute {attr}", **ctx) from ex
