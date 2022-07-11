import subprocess
import sys
from contextlib import asynccontextmanager
from io import TextIOBase
from typing import List, Optional, TextIO, Tuple, Union

import anyio
import anyio.abc
from anyio.streams.text import TextReceiveStream, TextSendStream

TextSink = Union[TextIO, TextSendStream]


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
    if sys.platform == "win32":
        command = " ".join(command)

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
    **kwargs
):
    """
    Like `anyio.run_process` but with:

    - Use of our `open_process` utility to ensure resources are cleaned up
    - Simple `stream_output` support to connect the subprocess to the parent stdout/err
    - Support for submission with `TaskGroup.start` marking as 'started' after the
        process has been created.

    """
    if stream_output is True:
        stream_output = (sys.stdout, sys.stderr)

    async with open_process(
        command,
        stdout=subprocess.PIPE if stream_output else subprocess.DEVNULL,
        stderr=subprocess.PIPE if stream_output else subprocess.DEVNULL,
        **kwargs
    ) as process:

        if task_status is not None:
            task_status.started()

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
    async for item in source:
        if isinstance(sink, TextSendStream):
            await sink.send(item)
        elif isinstance(sink, TextIOBase):
            sink.write(item)
            sink.flush()
