"""
Utilities for deprecated items.

When a deprecated item is used, a warning will be displayed. Warnings may not be
disabled with Prefect settings. Instead, the standard Python warnings filters can be
used.

Deprecated items require a start or end date. If a start date is given, the end date
will be calculated 6 months later. Start and end dates are always in the format MMM YYYY
e.g. Jan 2023.
"""
import functools
import sys
import warnings
from typing import Any, Callable, List, Optional, Type, TypeVar

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from prefect.utilities.callables import get_call_parameters
from prefect.utilities.importtools import (
    AliasedModuleDefinition,
    AliasedModuleFinder,
    to_qualified_name,
)

T = TypeVar("T", bound=Callable)
M = TypeVar("M", bound=pydantic.BaseModel)


DEPRECATED_WARNING = (
    "{name} has been deprecated{when}. It will not be available after {end_date}."
    " {help}"
)
DEPRECATED_MOVED_WARNING = (
    "{name} has moved to {new_location}. It will not be available at the old import "
    "path after {end_date}. {help}"
)
DEPRECATED_DATEFMT = "MMM YYYY"  # e.g. Feb 2023
DEPRECATED_MODULE_ALIASES: List[AliasedModuleDefinition] = []


class PrefectDeprecationWarning(DeprecationWarning):
    """
    A deprecation warning.
    """


def generate_deprecation_message(
    name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    help: str = "",
    when: str = "",
):
    if not start_date and not end_date:
        raise ValueError(
            "A start date is required if an end date is not provided. Suggested start"
            f" date is {pendulum.now('UTC').format(DEPRECATED_DATEFMT)!r}"
        )

    if not end_date:
        parsed_start_date = pendulum.from_format(start_date, DEPRECATED_DATEFMT)
        parsed_end_date = parsed_start_date.add(months=6)
        end_date = parsed_end_date.format(DEPRECATED_DATEFMT)
    else:
        # Validate format
        pendulum.from_format(end_date, DEPRECATED_DATEFMT)

    if when:
        when = " when " + when

    message = DEPRECATED_WARNING.format(
        name=name, when=when, end_date=end_date, help=help
    )
    return message.rstrip()


def deprecated_callable(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stacklevel: int = 2,
    help: str = "",
) -> Callable[[T], T]:
    def decorator(fn: T):
        message = generate_deprecation_message(
            name=to_qualified_name(fn),
            start_date=start_date,
            end_date=end_date,
            help=help,
        )

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            warnings.warn(message, PrefectDeprecationWarning, stacklevel=stacklevel)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def deprecated_parameter(
    name: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stacklevel: int = 2,
    help: str = "",
    when: Optional[Callable[[Any], bool]] = None,
    when_message: str = "",
) -> Callable[[T], T]:
    """
    Mark a parameter in a callable as deprecated.

    Example:

        ```python

        @deprecated_parameter("y", when=lambda y: y is not None)
        def foo(x, y = None):
            return x + 1 + (y or 0)
        ```
    """

    when = when or (lambda _: True)

    def decorator(fn: T):
        message = generate_deprecation_message(
            name=f"The parameter {name!r} for {fn.__name__!r}",
            start_date=start_date,
            end_date=end_date,
            help=help,
            when=when_message,
        )

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                parameters = get_call_parameters(fn, args, kwargs, apply_defaults=False)
            except Exception:
                # Avoid raising any parsing exceptions here
                parameters = kwargs

            if name in parameters and when(parameters[name]):
                warnings.warn(message, PrefectDeprecationWarning, stacklevel=stacklevel)

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def deprecated_field(
    name: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    when_message: str = "",
    help: str = "",
    when: Optional[Callable[[Any], bool]] = None,
    stacklevel: int = 2,
):
    """
    Mark a field in a Pydantic model as deprecated.

    Raises warning only if the field is specified during init.

    Example:

        ```python

        @deprecated_field("x", when=lambda x: x is not None)
        class Model(pydantic.BaseModel)
            x: Optional[int] = None
            y: str
        ```
    """

    when = when or (lambda _: True)

    # Replaces the model's __init__ method with one that performs an additional warning
    # check
    def decorator(model_cls: Type[M]) -> Type[M]:
        message = generate_deprecation_message(
            name=f"The field {name!r} in {model_cls.__name__!r}",
            start_date=start_date,
            end_date=end_date,
            help=help,
            when=when_message,
        )

        cls_init = model_cls.__init__

        @functools.wraps(model_cls.__init__)
        def __init__(__pydantic_self__, **data: Any) -> None:
            if name in data.keys() and when(data[name]):
                warnings.warn(message, PrefectDeprecationWarning, stacklevel=stacklevel)

            cls_init(__pydantic_self__, **data)

            field = __pydantic_self__.__fields__.get(name)
            if field is not None:
                field.field_info.extra["deprecated"] = True

        # Patch the model's init method
        model_cls.__init__ = __init__

        return model_cls

    return decorator


def inject_renamed_module_alias_finder():
    """
    Insert an aliased module finder into Python's import machinery.

    Required for `register_renamed_module` to work.
    """
    sys.meta_path.insert(0, AliasedModuleFinder(DEPRECATED_MODULE_ALIASES))


def register_renamed_module(old_name: str, new_name: str, start_date: str):
    """
    Register a renamed module.

    Adds backwwards compatibility imports for the old module name and displays a
    deprecation warnings on import of the module.
    """
    message = generate_deprecation_message(
        name=f"The {old_name!r} module",
        start_date=start_date,
        help=f"Use {new_name!r} instead.",
    )

    # Executed on module load
    def callback(_):
        return warnings.warn(message, DeprecationWarning, stacklevel=3)

    DEPRECATED_MODULE_ALIASES.append(
        AliasedModuleDefinition(old_name, new_name, callback)
    )
