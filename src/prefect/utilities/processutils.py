import asyncio
import os
import signal
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import TextIOBase
from typing import (
    IO,
    Any,
    Callable,
    List,
    Mapping,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Union,
)

import anyio
import anyio.abc
from anyio.streams.text import TextReceiveStream, TextSendStream

TextSink = Union[anyio.AsyncFile, TextIO, TextSendStream]


if sys.platform == "win32":
    from ctypes import WINFUNCTYPE, c_int, c_uint, windll

    _windows_process_group_pids = set()

    @WINFUNCTYPE(c_int, c_uint)
    def _win32_ctrl_handler(dwCtrlType):
        """
        A callback function for handling CTRL events cleanly on Windows. When called,
        this function will terminate all running win32 subprocesses the current
        process started in new process groups.
        """
        for pid in _windows_process_group_pids:
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            except OSError:
                # process is already terminated
                pass

        # returning 0 lets the next handler in the chain handle the signal
        return 0

    # anyio process wrapper classes
    @dataclass(eq=False)
    class StreamReaderWrapper(anyio.abc.ByteReceiveStream):
        _stream: asyncio.StreamReader

        async def receive(self, max_bytes: int = 65536) -> bytes:
            data = await self._stream.read(max_bytes)
            if data:
                return data
            else:
                raise anyio.EndOfStream

        async def aclose(self) -> None:
            self._stream.feed_eof()

    @dataclass(eq=False)
    class StreamWriterWrapper(anyio.abc.ByteSendStream):
        _stream: asyncio.StreamWriter

        async def send(self, item: bytes) -> None:
            self._stream.write(item)
            await self._stream.drain()

        async def aclose(self) -> None:
            self._stream.close()

    @dataclass(eq=False)
    class Process(anyio.abc.Process):
        _process: asyncio.subprocess.Process
        _stdin: Union[StreamWriterWrapper, None]
        _stdout: Union[StreamReaderWrapper, None]
        _stderr: Union[StreamReaderWrapper, None]

        async def aclose(self) -> None:
            if self._stdin:
                await self._stdin.aclose()
            if self._stdout:
                await self._stdout.aclose()
            if self._stderr:
                await self._stderr.aclose()

            await self.wait()

        async def wait(self) -> int:
            return await self._process.wait()

        def terminate(self) -> None:
            self._process.terminate()

        def kill(self) -> None:
            self._process.kill()

        def send_signal(self, signal: int) -> None:
            self._process.send_signal(signal)

        @property
        def pid(self) -> int:
            return self._process.pid

        @property
        def returncode(self) -> Union[int, None]:
            return self._process.returncode

        @property
        def stdin(self) -> Union[anyio.abc.ByteSendStream, None]:
            return self._stdin

        @property
        def stdout(self) -> Union[anyio.abc.ByteReceiveStream, None]:
            return self._stdout

        @property
        def stderr(self) -> Union[anyio.abc.ByteReceiveStream, None]:
            return self._stderr

    async def _open_anyio_process(
        command: Union[str, bytes, Sequence[Union[str, bytes]]],
        *,
        stdin: Union[int, IO[Any], None] = None,
        stdout: Union[int, IO[Any], None] = None,
        stderr: Union[int, IO[Any], None] = None,
        cwd: Union[str, bytes, os.PathLike, None] = None,
        env: Union[Mapping[str, str], None] = None,
        start_new_session: bool = False,
        **kwargs,
    ):
        """
        Open a subprocess and return a `Process` object.

        Args:
            command: The command to run
            kwargs: Additional arguments to pass to `asyncio.create_subprocess_exec`

        Returns:
            A `Process` object
        """
        # call either asyncio.create_subprocess_exec or asyncio.create_subprocess_shell
        # depending on whether the command is a list or a string
        if isinstance(command, list):
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                cwd=cwd,
                env=env,
                start_new_session=start_new_session,
                **kwargs,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                cwd=cwd,
                env=env,
                start_new_session=start_new_session,
                **kwargs,
            )

        return Process(
            process,
            StreamWriterWrapper(process.stdin) if process.stdin else None,
            StreamReaderWrapper(process.stdout) if process.stdout else None,
            StreamReaderWrapper(process.stderr) if process.stderr else None,
        )


@asynccontextmanager
async def open_process(command: List[str], **kwargs):
    """
    Like `anyio.open_process` but with:
    - Support for Windows command joining
    - Termination of the process on exception during yield
    - Forced cleanup of process resources during cancellation
    """
    # Passing a string to open_process is equivalent to shell=True which is
    # generally necessary for Unix-like commands on Windows but otherwise should
    # be avoided
    if not isinstance(command, list):
        raise TypeError(
            "The command passed to open process must be a list. You passed the command"
            f"'{command}', which is type '{type(command)}'."
        )

    if sys.platform == "win32":
        command = " ".join(command)
        process = await _open_anyio_process(command, **kwargs)
    else:
        process = await anyio.open_process(command, **kwargs)

    # if there's a creationflags kwarg and it contains CREATE_NEW_PROCESS_GROUP,
    # use SetConsoleCtrlHandler to handle CTRL-C
    win32_process_group = False
    if (
        sys.platform == "win32"
        and "creationflags" in kwargs
        and kwargs["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP
    ):
        win32_process_group = True
        _windows_process_group_pids.add(process.pid)
        # Add a handler for CTRL-C. Re-adding the handler is safe as Windows
        # will not add a duplicate handler if _win32_ctrl_handler is
        # already registered.
        windll.kernel32.SetConsoleCtrlHandler(_win32_ctrl_handler, 1)

    try:
        async with process:
            yield process
    finally:
        try:
            process.terminate()
            if win32_process_group:
                _windows_process_group_pids.remove(process.pid)

        except OSError:
            # Occurs if the process is already terminated
            pass

        # Ensure the process resource is closed. If not shielded from cancellation,
        # this resource can be left open and the subprocess output can appear after
        # the parent process has exited.
        with anyio.CancelScope(shield=True):
            await process.aclose()


async def run_process(
    command: List[str],
    stream_output: Union[bool, Tuple[Optional[TextSink], Optional[TextSink]]] = False,
    task_status: Optional[anyio.abc.TaskStatus] = None,
    task_status_handler: Optional[Callable[[anyio.abc.Process], Any]] = None,
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
            if not task_status_handler:
                task_status_handler = lambda process: process.pid

            task_status.started(task_status_handler(process))

        if stream_output:
            await consume_process_output(
                process, stdout_sink=stream_output[0], stderr_sink=stream_output[1]
            )

        await process.wait()

    return process


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
