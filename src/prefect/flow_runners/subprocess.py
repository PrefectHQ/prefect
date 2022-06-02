import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Union
from uuid import UUID

import anyio
import anyio.abc
import sniffio
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import root_validator, validator
from typing_extensions import Literal

from prefect.orion.schemas.core import FlowRun

from .base import UniversalFlowRunner, base_flow_run_environment, register_flow_runner


@register_flow_runner
class SubprocessFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a local subprocess.

    Attributes:
        stream_output: Stream output from the subprocess to local standard output
        condaenv: An optional name of an anaconda environment to run the flow in.
            A path can be provided instead, similar to `conda --prefix ...`.
        virtualenv: An optional path to a virtualenv environment to run the flow in.
            This also supports the python builtin `venv` environments.

    """

    typename: Literal["subprocess"] = "subprocess"
    stream_output: bool = True
    condaenv: Union[str, Path] = None
    virtualenv: Path = None

    @validator("condaenv")
    def coerce_pathlike_string_to_path(cls, value):
        if (
            not isinstance(value, Path)
            and value is not None
            and (value.startswith(os.sep) or value.startswith("~"))
        ):
            value = Path(value)
        return value

    @root_validator
    def ensure_only_one_env_was_given(cls, values):
        if values.get("condaenv") and values.get("virtualenv"):
            raise ValueError(
                "Received incompatible settings. You cannot provide both a conda and "
                "virtualenv to use."
            )
        return values

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus = None,
    ) -> Optional[bool]:

        if (
            sys.version_info < (3, 8)
            and sniffio.current_async_library() == "asyncio"
            and sys.platform != "win32"
        ):
            from prefect.utilities.compat import ThreadedChildWatcher

            # Python < 3.8 does not use a `ThreadedChildWatcher` by default which can
            # lead to errors in tests on unix as the previous default `SafeChildWatcher`
            # is not compatible with threaded event loops.
            asyncio.get_event_loop_policy().set_child_watcher(ThreadedChildWatcher())

        # Open a subprocess to execute the flow run
        self.logger.info(f"Opening subprocess for flow run '{flow_run.id}'...")

        command, env = self._generate_command_and_environment(flow_run.id)

        self.logger.debug(f"Using command: {' '.join(command)}")

        # passing a string to open_process is equivalent to shell=True
        # which is generally necessary for Unix-like commands on Windows
        # but otherwise should be avoided
        if isinstance(command, list) and sys.platform == "win32":
            command = " ".join(command)
        process_context = await anyio.open_process(
            command,
            stderr=subprocess.STDOUT,
            env=env,
        )

        # Mark this submission as successful
        if task_status:
            task_status.started()

        # Wait for the process to exit
        # - We must the output stream so the buffer does not fill
        # - We can log the success/failure of the process
        async with process_context as process:
            async for text in TextReceiveStream(process.stdout):
                if self.stream_output:
                    print(text, end="")  # Output is already new-line terminated

        if process.returncode:
            self.logger.error(
                f"Subprocess for flow run '{flow_run.id}' exited with bad code: "
                f"{process.returncode}"
            )
        else:
            self.logger.info(f"Subprocess for flow run '{flow_run.id}' exited cleanly.")

        return not process.returncode

    def _generate_command_and_environment(
        self, flow_run_id: UUID
    ) -> Tuple[Sequence[str], Dict[str, str]]:
        # Include the base environment and current process environment
        env = {**base_flow_run_environment(), **os.environ}

        # Set up defaults
        command = []
        python_executable = sys.executable

        if self.condaenv:
            command += ["conda", "run"]
            if isinstance(self.condaenv, Path):
                command += ["--prefix", str(self.condaenv.expanduser().resolve())]
            else:
                command += ["--name", self.condaenv]

            python_executable = "python"

        elif self.virtualenv:
            # This reproduces the relevant behavior of virtualenv's activation script
            # https://github.com/pypa/virtualenv/blob/main/src/virtualenv/activation/bash/activate.sh

            virtualenv_path = self.virtualenv.expanduser().resolve()
            python_executable = str(virtualenv_path / "bin" / "python")
            # Update the path to include the bin
            env["PATH"] = str(virtualenv_path / "bin") + os.pathsep + env["PATH"]
            env.pop("PYTHONHOME", None)
            env["VIRTUAL_ENV"] = str(virtualenv_path)

        # Add `prefect.engine` call
        command += [
            python_executable,
            "-m",
            "prefect.engine",
            flow_run_id.hex,
        ]

        # Override with any user-provided variables
        env.update(self.env)

        return command, env
