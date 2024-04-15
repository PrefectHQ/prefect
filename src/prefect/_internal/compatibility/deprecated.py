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
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field, root_validator
    from pydantic.v1.schema import default_ref_template
else:
    from pydantic import BaseModel, Field, root_validator
    from pydantic.schema import default_ref_template

from prefect.utilities.callables import get_call_parameters
from prefect.utilities.importtools import (
    AliasedModuleDefinition,
    AliasedModuleFinder,
    to_qualified_name,
)

T = TypeVar("T", bound=Callable)
M = TypeVar("M", bound=BaseModel)


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


def deprecated_class(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    stacklevel: int = 2,
    help: str = "",
) -> Callable[[T], T]:
    def decorator(cls: T):
        message = generate_deprecation_message(
            name=to_qualified_name(cls),
            start_date=start_date,
            end_date=end_date,
            help=help,
        )

        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            warnings.warn(message, PrefectDeprecationWarning, stacklevel=stacklevel)
            original_init(self, *args, **kwargs)

        cls.__init__ = new_init
        return cls

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
        class Model(BaseModel)
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


class DeprecatedInfraOverridesField(BaseModel):
    """
    A model mixin that handles the deprecated `infra_overrides` field.

    The `infra_overrides` field has been renamed to `job_variables`. This mixin maintains
    backwards compatibility with users of the `infra_overrides` field while presenting
    `job_variables` as the user-facing field.

    When we remove support for `infra_overrides`, we can remove this class as a parent of
    all schemas that use it, leaving them with only the `job_variables` field.
    """

    infra_overrides: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Deprecated field. Use `job_variables` instead.",
    )

    @root_validator(pre=True)
    def _job_variables_from_infra_overrides(
        cls, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that only one of `infra_overrides` or `job_variables` is used
        and keep them in sync during init.
        """
        job_variables = values.get("job_variables")
        infra_overrides = values.get("infra_overrides")

        if job_variables is not None and infra_overrides is not None:
            if job_variables != infra_overrides:
                raise ValueError(
                    "The `infra_overrides` field has been renamed to `job_variables`."
                    "Use one of these fields, but not both."
                )
            return values
        elif job_variables is not None and infra_overrides is None:
            values["infra_overrides"] = job_variables
        elif job_variables is None and infra_overrides is not None:
            values["job_variables"] = infra_overrides
        return values

    def __setattr__(self, key: str, value: Any) -> None:
        """
        Override the default __setattr__ to ensure that setting `infra_overrides` or
        `job_variables` will update both fields.
        """
        if key == "infra_overrides" or key == "job_variables":
            updates = {"infra_overrides": value, "job_variables": value}
            self.__dict__.update(updates)
            return
        super().__setattr__(key, value)

    def dict(self, **kwargs) -> Dict[str, Any]:
        """
        Override the default dict method to ensure only `infra_overrides` is serialized.
        This preserves backwards compatibility for newer clients talking to older servers.
        """
        exclude: Union[set, Dict[str, Any]] = kwargs.pop("exclude", set())
        exclude_type = type(exclude)

        if exclude_type is set:
            exclude.add("job_variables")
        elif exclude_type is dict:
            exclude["job_variables"] = True
        else:
            exclude = {"job_variables"}
        kwargs["exclude"] = exclude

        return super().dict(**kwargs)

    @classmethod
    def schema(
        cls, by_alias: bool = True, ref_template: str = default_ref_template
    ) -> Dict[str, Any]:
        """
        Don't use the mixin docstring as the description if this class is missing a
        docstring.
        """
        schema = super().schema(by_alias=by_alias, ref_template=ref_template)

        if not cls.__doc__:
            schema.pop("description", None)

        return schema


def handle_deprecated_infra_overrides_parameter(
    job_variables: Dict[str, Any], infra_overrides: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if infra_overrides is not None and job_variables is not None:
        raise RuntimeError(
            "The `infra_overrides` argument has been renamed to `job_variables`."
            "Use one or the other, but not both."
        )
    elif infra_overrides is not None and job_variables is None:
        jv = infra_overrides
    elif job_variables is not None and infra_overrides is None:
        jv = job_variables
    else:
        jv = None
    return jv
