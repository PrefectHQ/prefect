from typing import Any, Callable

from box import Box

REGISTRY = Box(api=Box(), models=Box(), plugins=Box())
API = REGISTRY.api
MODELS = REGISTRY.models
PLUGINS = REGISTRY.plugins


def _register(name: str, registry: dict) -> Callable:
    """
    A decorator for registering an object to a registry.
    """

    def _register(obj: Any) -> Any:
        nonlocal registry
        keys = name.split(".")
        for key in keys[:-1]:
            registry = registry.setdefault(key, Box())
        registry[keys[-1]] = obj
        return obj

    return _register


def register_api(name: str) -> Callable:
    """
    Register an API function.

    Args:
        - name (str): the dot-delimited qualified name for the API function

    @register_api("fns.my_fn")
    def f(x):
        return x + 1

    assert API.fns.my_fn(100) == 101

    """
    return _register(name, registry=API)


def register_model(name: str) -> Callable:
    return _register(name, registry=MODELS)


def register_plugin(name: str) -> Callable:
    return _register(name, registry=PLUGINS)
