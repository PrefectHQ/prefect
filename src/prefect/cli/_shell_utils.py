"""
Shared utilities for shell command execution.

Extracted from prefect.cli.shell so both typer and cyclopts
command modules can import without pulling in CLI framework deps.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
from typing import IO, Any, Callable, Dict, Optional

from prefect import flow
from prefect.exceptions import FailedRun
from prefect.logging.loggers import get_run_logger


def output_stream(pipe: IO[str], logger_function: Callable[[str], None]) -> None:
    """
    Read from a pipe line by line and log using the provided logging function.

    Args:
        pipe (IO): A file-like object for reading process output.
        logger_function (function): A logging function from the logger.
    """
    with pipe:
        for line in iter(pipe.readline, ""):
            logger_function(line.strip())


def output_collect(pipe: IO[str], container: list[str]) -> None:
    """
    Collects output from a subprocess pipe and stores it in a container list.

    Args:
        pipe: The output pipe of the subprocess, either stdout or stderr.
        container: A list to store the collected output lines.
    """
    for line in iter(pipe.readline, ""):
        container.append(line)


@flow
def run_shell_process(
    command: str,
    log_output: bool = True,
    stream_stdout: bool = False,
    log_stderr: bool = False,
    popen_kwargs: Optional[Dict[str, Any]] = None,
):
    """
    Asynchronously executes the specified shell command and logs its output.

    This function is designed to be used within Prefect flows to run shell commands as part of task execution.
    It handles both the execution of the command and the collection of its output for logging purposes.

    Args:
        command: The shell command to execute.
        log_output: If True, the output of the command (both stdout and stderr) is logged to Prefect.
        stream_stdout: If True, the stdout of the command is streamed to Prefect logs.
        log_stderr: If True, the stderr of the command is logged to Prefect logs.
        popen_kwargs: Additional keyword arguments to pass to the `subprocess.Popen` call.

    """

    logger = get_run_logger() if log_output else logging.getLogger("prefect")

    # Default Popen kwargs that can be overridden
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": True,
        "text": True,
        "bufsize": 1,
        "universal_newlines": True,
    }

    if popen_kwargs:
        kwargs |= popen_kwargs

    # Containers for log batching
    stdout_container, stderr_container = [], []
    with subprocess.Popen(command, **kwargs) as proc:
        # Create threads for collecting stdout and stderr
        if stream_stdout:
            stdout_logger = logger.info
            output = output_stream
        else:
            stdout_logger = stdout_container
            output = output_collect

        stdout_thread = threading.Thread(
            target=output, args=(proc.stdout, stdout_logger)
        )

        stderr_thread = threading.Thread(
            target=output_collect, args=(proc.stderr, stderr_container)
        )

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        proc.wait()
        if stdout_container:
            logger.info("".join(stdout_container).strip())

        if stderr_container and log_stderr:
            logger.error("".join(stderr_container).strip())
            # Suppress traceback
        if proc.returncode != 0:
            logger.error("".join(stderr_container).strip())
            sys.tracebacklimit = 0
            raise FailedRun(f"Command failed with exit code {proc.returncode}")
