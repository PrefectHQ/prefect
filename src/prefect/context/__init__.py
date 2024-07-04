import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ContextModel
    from .engine import EngineContext, FlowRunContext
    from .task import TaskRunContext
    from .client import ClientContext
    from .run import RunContext
    from .tags import TagsContext, tags
    from .settings import (
        SettingsContext,
        GLOBAL_SETTINGS_CONTEXT,
        root_settings_context,
        use_profile,
        get_settings_context,
    )
    from .utilities import get_run_context, serialize_context, hydrated_context


_public_api: dict[str, tuple[str, str]] = {
    "ContextModel": (__spec__.parent, ".base"),
    "FlowRunContext": (__spec__.parent, ".engine"),
    "EngineContext": (__spec__.parent, ".engine"),
    "TaskRunContext": (__spec__.parent, ".task"),
    "ClientContext": (__spec__.parent, ".client"),
    "RunContext": (__spec__.parent, ".run"),
    "TagsContext": (__spec__.parent, ".tags"),
    "tags": (__spec__.parent, ".tags"),
    "SettingsContext": (__spec__.parent, ".settings"),
    "GLOBAL_SETTINGS_CONTEXT": (__spec__.parent, ".settings"),
    "root_settings_context": (__spec__.parent, ".settings"),
    "use_profile": (__spec__.parent, ".settings"),
    "get_settings_context": (__spec__.parent, ".settings"),
    "get_run_context": (__spec__.parent, ".utilities"),
    "serialize_context": (__spec__.parent, ".utilities"),
    "hydrated_context": (__spec__.parent, ".utilities"),
}


# Declare API for type-checkers
__all__ = [
    "ContextModel",
    "FlowRunContext",
    "EngineContext",
    "TaskRunContext",
    "ClientContext",
    "RunContext",
    "TagsContext",
    "tags",
    "SettingsContext",
    "GLOBAL_SETTINGS_CONTEXT",
    "root_settings_context",
    "use_profile",
    "get_settings_context",
    "get_run_context",
    "serialize_context",
    "hydrated_context",
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
