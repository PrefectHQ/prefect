import asyncio
import os
import signal
import subprocess
import sys
import threading
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from types import FrameType
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    Callable,
    Optional,
    TextIO,
    Union,
    cast,
    overload,
)

import anyio
import anyio.abc
from anyio.streams.text import TextReceiveStream, TextSendStream
from typing_extensions import TypeAlias, TypeVar

if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath

TextSink: TypeAlias = Union[anyio.AsyncFile[AnyStr], TextIO, TextSendStream]
PrintFn: TypeAlias = Callable[[str], object]
T = TypeVar("T", infer_variance=True)

if sys.platform == "win32":
    from ctypes import WINFUNCTYPE, c_int, c_uint, windll

    _windows_process_group_pids = set()

    @WINFUNCTYPE(c_int, c_uint)
    def _win32_ctrl_handler(dwCtrlType: object) -> int:
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
        command: Union[str, bytes, list["StrOrBytesPath"]],
        *,
        stdin: Union[int, IO[Any], None] = None,
        stdout: Union[int, IO[Any], None] = None,
        stderr: Union[int, IO[Any], None] = None,
        cwd: Optional["StrOrBytesPath"] = None,
        env: Optional[Mapping[str, str]] = None,
        start_new_session: bool = False,
        **kwargs: Any,
    ) -> Process:
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
async def open_process(
    command: list[str], **kwargs: Any
) -> AsyncGenerator[anyio.abc.Process, Any]:
    """
    Like `anyio.open_process` but with:
    - Support for Windows command joining
    - Termination of the process on exception during yield
    - Forced cleanup of process resources during cancellation
    """
    # Passing a string to open_process is equivalent to shell=True which is
    # generally necessary for Unix-like commands on Windows but otherwise should
    # be avoided
    if not TYPE_CHECKING:
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
            if sys.platform == "win32" and win32_process_group:
                _windows_process_group_pids.remove(process.pid)

        except OSError:
            # Occurs if the process is already terminated
            pass

        # Ensure the process resource is closed. If not shielded from cancellation,
        # this resource can be left open and the subprocess output can appear after
        # the parent process has exited.
        with anyio.CancelScope(shield=True):
            await process.aclose()


@overload
async def run_process(
    command: list[str],
    *,
    stream_output: Union[
        bool, tuple[Optional[TextSink[str]], Optional[TextSink[str]]]
    ] = ...,
    task_status: anyio.abc.TaskStatus[T] = ...,
    task_status_handler: Callable[[anyio.abc.Process], T] = ...,
    **kwargs: Any,
) -> anyio.abc.Process: ...


@overload
async def run_process(
    command: list[str],
    *,
    stream_output: Union[
        bool, tuple[Optional[TextSink[str]], Optional[TextSink[str]]]
    ] = ...,
    task_status: Optional[anyio.abc.TaskStatus[int]] = ...,
    task_status_handler: None = None,
    **kwargs: Any,
) -> anyio.abc.Process: ...


@overload
async def run_process(
    command: list[str],
    *,
    stream_output: Union[
        bool, tuple[Optional[TextSink[str]], Optional[TextSink[str]]]
    ] = False,
    task_status: Optional[anyio.abc.TaskStatus[T]] = None,
    task_status_handler: Optional[Callable[[anyio.abc.Process], T]] = None,
    **kwargs: Any,
) -> anyio.abc.Process: ...


async def run_process(
    command: list[str],
    *,
    stream_output: Union[
        bool, tuple[Optional[TextSink[str]], Optional[TextSink[str]]]
    ] = False,
    task_status: Optional[anyio.abc.TaskStatus[T]] = None,
    task_status_handler: Optional[Callable[[anyio.abc.Process], T]] = None,
    **kwargs: Any,
) -> anyio.abc.Process:
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
            value: T = cast(T, process.pid)
            if task_status_handler:
                value = task_status_handler(process)
            task_status.started(value)

        if stream_output:
            await consume_process_output(
                process, stdout_sink=stream_output[0], stderr_sink=stream_output[1]
            )

        await process.wait()

    return process


async def consume_process_output(
    process: anyio.abc.Process,
    stdout_sink: Optional[TextSink[str]] = None,
    stderr_sink: Optional[TextSink[str]] = None,
) -> None:
    async with anyio.create_task_group() as tg:
        if process.stdout is not None:
            tg.start_soon(
                stream_text,
                TextReceiveStream(process.stdout),
                stdout_sink,
            )
        if process.stderr is not None:
            tg.start_soon(
                stream_text,
                TextReceiveStream(process.stderr),
                stderr_sink,
            )


async def stream_text(
    source: TextReceiveStream, *sinks: Optional[TextSink[str]]
) -> None:
    wrapped_sinks = [
        (
            anyio.wrap_file(cast(IO[str], sink))
            if hasattr(sink, "write") and hasattr(sink, "flush")
            else sink
        )
        for sink in sinks
        if sink is not None
    ]
    async for item in source:
        for sink in wrapped_sinks:
            if isinstance(sink, TextSendStream):
                await sink.send(item)
            elif isinstance(sink, anyio.AsyncFile):
                await sink.write(item)
                await sink.flush()


def _register_signal(
    signum: int,
    handler: Optional[
        Union[Callable[[int, Optional[FrameType]], Any], int, signal.Handlers]
    ],
) -> None:
    if threading.current_thread() is threading.main_thread():
        signal.signal(signum, handler)


def forward_signal_handler(
    pid: int, signum: int, *signums: int, process_name: str, print_fn: PrintFn
) -> None:
    """Forward subsequent signum events (e.g. interrupts) to respective signums."""
    current_signal, future_signals = signums[0], signums[1:]

    # avoid RecursionError when setting up a direct signal forward to the same signal for the main pid
    original_handler = None
    avoid_infinite_recursion = signum == current_signal and pid == os.getpid()
    if avoid_infinite_recursion:
        # store the vanilla handler so it can be temporarily restored below
        original_handler = signal.getsignal(current_signal)

    def handler(*arg: Any) -> None:
        print_fn(
            f"Received {getattr(signum, 'name', signum)}. "
            f"Sending {getattr(current_signal, 'name', current_signal)} to"
            f" {process_name} (PID {pid})..."
        )
        if avoid_infinite_recursion:
            signal.signal(current_signal, original_handler)
        os.kill(pid, current_signal)
        if future_signals:
            forward_signal_handler(
                pid,
                signum,
                *future_signals,
                process_name=process_name,
                print_fn=print_fn,
            )

    # register current and future signal handlers
    _register_signal(signum, handler)


def setup_signal_handlers_server(
    pid: int, process_name: str, print_fn: PrintFn
) -> None:
    """Handle interrupts of the server gracefully."""
    setup_handler = partial(
        forward_signal_handler, pid, process_name=process_name, print_fn=print_fn
    )
    # when server receives a signal, it needs to be propagated to the uvicorn subprocess
    if sys.platform == "win32":
        # on Windows, use CTRL_BREAK_EVENT as SIGTERM is useless:
        # https://bugs.python.org/issue26350
        setup_handler(signal.SIGINT, signal.CTRL_BREAK_EVENT)
    else:
        # first interrupt: SIGTERM, second interrupt: SIGKILL
        setup_handler(signal.SIGINT, signal.SIGTERM, signal.SIGKILL)
        # forward first SIGTERM directly, send SIGKILL on subsequent SIGTERM
        setup_handler(signal.SIGTERM, signal.SIGTERM, signal.SIGKILL)


def setup_signal_handlers_agent(pid: int, process_name: str, print_fn: PrintFn) -> None:
    """Handle interrupts of the agent gracefully."""
    setup_handler = partial(
        forward_signal_handler, pid, process_name=process_name, print_fn=print_fn
    )
    # when agent receives SIGINT, it stops dequeueing new FlowRuns, and runs until the subprocesses finish
    # the signal is not forwarded to subprocesses, so they can continue to run and hopefully still complete
    if sys.platform == "win32":
        # on Windows, use CTRL_BREAK_EVENT as SIGTERM is useless:
        # https://bugs.python.org/issue26350
        setup_handler(signal.SIGINT, signal.CTRL_BREAK_EVENT)
    else:
        # forward first SIGINT directly, send SIGKILL on subsequent interrupt
        setup_handler(signal.SIGINT, signal.SIGINT, signal.SIGKILL)
        # first SIGTERM: send SIGINT, send SIGKILL on subsequent SIGTERM
        setup_handler(signal.SIGTERM, signal.SIGINT, signal.SIGKILL)


def setup_signal_handlers_worker(
    pid: int, process_name: str, print_fn: PrintFn
) -> None:
    """Handle interrupts of workers gracefully."""
    setup_handler = partial(
        forward_signal_handler, pid, process_name=process_name, print_fn=print_fn
    )
    # when agent receives SIGINT, it stops dequeueing new FlowRuns, and runs until the subprocesses finish
    # the signal is not forwarded to subprocesses, so they can continue to run and hopefully still complete
    if sys.platform == "win32":
        # on Windows, use CTRL_BREAK_EVENT as SIGTERM is useless:
        # https://bugs.python.org/issue26350
        setup_handler(signal.SIGINT, signal.CTRL_BREAK_EVENT)
    else:
        # forward first SIGINT directly, send SIGKILL on subsequent interrupt
        setup_handler(signal.SIGINT, signal.SIGINT, signal.SIGKILL)
        # first SIGTERM: send SIGINT, send SIGKILL on subsequent SIGTERM
        setup_handler(signal.SIGTERM, signal.SIGINT, signal.SIGKILL)


def get_sys_executable() -> str:
    # python executable needs to be quotable on windows
    if os.name == "nt":
        executable_path = f'"{sys.executable}"'
    else:
        executable_path = sys.executable

    return executable_path
