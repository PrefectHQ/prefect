import subprocess
import sys
from contextlib import asynccontextmanager
from typing import List, Optional

import anyio
import anyio.abc
from anyio.streams.text import TextReceiveStream, TextSendStream


@asynccontextmanager
async def open_process(command: List[str], **kwargs):
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
    stream_output: bool = False,
    task_status: Optional[anyio.abc.TaskStatus] = None,
    **kwargs
):

    async with open_process(
        command,
        stdout=sys.stdout if stream_output else subprocess.DEVNULL,
        stderr=sys.stderr if stream_output else subprocess.DEVNULL,
        **kwargs
    ) as process:

        if task_status is not None:
            task_status.started()

        await process.wait()

    return process


async def consume_process_output(process, stream_output: bool = False):
    async with anyio.create_task_group() as tg:
        tg.start_soon(
            stream_text,
            TextReceiveStream(process.stdout),
            TextSendStream(sys.stdout) if stream_output else None,
        )
        tg.start_soon(
            stream_text,
            TextReceiveStream(process.stderr),
            TextSendStream(sys.stderr) if stream_output else None,
        )


async def stream_text(
    from_stream: TextReceiveStream, to_stream: Optional[TextSendStream]
):
    async for item in from_stream:
        if to_stream is not None:
            await to_stream.send(item)
