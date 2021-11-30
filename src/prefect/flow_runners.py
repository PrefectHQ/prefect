from typing import Any, Callable, Coroutine, Dict
from uuid import UUID

import anyio
from anyio.abc import TaskGroup, TaskStatus
from pydantic import BaseModel, Field

from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.utilities.logging import get_logger

_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}


class FlowRunner(BaseModel):
    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)

    env: Dict[str, str] = Field(default_factory=dict)

    def to_settings(self):
        return FlowRunnerSettings(typename=type(self).__name__, config=self.dict())

    @classmethod
    def from_settings(cls, settings: FlowRunnerSettings):
        subcls = lookup_flow_runner(settings.typename)
        return subcls(**settings.config)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_group: TaskGroup,
        callback: Callable[[bool], None],
    ) -> None:
        raise NotImplementedError()


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
        task_group: TaskGroup,
        callback: Callable[[bool], None],
    ) -> None:
        # TODO: Sort out logging
        logger = get_logger(type(self).__name__)

        async def check_result(
            task: Coroutine, flow_run_id: UUID, task_status: TaskStatus
        ) -> None:
            """
            Here we await the result of the subprocess which will contain the final flow
            run state which we will log.

            This is useful for early development but is not feasible for all planned
            submission methods so I will not generalize it yet
            """
            task_status.started()

            try:
                state = await task
            except BaseException as exc:
                # Capture errors and display them instead of tearing down the agent
                # This is most often an `Abort` signal because the flow is being run
                # by another agent.
                logger.info(f"Flow run '{flow_run_id}' exited with exception: {exc!r}")
            else:
                if state.is_failed():
                    logger.info(f"Flow run '{flow_run_id}' failed!")
                elif state.is_completed():
                    logger.info(f"Flow run '{flow_run_id}' completed.")

        import prefect.engine

        try:
            task = anyio.to_process.run_sync(
                prefect.engine.enter_flow_run_engine_from_subprocess,
                flow_run.id,
                cancellable=True,
            )
            await task_group.start(check_result, task, flow_run.id)

            # Submission was successful
            callback(True)

        except:
            # Submission failed
            callback(False)
            raise
