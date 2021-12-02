import subprocess
from typing import Dict, TypeVar, Literal, Type

import anyio
import anyio.abc
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field

from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.utilities.logging import get_logger


_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}
FlowRunnerT = TypeVar("FlowRunnerT", bound=Type["FlowRunner"])


# TODO: Sort out logging
logger = get_logger("flow_runner")


class FlowRunner(BaseModel):
    """
    Flow runners are responsible for creating infrastructure for flow runs and starting
    execution.

    Attributes:
        env: Environment variables to provide to the flow run
    """

    typename: Literal["universal"] = "universal"
    env: Dict[str, str] = Field(default_factory=dict)

    def to_settings(self):
        """
        Convert this instance to a `FlowRunnerSettings` instance for storage in the
        backend.
        """
        return FlowRunnerSettings(typename=self.typename, config=self.dict())

    @classmethod
    def from_settings(cls, settings: FlowRunnerSettings) -> "FlowRunner":
        subcls = lookup_flow_runner(settings.typename)
        return subcls(**settings.config)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> None:
        """
        Implementions should:

        - Create flow run infrastructure.
        - Start the flow run within it.
        - Call `task_status.started()` to indicate that submission was successful

        The method can then exit or continue monitor the flow run asynchronously.
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
class SubprocessFlowRunner(FlowRunner):
    """
    Executes flow runs in a local subprocess
    """

    typename: Literal["subprocess"] = "subprocess"
    condaenv: str = Field(
        None,
        description="An optional name of an anaconda environment to run the flow in. ",
    )
    virtualenv: str = Field(
        None,
        description="An optional path to a virtualenv environment to run the flow in.",
    )

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> None:

        # Open a subprocess to execute the flow run
        logger.info(f"Opening subprocess for flow run '{flow_run.id}'...")
        process_context = await anyio.open_process(
            ["python", "-m", "prefect.engine", flow_run.id.hex],
            stderr=subprocess.STDOUT,
        )

        # Mark this submission as successful
        task_status.started()

        # Wait for the process to exit
        # - We must the output stream so the buffer does not fill
        # - We can log the success/failure of the process

        async with process_context as process:
            async for text in TextReceiveStream(process.stdout):
                # TODO: Toggle the display of this output
                print(text, end="")  # Output is already new-line terminated

        if process.returncode:
            logger.error(
                f"Subprocess for flow run '{flow_run.id}' exited with bad code: "
                f"{process.returncode}"
            )
        else:
            logger.info(f"Subprocess for flow run '{flow_run.id}' exited cleanly.")


@register_flow_runner
class FakeFlowRunner(FlowRunner):
    typename: Literal["fake"] = "fake"
    run_success: bool = True
    submit_success: bool = True

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> None:
        from prefect.client import OrionClient
        from prefect.orion.schemas.states import Completed, Failed

        if self.submit_success:
            task_status.started()
            async with OrionClient() as client:
                await client.set_flow_run_state(
                    flow_run.id, Completed() if self.run_success else Failed()
                )
        else:
            raise RuntimeError("Fake failure on submission!")
