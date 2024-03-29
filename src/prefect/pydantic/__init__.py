import typing
from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

if typing.TYPE_CHECKING:
    # import of virtually everything is supported via `__getattr__` below,
    # but we need them here for type checking and IDE support
    from pydantic import Field, SecretField
    from .main import BaseModel, PrefectBaseModel

__all__ = ["BaseModel", "PrefectBaseModel", "Field", "SecretField"]

_dynamic_imports: "typing.Dict[str, tuple[str, str]]" = {
    "BaseModel": ("prefect.pydantic.main", "BaseModel"),
    "PrefectBaseModel": ("prefect.pydantic.main", "PrefectBaseModel"),
}


def __getattr__(attr_name: str) -> object:
    from importlib import import_module

    if attr_name in _dynamic_imports:
        # If the attribute is in the dynamic imports, import it from the specified module
        module_path, module_name = _dynamic_imports[attr_name]
        module = import_module(module_path, module_name)
        return getattr(module, module_name)
    elif HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
        # In this case, we are using Pydantic v2 but it is not enabled, so we should import from pydantic.v1
        module = import_module("pydantic.v1", attr_name)
        return module
    else:
        # In this case, we are using either Pydantic v1 or Pydantic v2 is enabled, so we should import from pydantic
        module = import_module("pydantic", attr_name)
        return module
