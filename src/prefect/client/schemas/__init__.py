# Some objects are exported here for backwards compatibility.
# In general, it is recommended to import schemas from their respective modules.

from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    from .actions import BlockTypeUpdate, StateCreate
    from .objects import (
        DEFAULT_BLOCK_SCHEMA_VERSION,
        BlockDocument,
        BlockSchema,
        BlockType,
        FlowRun,
        FlowRunPolicy,
        State,
        StateDetails,
        StateType,
        TaskRun,
        TaskRunInput,
        TaskRunPolicy,
        TaskRunResult,
        Workspace,
    )
    from .responses import (
        OrchestrationResult,
        SetStateStatus,
        StateAbortDetails,
        StateAcceptDetails,
        StateRejectDetails,
    )


_public_api: dict[str, tuple[str, str]] = {
    "BlockTypeUpdate": (__spec__.parent, ".actions"),
    "StateCreate": (__spec__.parent, ".actions"),
    "DEFAULT_BLOCK_SCHEMA_VERSION": (__spec__.parent, ".objects"),
    "BlockDocument": (__spec__.parent, ".objects"),
    "BlockSchema": (__spec__.parent, ".objects"),
    "BlockType": (__spec__.parent, ".objects"),
    "FlowRun": (__spec__.parent, ".objects"),
    "FlowRunPolicy": (__spec__.parent, ".objects"),
    "State": (__spec__.parent, ".objects"),
    "StateDetails": (__spec__.parent, ".objects"),
    "StateType": (__spec__.parent, ".objects"),
    "TaskRun": (__spec__.parent, ".objects"),
    "TaskRunInput": (__spec__.parent, ".objects"),
    "TaskRunPolicy": (__spec__.parent, ".objects"),
    "TaskRunResult": (__spec__.parent, ".objects"),
    "Workspace": (__spec__.parent, ".objects"),
    "OrchestrationResult": (__spec__.parent, ".responses"),
    "SetStateStatus": (__spec__.parent, ".responses"),
    "StateAbortDetails": (__spec__.parent, ".responses"),
    "StateAcceptDetails": (__spec__.parent, ".responses"),
    "StateRejectDetails": (__spec__.parent, ".responses"),
}

__all__ = [
    "BlockTypeUpdate",
    "StateCreate",
    "DEFAULT_BLOCK_SCHEMA_VERSION",
    "BlockDocument",
    "BlockSchema",
    "BlockType",
    "FlowRun",
    "FlowRunPolicy",
    "State",
    "StateDetails",
    "StateType",
    "TaskRun",
    "TaskRunInput",
    "TaskRunPolicy",
    "TaskRunResult",
    "Workspace",
    "OrchestrationResult",
    "SetStateStatus",
    "StateAbortDetails",
    "StateAcceptDetails",
    "StateRejectDetails",
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
