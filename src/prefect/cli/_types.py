"""
Custom Prefect CLI types
"""

import asyncio
import functools
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.theme import Theme

from prefect._internal.compatibility.deprecated import generate_deprecation_message
from prefect.cli._utilities import with_cli_exception_handling
from prefect.settings import PREFECT_CLI_COLORS, Setting
from prefect.utilities.asyncutils import is_async_fn


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

    console: Console

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

        self.console = Console(
            highlight=False,
            theme=Theme({"prompt.choices": "bold blue"}),
            color_system="auto" if PREFECT_CLI_COLORS else None,
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

    def command(
        self,
        name: Optional[str] = None,
        *args,
        aliases: List[str] = None,
        deprecated: bool = False,
        deprecated_start_date: Optional[str] = None,
        deprecated_help: str = "",
        deprecated_name: str = "",
        **kwargs,
    ):
        """
        Create a new command. If aliases are provided, the same command function
        will be registered with multiple names.

        Provide `deprecated=True` to mark the command as deprecated. If `deprecated=True`,
        `deprecated_name` and `deprecated_start_date` must be provided.
        """

        def wrapper(fn):
            # click doesn't support async functions, so we wrap them in
            # asyncio.run(). This has the advantage of keeping the function in
            # the main thread, which means signal handling works for e.g. the
            # server and workers. However, it means that async CLI commands can
            # not directly call other async CLI commands (because asyncio.run()
            # can not be called nested). In that (rare) circumstance, refactor
            # the CLI command so its business logic can be invoked separately
            # from its entrypoint.
            if is_async_fn(fn):
                _fn = fn

                @functools.wraps(fn)
                def fn(*args, **kwargs):
                    return asyncio.run(_fn(*args, **kwargs))

                fn.aio = _fn

            fn = with_cli_exception_handling(fn)
            if deprecated:
                if not deprecated_name or not deprecated_start_date:
                    raise ValueError(
                        "Provide the name of the deprecated command and a deprecation start date."
                    )
                command_deprecated_message = generate_deprecation_message(
                    name=f"The {deprecated_name!r} command",
                    start_date=deprecated_start_date,
                    help=deprecated_help,
                )
                fn = with_deprecated_message(command_deprecated_message)(fn)
            elif self.deprecated:
                fn = with_deprecated_message(self.deprecated_message)(fn)

            # register fn with its original name
            command_decorator = super(PrefectTyper, self).command(
                name=name, *args, **kwargs
            )
            original_command = command_decorator(fn)

            # register fn for each alias, e.g. @marvin_app.command(aliases=["r"])
            if aliases:
                for alias in aliases:
                    super(PrefectTyper, self).command(
                        name=alias,
                        *args,
                        **{k: v for k, v in kwargs.items() if k != "aliases"},
                    )(fn)

            return original_command

        return wrapper

    def setup_console(self, soft_wrap: bool, prompt: bool):
        self.console = Console(
            highlight=False,
            color_system="auto" if PREFECT_CLI_COLORS else None,
            theme=Theme({"prompt.choices": "bold blue"}),
            soft_wrap=not soft_wrap,
            force_interactive=prompt,
        )
