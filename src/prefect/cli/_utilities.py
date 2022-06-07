"""
Utilities for Prefect CLI commands
"""
import functools
import sys
import traceback
from typing import Any, Sequence, Union

import anyio
import typer
import typer.core
from click.exceptions import ClickException

from prefect.exceptions import MissingProfileError
from prefect.settings import PREFECT_TEST_MODE


def exit_with_error(message, code=1, **kwargs):
    """
    Utility to print a stylized error message and exit with a non-zero code
    """
    from prefect.cli.root import app

    kwargs.setdefault("style", "red")
    app.console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message, **kwargs):
    """
    Utility to print a stylized success message and exit with a zero code
    """
    from prefect.cli.root import app

    kwargs.setdefault("style", "green")
    app.console.print(message, **kwargs)
    raise typer.Exit(0)


def with_cli_exception_handling(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
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


async def open_process_and_stream_output(
    command: Union[str, Sequence[str]],
    task_status: anyio.abc.TaskStatus = None,
    **kwargs: Any,
) -> None:
    """
    Opens a subprocess and streams standard output and error

    Args:
        command: The command to open a subprocess with.
        task_status: Enables this coroutine function to be used with `task_group.start`
            The task will report itself as started once the process is started.
        **kwargs: Additional keyword arguments are passed to `anyio.open_process`.
    """
    # passing a string to open_process is equivalent to shell=True
    # which is generally necessary for Unix-like commands on Windows
    # but otherwise should be avoided
    if isinstance(command, list) and sys.platform == "win32":
        command = " ".join(command)
    process = await anyio.open_process(
        command, stderr=sys.stderr, stdout=sys.stdout, **kwargs
    )
    if task_status:
        task_status.started()

    try:
        await process.wait()
    finally:
        with anyio.CancelScope(shield=True):
            try:
                process.terminate()
            except Exception:
                pass  # Process may already be terminated

            await process.aclose()
