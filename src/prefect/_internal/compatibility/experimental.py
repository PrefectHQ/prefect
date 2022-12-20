"""
Utilities for experimental features.

Experimental features have a group, feature name, and optional help string.

When an experimental feature is used, a warning will be displayed. Warnings may be
disabled per feature group with the setting `PREFECT_EXPERIMENTAL_WARN_<GROUP>`. 
Warnings may also be disabled globally with the setting `PREFECT_EXPERIMENTAL_WARN`.

Some experimental features require opt-in to enable any usage. These require the setting
`PREFECT_EXPERIMENTAL_ENABLE_<GROUP>` to be set or an error will be thrown on use.
"""
import functools
import warnings
from typing import Any, Callable, Optional, Set, TypeVar

from prefect.settings import PREFECT_EXPERIMENTAL_WARN, SETTING_VARIABLES, Setting
from prefect.utilities.callables import get_call_parameters

T = TypeVar("T", bound=Callable)


EXPERIMENTAL_WARNING = (
    "{feature} is experimental. {help}"
    "The interface or behavior may change without warning, we recommend pinning versions to prevent unexpected changes. "
    "To disable warnings for this group of experiments, disable PREFECT_EXPERIMENTAL_WARN_{group}."
)

EXPERIMENTAL_ERROR = (
    "{feature} is experimental and requires opt-in for usage. {help}"
    "To use this feature, enable PREFECT_EXPERIMENTAL_ENABLE_{group}."
)


class ExperimentalWarning(Warning):
    """
    A warning related to expirimental code.
    """


class ExperimentalError(Exception):
    """
    An exception related to experimental code.
    """


class ExperimentalFeature(ExperimentalWarning):
    """
    A warning displayed on use of an experimental feature.

    These can be globally disabled by the PREFECT_EXPIRIMENTAL_WARN setting.
    """


class ExperimentalFeatureDisabled(ExperimentalError):
    """
    An error displayed on use of a disabled experimental feature that requires opt-in.
    """


def _opt_in_setting_for_group(group: str) -> Setting[bool]:
    group_opt_in_setting_name = f"PREFECT_EXPERIMENTAL_ENABLE_{group.upper()}"
    group_opt_in = SETTING_VARIABLES.get(group_opt_in_setting_name)
    if group_opt_in is None:
        raise ValueError(
            f"A opt-in setting for experimental feature {group!r} does not exist yet. "
            f"{group_opt_in_setting_name!r} must be created before the group can be "
            "used."
        )
    return group_opt_in


def _warn_setting_for_group(group: str) -> Setting[bool]:
    group_warn_setting_name = f"PREFECT_EXPERIMENTAL_WARN_{group.upper()}"
    group_warn = SETTING_VARIABLES.get(group_warn_setting_name)
    if group_warn is None:
        raise ValueError(
            f"A warn setting for experimental feature {group!r} does not exist yet. "
            f"{group_warn_setting_name!r} must be created before the group can be used."
        )
    return group_warn


def experimental(
    feature: str,
    *,
    group: str,
    help: str = "",
    stacklevel: int = 2,
    opt_in: bool = False,
) -> Callable[[T], T]:
    group = group.upper()

    if help:
        # Ensure help ends in a trailing space
        help = help.rstrip() + " "

    warn_message = EXPERIMENTAL_WARNING.format(feature=feature, group=group, help=help)
    error_message = EXPERIMENTAL_ERROR.format(feature=feature, group=group, help=help)

    if opt_in:
        group_opt_in = _opt_in_setting_for_group(group)

    group_warn = _warn_setting_for_group(group)

    def decorator(fn: T):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if opt_in and not group_opt_in:
                raise ExperimentalFeatureDisabled(error_message)

            if PREFECT_EXPERIMENTAL_WARN and group_warn:
                warnings.warn(
                    warn_message,
                    ExperimentalFeature,
                    stacklevel=stacklevel,
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def experiment_enabled(group: str) -> bool:
    group_opt_in = _opt_in_setting_for_group(group)
    return group_opt_in.value()


def experimental_parameter(
    name: str,
    *,
    group: str,
    help: str = "",
    stacklevel: int = 2,
    opt_in: bool = False,
    when: Optional[Callable[[Any], bool]] = None,
) -> Callable[[T], T]:
    """
    Mark a parameter in a callable as experimental.

    Example:

        ```python

        @experimental_parameter("y", group="example", when=lambda y: y is not None)
        def foo(x, y = None):
            return x + 1 + (y or 0)
        ```
    """

    when = when or (lambda _: True)

    @experimental(
        group=group,
        feature=f"The parameter {name!r}",
        help=help,
        opt_in=opt_in,
        stacklevel=stacklevel + 2,
    )
    def experimental_check():
        pass

    def decorator(fn: T):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                parameters = get_call_parameters(fn, args, kwargs, apply_defaults=False)
            except Exception:
                # Avoid raising any parsing exceptions here
                parameters = kwargs

            if name in parameters and when(parameters[name]):
                experimental_check()
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def enabled_experiments() -> Set[str]:
    """
    Return the set of all enabled experiments.
    """
    return {
        name[len("PREFECT_EXPERIMENTAL_ENABLE_") :].lower()
        for name, setting in SETTING_VARIABLES.items()
        if name.startswith("PREFECT_EXPERIMENTAL_ENABLE_") and setting.value()
    }
