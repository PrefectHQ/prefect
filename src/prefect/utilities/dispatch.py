"""
Provides methods for performing dynamic dispatch for actions on base type to one of its
subtypes.

Example:

```python
@register_base_type
class Base:
    @classmethod
    def __dispatch_key__(cls):
        return cls.__name__.lower()


class Foo(Base):
    ...

key = get_dispatch_key(Foo)  # 'foo'
lookup_type(Base, key) # Foo
```
"""

import abc
import inspect
import warnings
from typing import Any, Literal, Optional, TypeVar, overload

T = TypeVar("T", bound=type[Any])

_TYPE_REGISTRIES: dict[Any, dict[str, Any]] = {}


def get_registry_for_type(cls: T) -> Optional[dict[str, T]]:
    """
    Get the first matching registry for a class or any of its base classes.

    If not found, `None` is returned.
    """
    return next(
        (reg for cls in cls.mro() if (reg := _TYPE_REGISTRIES.get(cls)) is not None),
        None,
    )


@overload
def get_dispatch_key(
    cls_or_instance: Any, allow_missing: Literal[False] = False
) -> str: ...


@overload
def get_dispatch_key(
    cls_or_instance: Any, allow_missing: Literal[True] = ...
) -> Optional[str]: ...


def get_dispatch_key(
    cls_or_instance: Any, allow_missing: bool = False
) -> Optional[str]:
    """
    Retrieve the unique dispatch key for a class type or instance.

    This key is defined at the `__dispatch_key__` attribute. If it is a callable, it
    will be resolved.

    If `allow_missing` is `False`, an exception will be raised if the attribute is not
    defined or the key is null. If `True`, `None` will be returned in these cases.
    """
    dispatch_key = getattr(cls_or_instance, "__dispatch_key__", None)

    type_name = (
        cls_or_instance.__name__
        if isinstance(cls_or_instance, type)
        else type(cls_or_instance).__name__
    )

    if dispatch_key is None:
        if allow_missing:
            return None
        raise ValueError(
            f"Type {type_name!r} does not define a value for "
            "'__dispatch_key__' which is required for registry lookup."
        )

    if callable(dispatch_key):
        dispatch_key = dispatch_key()

    if allow_missing and dispatch_key is None:
        return None

    if not isinstance(dispatch_key, str):
        raise TypeError(
            f"Type {type_name!r} has a '__dispatch_key__' of type "
            f"{type(dispatch_key).__name__} but a type of 'str' is required."
        )

    return dispatch_key


@classmethod
def _register_subclass_of_base_type(cls: type[Any], **kwargs: Any) -> None:
    if hasattr(cls, "__init_subclass_original__"):
        cls.__init_subclass_original__(**kwargs)
    elif hasattr(cls, "__pydantic_init_subclass_original__"):
        cls.__pydantic_init_subclass_original__(**kwargs)

    # Do not register abstract base classes
    if abc.ABC in cls.__bases__:
        return

    register_type(cls)


def register_base_type(cls: T) -> T:
    """
    Register a base type allowing child types to be registered for dispatch with
    `register_type`.

    The base class may or may not define a `__dispatch_key__` to allow lookups of the
    base type.
    """
    registry = _TYPE_REGISTRIES.setdefault(cls, {})
    base_key = get_dispatch_key(cls, allow_missing=True)
    if base_key is not None:
        registry[base_key] = cls

    # Add automatic subtype registration
    if hasattr(cls, "__pydantic_init_subclass__"):
        cls.__pydantic_init_subclass_original__ = getattr(
            cls, "__pydantic_init_subclass__"
        )
        cls.__pydantic_init_subclass__ = _register_subclass_of_base_type
    else:
        cls.__init_subclass_original__ = getattr(cls, "__init_subclass__")
        setattr(cls, "__init_subclass__", _register_subclass_of_base_type)

    return cls


def register_type(cls: T) -> T:
    """
    Register a type for lookup with dispatch.

    The type or one of its parents must define a unique `__dispatch_key__`.

    One of the classes base types must be registered using `register_base_type`.
    """
    # Lookup the registry for this type
    registry = get_registry_for_type(cls)

    # Check if a base type is registered
    if registry is None:
        # Include a description of registered base types
        known = ", ".join(repr(base.__name__) for base in _TYPE_REGISTRIES)
        known_message = (
            f" Did you mean to inherit from one of the following known types: {known}."
            if known
            else ""
        )

        # And a list of all base types for the type they tried to register
        bases = ", ".join(
            repr(base.__name__) for base in cls.mro() if base not in (object, cls)
        )

        raise ValueError(
            f"No registry found for type {cls.__name__!r} with bases {bases}."
            + known_message
        )

    key = get_dispatch_key(cls)
    existing_value = registry.get(key)
    if existing_value is not None and id(existing_value) != id(cls):
        try:
            # Get line numbers for debugging
            file = inspect.getsourcefile(cls)
            line_number = inspect.getsourcelines(cls)[1]
            existing_file = inspect.getsourcefile(existing_value)
            existing_line_number = inspect.getsourcelines(existing_value)[1]
            warnings.warn(
                f"Type {cls.__name__!r} at {file}:{line_number} has key {key!r} that "
                f"matches existing registered type {existing_value.__name__!r} from "
                f"{existing_file}:{existing_line_number}. The existing type will be "
                "overridden."
            )
        except OSError:
            # If we can't get the source, another actor is loading this class via eval
            # and we shouldn't update the registry
            return cls

    # Add to the registry
    registry[key] = cls

    return cls


def lookup_type(cls: T, dispatch_key: str) -> T:
    """
    Look up a dispatch key in the type registry for the given class.
    """
    # Get the first matching registry for the class or one of its bases
    registry = get_registry_for_type(cls) or {}

    # Look up this type in the registry
    subcls = registry.get(dispatch_key)

    if subcls is None:
        raise KeyError(
            f"No class found for dispatch key {dispatch_key!r} in registry for type "
            f"{cls.__name__!r}."
        )

    return subcls
