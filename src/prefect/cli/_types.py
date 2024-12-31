"""
Custom Prefect CLI types
"""

import functools
from typing import (
    Any,
    Callable,
    Concatenate,
    Coroutine,
    Optional,
    Protocol,
    Type,
    TypeVar,
)

import typer
from rich.console import Console
from rich.theme import Theme
from typer.core import TyperCommand
from typing_extensions import ParamSpec

from prefect.settings import PREFECT_CLI_COLORS, Setting
from prefect.utilities.asyncutils import sync

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


class _WrappedCallable(Protocol[P, T]):
    __wrapped__: Callable[P, T]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T: ...


class PrefectTyper(typer.Typer):
    """
    Wraps commands created by `Typer` to support async functions and handle errors.
    """

    console: Console

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
        Callable[P, T],
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

    def setup_console(self, soft_wrap: bool, prompt: bool):
        self.console = Console(
            highlight=False,
            color_system="auto" if PREFECT_CLI_COLORS else None,
            theme=Theme({"prompt.choices": "bold blue"}),
            soft_wrap=not soft_wrap,
            force_interactive=prompt,
        )
