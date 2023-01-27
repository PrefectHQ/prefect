"""
Custom Prefect CLI types
"""
from typing import List

import typer
import typer.core

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


class PrefectTyper(typer.Typer):
    """
    Wraps commands created by `Typer` to support async functions and handle errors.
    """

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
            return command_decorator(fn)

        return wrapper
