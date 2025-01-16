"""
Utility project steps that are useful for managing a project's deployment lifecycle.

Steps within this module can be used within a `build`, `push`, or `pull` deployment action.

Example:
    Use the `run_shell_script` setp to retrieve the short Git commit hash of the current
        repository and use it as a Docker image tag:
    ```yaml
    build:
        - prefect.deployments.steps.run_shell_script:
            id: get-commit-hash
            script: git rev-parse --short HEAD
            stream_output: false
        - prefect_docker.deployments.steps.build_docker_image:
            requires: prefect-docker
            image_name: my-image
            image_tag: "{{ get-commit-hash.stdout }}"
            dockerfile: auto
    ```
"""

import io
import os
import shlex
import string
import subprocess
import sys
from typing import Any, Dict, Optional

from anyio import create_task_group
from anyio.streams.text import TextReceiveStream
from typing_extensions import TypedDict

from prefect.utilities.processutils import (
    get_sys_executable,
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


class RunShellScriptResult(TypedDict):
    """
    The result of a `run_shell_script` step.

    Attributes:
        stdout: The captured standard output of the script.
        stderr: The captured standard error of the script.
    """

    stdout: str
    stderr: str


async def run_shell_script(
    script: str,
    directory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stream_output: bool = True,
    expand_env_vars: bool = False,
) -> RunShellScriptResult:
    """
    Runs one or more shell commands in a subprocess. Returns the standard
    output and standard error of the script.

    Args:
        script: The script to run
        directory: The directory to run the script in. Defaults to the current
            working directory.
        env: A dictionary of environment variables to set for the script
        stream_output: Whether to stream the output of the script to
            stdout/stderr
        expand_env_vars: Whether to expand environment variables in the script
            before running it

    Returns:
        A dictionary with the keys `stdout` and `stderr` containing the output
            of the script

    Examples:
        Retrieve the short Git commit hash of the current repository to use as
            a Docker image tag:
        ```yaml
        build:
            - prefect.deployments.steps.run_shell_script:
                id: get-commit-hash
                script: git rev-parse --short HEAD
                stream_output: false
            - prefect_docker.deployments.steps.build_docker_image:
                requires: prefect-docker
                image_name: my-image
                image_tag: "{{ get-commit-hash.stdout }}"
                dockerfile: auto
        ```

        Run a multi-line shell script:
        ```yaml
        build:
            - prefect.deployments.steps.run_shell_script:
                script: |
                    echo "Hello"
                    echo "World"
        ```

        Run a shell script with environment variables:
        ```yaml
        build:
            - prefect.deployments.steps.run_shell_script:
                script: echo "Hello $NAME"
                env:
                    NAME: World
        ```

        Run a shell script with environment variables expanded
            from the current environment:
        ```yaml
        pull:
            - prefect.deployments.steps.run_shell_script:
                script: |
                    echo "User: $USER"
                    echo "Home Directory: $HOME"
                stream_output: true
                expand_env_vars: true
        ```

        Run a shell script in a specific directory:
        ```yaml
        build:
            - prefect.deployments.steps.run_shell_script:
                script: echo "Hello"
                directory: /path/to/directory
        ```

        Run a script stored in a file:
        ```yaml
        build:
            - prefect.deployments.steps.run_shell_script:
                script: "bash path/to/script.sh"
        ```
    """
    current_env = os.environ.copy()
    current_env.update(env or {})

    commands = script.splitlines()
    stdout_sink = io.StringIO()
    stderr_sink = io.StringIO()

    for command in commands:
        if expand_env_vars:
            # Expand environment variables in command and provided environment
            command = string.Template(command).safe_substitute(current_env)
        split_command = shlex.split(command, posix=sys.platform != "win32")
        if not split_command:
            continue
        async with open_process(
            split_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=directory,
            env=current_env,
        ) as process:
            await _stream_capture_process_output(
                process,
                stdout_sink=stdout_sink,
                stderr_sink=stderr_sink,
                stream_output=stream_output,
            )

            await process.wait()

            if process.returncode != 0:
                raise RuntimeError(
                    f"`run_shell_script` failed with error code {process.returncode}:"
                    f" {stderr_sink.getvalue()}"
                )

    return {
        "stdout": stdout_sink.getvalue().strip(),
        "stderr": stderr_sink.getvalue().strip(),
    }


async def pip_install_requirements(
    directory: Optional[str] = None,
    requirements_file: str = "requirements.txt",
    stream_output: bool = True,
) -> dict[str, Any]:
    """
    Installs dependencies from a requirements.txt file.

    Args:
        requirements_file: The requirements.txt to use for installation.
        directory: The directory the requirements.txt file is in. Defaults to
            the current working directory.
        stream_output: Whether to stream the output from pip install should be
            streamed to the console

    Returns:
        A dictionary with the keys `stdout` and `stderr` containing the output
            the `pip install` command

    Raises:
        subprocess.CalledProcessError: if the pip install command fails for any reason

    Example:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                id: clone-step
                repository: https://github.com/org/repo.git
            - prefect.deployments.steps.pip_install_requirements:
                directory: {{ clone-step.directory }}
                requirements_file: requirements.txt
                stream_output: False
        ```
    """
    stdout_sink = io.StringIO()
    stderr_sink = io.StringIO()

    async with open_process(
        [get_sys_executable(), "-m", "pip", "install", "-r", requirements_file],
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

        if process.returncode != 0:
            raise RuntimeError(
                f"pip_install_requirements failed with error code {process.returncode}:"
                f" {stderr_sink.getvalue()}"
            )

    return {
        "stdout": stdout_sink.getvalue().strip(),
        "stderr": stderr_sink.getvalue().strip(),
    }
