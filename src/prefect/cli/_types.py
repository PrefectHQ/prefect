"""
Custom Prefect CLI types
"""

import asyncio
import functools
import sys
from typing import (
    Any,
    Callable,
    Concatenate,
    Coroutine,
    Generic,
    List,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

import typer
from rich.console import Console
from rich.theme import Theme
from typer.core import TyperCommand
from typing_extensions import ParamSpec

from prefect._internal.compatibility.deprecated import generate_deprecation_message
from prefect.cli._utilities import with_cli_exception_handling
from prefect.settings import PREFECT_CLI_COLORS, Setting
from prefect.utilities.asyncutils import is_async_fn, sync

P = ParamSpec("P")

R = TypeVar("R")
T = TypeVar("T")


def with_settings(
    func: Callable[Concatenate[Any, P], T],
) -> Callable[Concatenate[Setting, P], T]:
    @functools.wraps(func)
    def wrapper(setting: Setting, *args: P.args, **kwargs: P.kwargs) -> T:
        kwargs.update({"show_default": f"from {setting.name}"})
        return func(setting.value, *args, **kwargs)

    return wrapper


SettingsOption = with_settings(typer.Option)


def with_deprecated_message(warning: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            print("WARNING:", warning, file=sys.stderr, flush=True)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


class _WrappedCallable(Protocol[P, T]):
    __wrapped__: Callable[P, T]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T: ...


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

    def acommand(
        self,
        name: Optional[str] = None,
        *,
        cls: Optional[Type[TyperCommand]] = None,
        context_settings: Optional[dict[str, Any]] = None,
        help: Optional[str] = None,
        epilog: Optional[str] = None,
        short_help: Optional[str] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
    ) -> Callable[
        [Callable[P, Coroutine[Any, Any, T]]],
        _WrappedCallable[P, T],
    ]:
        """
        Decorator for registering a command on this Typer app that MUST be async.

        If the decorated function is async, it will be wrapped via your custom
        sync(...) method so Typer sees a synchronous function.

        If the decorated function is NOT async, a TypeError is raised.
        """

        def wrapper(fn: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, T]:
            @functools.wraps(fn)
            def sync_fn(*args: P.args, **kwargs: P.kwargs) -> T:
                return sync(fn, *args, **kwargs)

            command_decorator = super(PrefectTyper, self).command(
                name=name,
                cls=cls,
                context_settings=context_settings,
                help=help,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                no_args_is_help=no_args_is_help,
                hidden=hidden,
                deprecated=deprecated,
            )
            return command_decorator(sync_fn)

        return wrapper

    def command(
        self,
        name: Optional[str] = None,
        *args,
        aliases: Optional[List[str]] = None,
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

        def wrapper(original_fn: Callable):
            # click doesn't support async functions, so we wrap them in
            # asyncio.run(). This has the advantage of keeping the function in
            # the main thread, which means signal handling works for e.g. the
            # server and workers. However, it means that async CLI commands can
            # not directly call other async CLI commands (because asyncio.run()
            # can not be called nested). In that (rare) circumstance, refactor
            # the CLI command so its business logic can be invoked separately
            # from its entrypoint.
            if is_async_fn(original_fn):
                async_fn = original_fn

                @functools.wraps(original_fn)
                def sync_fn(*args, **kwargs):
                    return asyncio.run(async_fn(*args, **kwargs))

                sync_fn.aio = async_fn
                wrapped_fn = sync_fn
            else:
                wrapped_fn = original_fn

            # register fn with its original name
            command_decorator = super(PrefectTyper, self).command(
                name=name, *args, **kwargs
            )
            original_command = command_decorator(wrapped_fn)

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
