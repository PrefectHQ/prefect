import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Type, TypeVar
from uuid import UUID

import anyio
import anyio.abc
import sniffio
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field
from typing_extensions import Literal

from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.utilities.compat import ThreadedChildWatcher
from prefect.utilities.logging import get_logger

_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}
FlowRunnerT = TypeVar("FlowRunnerT", bound=Type["FlowRunner"])


class FlowRunner(BaseModel):
    """
    Flow runners are responsible for creating infrastructure for flow runs and starting
    execution.

    This base implementation manages casting to and from the API representation of
    flow runner settings and defines the interface for `submit_flow_run`. It cannot
    be used to run flows.
    """

    typename: str

    def to_settings(self) -> FlowRunnerSettings:
        return FlowRunnerSettings(
            type=self.typename, config=self.dict(exclude={"typename"})
        )

    @classmethod
    def from_settings(cls, settings: FlowRunnerSettings) -> "FlowRunner":
        subcls = lookup_flow_runner(settings.type)
        return subcls(**(settings.config or {}))

    @property
    def logger(self):
        return get_logger(f"flow_runner.{self.typename}")

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        """
        Implementions should:

        - Create flow run infrastructure.
        - Start the flow run within it.
        - Call `task_status.started()` to indicate that submission was successful

        The method can then exit or continue monitor the flow run asynchronously.

        The method _may_ return a boolean indicating successful completion of the run.
        This return value is not intended for general consumption and is primarily
        useful for testing.
        """
        raise NotImplementedError()

    class Config:
        extra = "forbid"


def register_flow_runner(cls: FlowRunnerT) -> FlowRunnerT:
    _FLOW_RUNNERS[cls.__fields__["typename"].default] = cls
    return cls


def lookup_flow_runner(typename: str) -> FlowRunner:
    """Return the flow runner class for the given `typename`"""
    try:
        return _FLOW_RUNNERS[typename]
    except KeyError:
        raise ValueError(f"Unregistered flow runner {typename!r}")


@register_flow_runner
class UniversalFlowRunner(FlowRunner):
    """
    The universal flow runner contains configuration options that can be used by any
    Prefect flow runner implementation.

    This flow runner cannot be used at runtime and should be converted into a subtype.

    Attributes:
        env: Environment variables to provide to the flow run
    """

    typename: Literal["universal"] = "universal"
    env: Dict[str, str] = Field(default_factory=dict)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        raise RuntimeError(
            "The universal flow runner cannot be used to submit flow runs. If a flow "
            "run has a universal flow runner, it should be updated to the default "
            "runner type by the agent or user."
        )


@register_flow_runner
class SubprocessFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a local subprocess.

    Attributes:
        stream_output: Stream output from the subprocess to local standard output
        conda_env: An optional name of an anaconda environment to run the flow in.
        virtual_env: An optional path to a virtualenv environment to run the flow in.

    """

    typename: Literal["subprocess"] = "subprocess"
    stream_output: bool = False
    condaenv: str = None
    virtualenv: Path = None

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:

        if sys.version_info < (3, 8) and sniffio.current_async_library() == "asyncio":
            # Python < 3.8 does not use a `ThreadedChildWatcher` by default which can
            # lead to errors in tests on unix as the previous default `SafeChildWatcher`
            # is not compatible with threaded event loops.
            asyncio.get_event_loop_policy().set_child_watcher(ThreadedChildWatcher())

        # Open a subprocess to execute the flow run
        self.logger.info(f"Opening subprocess for flow run '{flow_run.id}'...")

        command, env = self._generate_command_and_environment(flow_run.id)

        self.logger.debug(f"Using command: {' '.join(command)}")

        process_context = await anyio.open_process(
            command,
            stderr=subprocess.STDOUT,
            env=env,
        )

        # Mark this submission as successful
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
        # Copy the base environment
        env = os.environ.copy()

        # Set up defaults
        command = []
        python_executable = sys.executable

        # Prepare to run in `conda`
        if self.condaenv:
            command = ["conda", "run", "-n", self.condaenv]
            python_executable = "python"

        # Prepare to run in `virtualenv`
        elif self.virtualenv:
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
