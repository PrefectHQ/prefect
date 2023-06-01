"""
Utility project steps that are useful for managing a project's deployment lifecycle.
"""
from anyio import create_task_group
from anyio.streams.text import TextReceiveStream
import io
import os
import shlex
import subprocess
import sys
from typing import Optional, Dict

from prefect.utilities.processutils import (
    open_process,
    stream_text,
)


async def _stream_capture_process_output(
    process,
    stdout_sink: io.StringIO,
    stderr_sink: io.StringIO,
    stream_output: bool = True,
):
    stdout_sinks = [stdout_sink, sys.stdout] if stream_output else [stdout_sink]
    stderr_sinks = [stderr_sink, sys.stderr] if stream_output else [stderr_sink]
    async with create_task_group() as tg:
        tg.start_soon(
            stream_text,
            TextReceiveStream(process.stdout),
            *stdout_sinks,
        )
        tg.start_soon(
            stream_text,
            TextReceiveStream(process.stderr),
            *stderr_sinks,
        )


async def run_shell_script(
    script: str,
    directory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stream_output: bool = True,
):
    """
    Runs a shell script.

    Args:
        script: The script to run
        directory: The directory to run the script in. Defaults to the current working directory.
        env: A dictionary of environment variables to set for the script
        stream_output: Whether to stream the output of the script to stdout/stderr
    """
    current_env = os.environ.copy()
    current_env.update(env or {})

    commands = script.splitlines()
    stdout_sink = io.StringIO()
    stderr_sink = io.StringIO()

    for command in commands:
        async with open_process(
            shlex.split(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=directory,
        ) as process:
            await _stream_capture_process_output(
                process,
                stdout_sink=stdout_sink,
                stderr_sink=stderr_sink,
                stream_output=stream_output,
            )

            await process.wait()

    return dict(
        stdout=stdout_sink.getvalue().strip(), stderr=stderr_sink.getvalue().strip()
    )
