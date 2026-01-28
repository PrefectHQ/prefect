"""
Custom Prefect CLI types
"""

import asyncio
import functools
import importlib
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Iterable, List, Optional

import typer
from rich.console import Console
from rich.theme import Theme
from typer.core import TyperGroup

from prefect._internal.compatibility.deprecated import generate_deprecation_message
from prefect.cli._utilities import with_cli_exception_handling
from prefect.settings import get_current_settings
from prefect.utilities.asyncutils import is_async_fn

if TYPE_CHECKING:
    from prefect.settings.legacy import Setting


def SettingsOption(setting: "Setting", *args: Any, **kwargs: Any) -> Any:
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


def SettingsArgument(setting: "Setting", *args: Any, **kwargs: Any) -> Any:
    """Custom `typer.Argument` factory to load the default value from settings"""

    # See comments in `SettingsOption`
    return typer.Argument(
        setting.value,
        *args,
        show_default=f"from {setting.name}",
        **kwargs,
    )


def with_deprecated_message(
    warning: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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
        *args: Any,
        deprecated: bool = False,
        deprecated_start_date: Optional[datetime] = None,
        deprecated_help: str = "",
        deprecated_name: str = "",
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)

        self.deprecated = deprecated
        if self.deprecated:
            if not deprecated_name:
                raise ValueError("Provide the name of the deprecated command group.")
            self.deprecated_message: str = generate_deprecation_message(
                name=f"The {deprecated_name!r} command group",
                start_date=deprecated_start_date,
                help=deprecated_help,
            )

        self.console = Console(
            highlight=False,
            theme=Theme({"prompt.choices": "bold blue"}),
            color_system="auto" if get_current_settings().cli.colors else None,
        )

    def add_typer(
        self,
        typer_instance: "PrefectTyper",
        *args: Any,
        no_args_is_help: bool = True,
        aliases: Optional[list[str]] = None,
        **kwargs: Any,
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
        *args: Any,
        aliases: Optional[List[str]] = None,
        deprecated: bool = False,
        deprecated_start_date: Optional[datetime] = None,
        deprecated_help: str = "",
        deprecated_name: str = "",
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Create a new command. If aliases are provided, the same command function
        will be registered with multiple names.

        Provide `deprecated=True` to mark the command as deprecated. If `deprecated=True`,
        `deprecated_name` and `deprecated_start_date` must be provided.
        """

        def wrapper(original_fn: Callable[..., Any]) -> Callable[..., Any]:
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
                def sync_fn(*args: Any, **kwargs: Any) -> Any:
                    return asyncio.run(async_fn(*args, **kwargs))

                setattr(sync_fn, "aio", async_fn)
                wrapped_fn = sync_fn
            else:
                wrapped_fn = original_fn

            wrapped_fn = with_cli_exception_handling(wrapped_fn)
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
                wrapped_fn = with_deprecated_message(command_deprecated_message)(
                    wrapped_fn
                )
            elif self.deprecated:
                wrapped_fn = with_deprecated_message(self.deprecated_message)(
                    wrapped_fn
                )

            # register fn with its original name
            command_decorator = super(PrefectTyper, self).command(
                name=name, *args, **kwargs
            )
            original_command = command_decorator(wrapped_fn)

            # register fn for each alias, e.g. @marvin_app.command(aliases=["r"])
            if aliases:
                for alias in aliases:
                    super(PrefectTyper, self).command(
                        name=alias,
                        *args,
                        **{k: v for k, v in kwargs.items() if k != "aliases"},
                    )(wrapped_fn)

            return original_command

        return wrapper

    def setup_console(self, soft_wrap: bool, prompt: bool) -> None:
        self.console = Console(
            highlight=False,
            color_system="auto" if get_current_settings().cli.colors else None,
            theme=Theme({"prompt.choices": "bold blue"}),
            soft_wrap=not soft_wrap,
            force_interactive=prompt,
        )


class LazyTyperGroup(TyperGroup):
    """Typer group that lazy-loads CLI modules on first access."""

    _lazy_commands: dict[str, tuple[str, ...]] = {}
    _loaded_modules: set[str] = set()
    _typer_instance: Optional[typer.Typer] = None

    @classmethod
    def register_lazy_commands(
        cls,
        commands: dict[str, Iterable[str] | str],
        *,
        typer_instance: Optional[typer.Typer] = None,
    ) -> None:
        normalized: dict[str, tuple[str, ...]] = {}
        for name, modules in commands.items():
            if isinstance(modules, str):
                normalized[name] = (modules,)
            else:
                normalized[name] = tuple(modules)

        cls._lazy_commands.update(normalized)
        if typer_instance is not None:
            cls._typer_instance = typer_instance

    def list_commands(self, ctx: typer.Context) -> list[str]:  # type: ignore[override]
        commands = set(super().list_commands(ctx))
        commands.update(self._lazy_commands.keys())
        return sorted(commands)

    def get_command(self, ctx: typer.Context, cmd_name: str):  # type: ignore[override]
        if cmd_name in self._lazy_commands:
            self._load_lazy_command(cmd_name)
        return super().get_command(ctx, cmd_name)

    def _load_lazy_command(self, cmd_name: str) -> None:
        modules = self._lazy_commands.get(cmd_name, ())
        for module in modules:
            if module in self._loaded_modules:
                continue
            importlib.import_module(module)
            self._loaded_modules.add(module)

        if self._typer_instance is None:
            return

        refreshed_group = typer.main.get_group(self._typer_instance)
        self.commands.update(refreshed_group.commands)
        self._prune_loaded_commands()

    def _prune_loaded_commands(self) -> None:
        if not self._lazy_commands:
            return
        loaded = self._loaded_modules
        ready = [
            name
            for name, modules in self._lazy_commands.items()
            if all(module in loaded for module in modules)
        ]
        for name in ready:
            self._lazy_commands.pop(name, None)
