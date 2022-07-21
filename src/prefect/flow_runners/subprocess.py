import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Union
from uuid import UUID

import sniffio
from anyio.abc import TaskStatus
from pydantic import root_validator, validator
from typing_extensions import Literal

from prefect.flow_runners.base import (
    UniversalFlowRunner,
    base_flow_run_environment,
    register_flow_runner,
)
from prefect.orion.schemas.core import FlowRun
from prefect.settings import SETTING_VARIABLES
from prefect.utilities.processutils import run_process


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

        process = await run_process(
            command, stream_output=self.stream_output, task_status=task_status, env=env
        )

        if process.returncode:
            self.logger.error(
                f"Subprocess for flow run '{flow_run.id}' exited with bad code: "
                f"{process.returncode}"
            )
        else:
            self.logger.info(f"Subprocess for flow run '{flow_run.id}' exited cleanly.")

        return not process.returncode

    async def preview(self, flow_run: FlowRun) -> str:
        """
        Produce a textual preview of the given FlowRun.

        For the SubprocessFlowRunner, this produces a shell command with the
        environment variables and command necessary to run the job.

        Args:
            flow_run: The flow run

        Returns:
            A shell command string
        """
        command, environment = self._generate_command_and_environment(
            flow_run.id, include_os_environ=False
        )
        return " \\\n".join(
            [f"{key}={value}" for key, value in environment.items()]
            + [" ".join(command)]
        )

    def _generate_command_and_environment(
        self, flow_run_id: UUID, include_os_environ=True
    ) -> Tuple[Sequence[str], Dict[str, str]]:
        # Include the base environment and current process environment
        env = base_flow_run_environment()
        if include_os_environ:
            env.update(
                {
                    key: value
                    for key, value in os.environ.items()
                    # Allow override of base environment keys unless they are settings
                    # Otherwise, settings in a context could be ignored
                    if key not in env or key not in SETTING_VARIABLES
                }
            )

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
