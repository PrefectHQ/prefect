"""
Custom Prefect CLI types
"""
import functools
from typing import List, Optional

import typer
import typer.core
import sys

from prefect._internal.compatibility.deprecated import generate_deprecation_message
from prefect.cli._utilities import with_cli_exception_handling
from prefect.settings import Setting
from prefect.utilities.asyncutils import is_async_fn, sync_compatible


def SettingsOption(setting: Setting, *args, **kwargs) -> typer.Option:
    """Custom `typer.Option` factory to load the default value from settings"""

    return typer.Option(
        # The default is dynamically retrieved
        setting.value,
        *args,
        # Typer shows "(dynamic)" by default. We'd like to actually show the value
        # that would be used if the parameter is not specified and a reference if the
        # source is from the environment or profile, but typer does not support this
        # yet. See https://github.com/tiangolo/typer/issues/354
        show_default=f"from {setting.name}",
        **kwargs,
    )


def SettingsArgument(setting: Setting, *args, **kwargs) -> typer.Argument:
    """Custom `typer.Argument` factory to load the default value from settings"""

    # See comments in `SettingsOption`
    return typer.Argument(
        setting.value,
        *args,
        show_default=f"from {setting.name}",
        **kwargs,
    )


def with_deprecated_message(warning: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            print("WARNING:", warning, file=sys.stderr, flush=True)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


class PrefectTyper(typer.Typer):
    """
    Wraps commands created by `Typer` to support async functions and handle errors.
    """

    def __init__(
        self,
        *args,
        deprecated: bool = False,
        deprecated_start_date: Optional[str] = None,
        deprecated_help: str = "",
        deprecated_name: str = "",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.deprecated = deprecated
        if self.deprecated:
            if not deprecated_name:
                raise ValueError("Provide the name of the deprecated command group.")
            self.deprecated_message = generate_deprecation_message(
                name=f"The {deprecated_name!r} command group",
                start_date=deprecated_start_date,
                help=deprecated_help,
            )

    def add_typer(
        self,
        typer_instance: "PrefectTyper",
        *args,
        no_args_is_help: bool = True,
        aliases: List[str] = None,
        **kwargs,
    ) -> None:
        """
        This will cause help to be default command for all sub apps unless specifically stated otherwise, opposite of before.
        """
        if aliases:
            for alias in aliases:
                super().add_typer(
                    typer_instance,
                    *args,
                    name=alias,
                    no_args_is_help=no_args_is_help,
                    hidden=True,
                    **kwargs,
                )

        return super().add_typer(
            typer_instance, *args, no_args_is_help=no_args_is_help, **kwargs
        )

    def command(self, *args, **kwargs):
        command_decorator = super().command(*args, **kwargs)

        def wrapper(fn):
            if is_async_fn(fn):
                fn = sync_compatible(fn)
            fn = with_cli_exception_handling(fn)
            if self.deprecated:
                fn = with_deprecated_message(self.deprecated_message)(fn)
            return command_decorator(fn)

        return wrapper
