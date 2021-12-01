import subprocess
from typing import Any, Dict
from uuid import UUID

import anyio
import anyio.abc
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field

from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.utilities.logging import get_logger


_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}


# TODO: Sort out logging
logger = get_logger("flow_runner")


class FlowRunner(BaseModel):
    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)

    env: Dict[str, str] = Field(default_factory=dict)

    def to_settings(self):
        return FlowRunnerSettings(typename=type(self).__name__, config=self.dict())

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


def register_flow_runner(cls):
    _FLOW_RUNNERS[cls.__name__] = cls
    return cls


def lookup_flow_runner(typename: str) -> FlowRunner:
    """Return the serializer implementation for the given ``encoding``"""
    try:
        return _FLOW_RUNNERS[typename]
    except KeyError:
        raise ValueError(f"Unregistered flow runner {typename!r}")


@register_flow_runner
class SubprocessFlowRunner(FlowRunner):
    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> None:
        logger.info(f"Opening subprocess for flow run '{flow_run.id}'...")
        process_context = await anyio.open_process(
            ["python", "-m", "prefect.engine", flow_run.id.hex],
            stderr=subprocess.STDOUT,
        )
        task_status.started()

        async with process_context as process:
            # Consume the text stream so the buffer does not fill
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
