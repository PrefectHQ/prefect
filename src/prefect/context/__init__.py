from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import (
        SettingsContext,
        TagsContext,
        RunContext,
        ClientContext,
        ContextModel,
        use_profile,
        MissingContextError,
        get_settings_context,
        tags,
    )

    from .flow import FlowRunContext
    from .task import TaskRunContext
    from .utilities import serialize_context, get_run_context, hydrated_context

_public_api: dict[str, tuple[str, str]] = {
    "FlowRunContext": (__spec__.parent, ".flow"),
    "TaskRunContext": (__spec__.parent, ".task"),
    "SettingsContext": (__spec__.parent, ".main"),
    "TagsContext": (__spec__.parent, ".main"),
    "RunContext": (__spec__.parent, ".main"),
    "ClientContext": (__spec__.parent, ".main"),
    "serialize_context": (__spec__.parent, ".utilities"),
    "ContextModel": (__spec__.parent, ".main"),
    "use_profile": (__spec__.parent, ".main"),
    "get_settings_context": (__spec__.parent, ".main"),
    "MissingContextError": (__spec__.parent, ".main"),
    "get_run_context": (__spec__.parent, ".utilities"),
    "hydrated_context": (__spec__.parent, ".utilities"),
    "tags": (__spec__.parent, ".main"),
}

# Declare API for type-checkers
__all__ = [
    "FlowRunContext",
    "TaskRunContext",
    "SettingsContext",
    "TagsContext",
    "RunContext",
    "ClientContext",
    "serialize_context",
    "ContextModel",
    "use_profile",
    "MissingContextError",
    "get_settings_context",
    "get_run_context",
    "hydrated_context",
    "tags",
]


def __getattr__(attr_name: str) -> object:
    from importlib import import_module

    dynamic_attr = _public_api.get(attr_name)
    if dynamic_attr is None:
        return import_module(f".{attr_name}", package=__name__)

    package, module_name = dynamic_attr

    if module_name == "__module__":
        return import_module(f".{attr_name}", package=package)
    else:
        module = import_module(module_name, package=package)
        return getattr(module, attr_name)
