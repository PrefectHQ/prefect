"""
Utilities for cyclopts CLI commands.

Mirrors prefect.cli._utilities but uses sys.exit instead of typer.Exit.
"""

import functools
import inspect
import json
import textwrap
import traceback
from typing import Any, Callable, NoReturn

import prefect.cli._app as _cli


def exit_with_error(message: str | Exception, code: int = 1, **kwargs: Any) -> NoReturn:
    """Print a stylized error message and exit with a non-zero code."""
    kwargs.setdefault("style", "red")
    _cli.console.print(message, **kwargs)
    raise SystemExit(code)


def exit_with_success(message: str, **kwargs: Any) -> NoReturn:
    """Print a stylized success message and exit with a zero code."""
    kwargs.setdefault("style", "green")
    _cli.console.print(message, **kwargs)
    raise SystemExit(0)


def with_cli_exception_handling(fn: Callable[..., Any]) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except SystemExit:
                raise
            except KeyboardInterrupt:
                raise SystemExit(1)
            except Exception:
                from prefect.settings import get_current_settings

                if get_current_settings().testing.test_mode:
                    raise
                traceback.print_exc()
                exit_with_error("An exception occurred.")

        return async_wrapper
    else:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except SystemExit:
                raise
            except KeyboardInterrupt:
                raise SystemExit(1)
            except Exception:
                from prefect.settings import get_current_settings

                if get_current_settings().testing.test_mode:
                    raise
                traceback.print_exc()
                exit_with_error("An exception occurred.")

        return wrapper


def load_json_key_values(
    cli_input: list[str], display_name: str
) -> dict[str, dict[str, Any] | str | int]:
    """Parse a list of "key=value" strings where the value is loaded as JSON."""
    parsed: dict[str, dict[str, Any] | str | int] = {}

    def cast_value(value: str) -> Any:
        try:
            return json.loads(value)
        except ValueError as exc:
            if (
                "Extra data" in str(exc) or "Expecting value" in str(exc)
            ) and '"' not in value:
                return cast_value(f'"{value}"')
            raise exc

    for spec in cli_input:
        try:
            key, _, value = spec.partition("=")
        except ValueError:
            exit_with_error(
                f"Invalid {display_name} option {spec!r}. Expected format 'key=value'."
            )

        try:
            parsed[key] = cast_value(value)
        except ValueError as exc:
            indented_value = textwrap.indent(value, prefix="\t")
            exit_with_error(
                f"Failed to parse JSON for {display_name} {key!r} with value"
                f"\n\n{indented_value}\n\n"
                f"JSON Error: {exc}"
            )

    return parsed
