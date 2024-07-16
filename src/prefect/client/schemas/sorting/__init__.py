from typing import TYPE_CHECKING
import importlib

if TYPE_CHECKING:
    from .artifact_collection_sort import ArtifactCollectionSort
    from .artifact_sort import ArtifactSort
    from .automation_sort import AutomationSort
    from .block_document_sort import BlockDocumentSort
    from .deployment_sort import DeploymentSort
    from .flow_run_sort import FlowRunSort
    from .flow_sort import FlowSort
    from .log_sort import LogSort
    from .task_run_sort import TaskRunSort
    from .variable_sort import VariableSort


_public_api: dict[str, tuple[str, str]] = {
    "ArtifactCollectionSort": (__spec__.parent, ".artifact_collection_sort"),
    "ArtifactSort": (__spec__.parent, ".artifact_sort"),
    "AutomationSort": (__spec__.parent, ".automation_sort"),
    "BlockDocumentSort": (__spec__.parent, ".block_document_sort"),
    "DeploymentSort": (__spec__.parent, ".deployment_sort"),
    "FlowRunSort": (__spec__.parent, ".flow_run_sort"),
    "FlowSort": (__spec__.parent, ".flow_sort"),
    "LogSort": (__spec__.parent, ".log_sort"),
    "TaskRunSort": (__spec__.parent, ".task_run_sort"),
    "VariableSort": (__spec__.parent, ".variable_sort"),
}

__all__ = [
    "ArtifactCollectionSort",
    "ArtifactSort",
    "AutomationSort",
    "BlockDocumentSort",
    "DeploymentSort",
    "FlowRunSort",
    "FlowSort",
    "LogSort",
    "TaskRunSort",
    "VariableSort",
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
