"""
Utilities for cyclopts CLI commands.

Mirrors prefect.cli._utilities but uses sys.exit instead of typer.Exit.
"""

import asyncio
import functools
import traceback
from typing import Any, Callable, NoReturn


def exit_with_error(message: str | Exception, code: int = 1, **kwargs: Any) -> NoReturn:
    """Print a stylized error message and exit with a non-zero code."""
    from prefect.cli._cyclopts import console

    kwargs.setdefault("style", "red")
    console.print(message, **kwargs)
    raise SystemExit(code)


def exit_with_success(message: str, **kwargs: Any) -> NoReturn:
    """Print a stylized success message and exit with a zero code."""
    from prefect.cli._cyclopts import console

    kwargs.setdefault("style", "green")
    console.print(message, **kwargs)
    raise SystemExit(0)


def with_cli_exception_handling(fn: Callable[..., Any]) -> Callable[..., Any]:
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


def run_async(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to run an async function synchronously via asyncio.run."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(fn(*args, **kwargs))

    return wrapper
