"""
Utilities for Prefect CLI commands
"""

import functools
import traceback
from typing import Any, Callable, NoReturn, TypeVar, Union

import typer
from click.exceptions import ClickException

from prefect.exceptions import MissingProfileError
from prefect.settings import PREFECT_TEST_MODE

T = TypeVar("T")


def exit_with_error(
    message: Union[str, Exception], code: int = 1, **kwargs: Any
) -> NoReturn:
    """
    Utility to print a stylized error message and exit with a non-zero code
    """
    from prefect.cli.root import app

    kwargs.setdefault("style", "red")
    app.console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message: str, **kwargs: Any) -> NoReturn:
    """
    Utility to print a stylized success message and exit with a zero code
    """
    from prefect.cli.root import app

    kwargs.setdefault("style", "green")
    app.console.print(message, **kwargs)
    raise typer.Exit(0)


def with_cli_exception_handling(fn: Callable[..., T]) -> Callable[..., T]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return fn(*args, **kwargs)
        except (typer.Exit, typer.Abort, ClickException):
            raise  # Do not capture click or typer exceptions
        except MissingProfileError as exc:
            exit_with_error(exc)
        except Exception:
            if PREFECT_TEST_MODE.value():
                raise  # Reraise exceptions during test mode
            traceback.print_exc()
            exit_with_error("An exception occurred.")

    return wrapper
