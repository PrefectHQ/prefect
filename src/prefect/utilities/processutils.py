import os
import signal
import subprocess
import sys
from contextlib import asynccontextmanager
from io import TextIOBase
from typing import Callable, List, Optional, TextIO, Tuple, Union

import anyio
import anyio.abc
import psutil
from anyio.streams.text import TextReceiveStream, TextSendStream

TextSink = Union[anyio.AsyncFile, TextIO, TextSendStream]


def parse_command(command: List[str]) -> Union[List[str], str]:
    # Passing a string to open_process is equivalent to shell=True which is
    # generally necessary for Unix-like commands on Windows but otherwise should
    # be avoided
    if sys.platform == "win32":
        command = " ".join(command)

    return command


@asynccontextmanager
async def open_process(command: List[str], **kwargs):
    """
    Like `anyio.open_process` but with:
    - Support for Windows command joining
    - Termination of the process on exception during yield
    - Forced cleanup of process resources during cancellation
    """
    command = parse_command(command)

    process = await anyio.open_process(command, **kwargs)

    try:
        async with process:
            yield process
    finally:
        try:
            process.terminate()
        except ProcessLookupError:
            # Occurs if the process is already terminated
            pass

        # Ensure the process resource is closed. If not shielded from cancellation,
        # this resource an be left open and the subprocess output can be appear after
        # the parent process has exited.
        with anyio.CancelScope(shield=True):
            await process.aclose()


async def run_process(
    command: List[str],
    stream_output: Union[bool, Tuple[Optional[TextSink], Optional[TextSink]]] = False,
    task_status: Optional[anyio.abc.TaskStatus] = None,
    **kwargs,
):
    """
    Like `anyio.run_process` but with:

    - Use of our `open_process` utility to ensure resources are cleaned up
    - Simple `stream_output` support to connect the subprocess to the parent stdout/err
    - Support for submission with `TaskGroup.start` marking as 'started' after the
        process has been created. When used, the PID is returned to the task status.

    """
    if stream_output is True:
        stream_output = (sys.stdout, sys.stderr)

    async with open_process(
        command,
        stdout=subprocess.PIPE if stream_output else subprocess.DEVNULL,
        stderr=subprocess.PIPE if stream_output else subprocess.DEVNULL,
        **kwargs,
    ) as process:

        if task_status is not None:
            task_status.started(process.pid)

        if stream_output:
            await consume_process_output(
                process, stdout_sink=stream_output[0], stderr_sink=stream_output[1]
            )

        await process.wait()

    return process


def start_process(
    command: List[str], pid_file: Union[str, bytes, os.PathLike, None] = None, **kwargs
):
    """
    Start an external command in a detached process.

    Similar to `run_process` but without waiting for the process to finish.
    This allows the process to run in the background.

    Args:
        command: An iterable of strings containing the executable name or path and its arguments.
        pid_file: File name to store the process ID (PID). Only needed if the command does not have its own process manager.

    Returns:
        A process object.

    """
    command = parse_command(command)
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.DETACHED_PROCESS)

    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs
    )

    if pid_file is not None:
        # Some commands have their own process manager. That's nice.
        # I will control in a basic way those that do not have this feature.
        try:
            with open(pid_file, "w") as f:
                f.write(str(process.pid))
        except OSError as e:
            process.terminate()
            process.wait()
            raise OSError(f"Unable to write PID file: {e}\n")

    return process


def stop_process(pid_file: Union[str, bytes, os.PathLike]):
    """
    Stop an external command in a subprocess and delete its PID file.

    Args:
        pid_file: File name to read the process ID (PID).
    """
    try:
        with open(pid_file, "r") as f:
            pid = f.read()
    except OSError as e:
        raise OSError(f"Unable to read PID file: {e}\n")

    try:
        process = psutil.Process(int(pid))

        # Finish the process, wait a while and if it's still alive, kill it.
        process.terminate()
        try:
            process.wait(3)
        except psutil.TimeoutExpired:
            process.kill()

    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid PID file: {e}\n")
    except psutil.NoSuchProcess as e:
        raise ProcessLookupError(e)
    finally:
        if os.path.exists(pid_file):
            os.remove(pid_file)


async def consume_process_output(
    process,
    stdout_sink: Optional[TextSink] = None,
    stderr_sink: Optional[TextSink] = None,
):
    async with anyio.create_task_group() as tg:
        tg.start_soon(
            stream_text,
            TextReceiveStream(process.stdout),
            stdout_sink,
        )
        tg.start_soon(
            stream_text,
            TextReceiveStream(process.stderr),
            stderr_sink,
        )


async def stream_text(source: TextReceiveStream, sink: Optional[TextSink]):
    if isinstance(sink, TextIOBase):
        # Convert the blocking sink to an async-compatible object
        sink = anyio.wrap_file(sink)

    async for item in source:
        if isinstance(sink, TextSendStream):
            await sink.send(item)
        elif isinstance(sink, anyio.AsyncFile):
            await sink.write(item)
            await sink.flush()
        elif sink is None:
            pass  # Consume the item but perform no action
        else:
            raise TypeError(f"Unsupported sink type {type(sink).__name__}")


def kill_on_interrupt(pid: int, process_name: str, print_fn: Callable):
    """Kill a process with the given `pid` when a SIGNINT is received."""

    # In a non-windows enviornment first interrupt with send a SIGTERM, then
    # subsequent interrupts will send SIGKILL. In Windows we use
    # CTRL_BREAK_EVENT as SIGTERM is useless:
    # https://bugs.python.org/issue26350
    if sys.platform == "win32":

        def stop_process(*args):
            print_fn(f"\nStopping {process_name}...")
            os.kill(pid, signal.CTRL_BREAK_EVENT)

    else:

        def stop_process(*args):
            print_fn(f"\nStopping {process_name}...")
            os.kill(pid, signal.SIGTERM)
            signal.signal(signal.SIGINT, kill_process)

        def kill_process(*args):
            print_fn(f"\nKilling {process_name}...")
            os.kill(pid, signal.SIGKILL)

    signal.signal(signal.SIGINT, stop_process)
