"""
Utility project steps that are useful for managing a project's deployment lifecycle.
"""
import os
import shlex
from typing import Optional, Dict

from prefect.utilities.processutils import run_process


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
    for command in commands:
        await run_process(
            shlex.split(command),
            cwd=directory,
            env=current_env,
            stream_output=stream_output,
        )
