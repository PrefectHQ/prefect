import subprocess
from typing import Dict, TypeVar, Type, Optional

import anyio
import anyio.abc
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from pydantic import BaseModel, Field
from typing_extensions import Literal

from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.utilities.logging import get_logger

_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}
FlowRunnerT = TypeVar("FlowRunnerT", bound=Type["FlowRunner"])


"""Temporary patch"""

import asyncio
import itertools
import logging
import time
import threading

try:
    # Python 3.8 or newer has a suitable process watcher
    asyncio.ThreadedChildWatcher
except AttributeError:
    # backport the Python 3.8 threaded child watcher
    import os
    import warnings

    # Python 3.7 preferred API
    _get_running_loop = getattr(asyncio, "get_running_loop", asyncio.get_event_loop)

    class _Py38ThreadedChildWatcher(asyncio.AbstractChildWatcher):
        def __init__(self):
            self._pid_counter = itertools.count(0)
            self._threads = {}

        def is_active(self):
            return True

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def __del__(self, _warn=warnings.warn):
            threads = [t for t in list(self._threads.values()) if t.is_alive()]
            if threads:
                _warn(
                    f"{self.__class__} has registered but not finished child processes",
                    ResourceWarning,
                    source=self,
                )

        def add_child_handler(self, pid, callback, *args):
            loop = _get_running_loop()
            thread = threading.Thread(
                target=self._do_waitpid,
                name=f"waitpid-{next(self._pid_counter)}",
                args=(loop, pid, callback, args),
                daemon=True,
            )
            self._threads[pid] = thread
            thread.start()

        def remove_child_handler(self, pid):
            # asyncio never calls remove_child_handler() !!!
            # The method is no-op but is implemented because
            # abstract base class requires it
            return True

        def attach_loop(self, loop):
            pass

        def _do_waitpid(self, loop, expected_pid, callback, args):
            assert expected_pid > 0

            try:
                pid, status = os.waitpid(expected_pid, 0)
            except ChildProcessError:
                # The child process is already reaped
                # (may happen if waitpid() is called elsewhere).
                pid = expected_pid
                returncode = 255
            else:
                if os.WIFSIGNALED(status):
                    returncode = -os.WTERMSIG(status)
                elif os.WIFEXITED(status):
                    returncode = os.WEXITSTATUS(status)
                else:
                    returncode = status

            if not loop.is_closed():
                loop.call_soon_threadsafe(callback, pid, returncode, *args)

            self._threads.pop(expected_pid)

    # add the watcher to the loop policy
    asyncio.get_event_loop_policy().set_child_watcher(_Py38ThreadedChildWatcher())


class FlowRunner(BaseModel):
    """
    Flow runners are responsible for creating infrastructure for flow runs and starting
    execution.

    Attributes:
        env: Environment variables to provide to the flow run
    """

    typename: str

    def to_settings(self):
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
            "runner type."
        )


@register_flow_runner
class SubprocessFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a local subprocess
    """

    typename: Literal["subprocess"] = "subprocess"
    stream_output: bool = Field(
        False,
        description="Stream output from the subprocess to local standard output.",
    )

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:

        # Open a subprocess to execute the flow run
        self.logger.info(f"Opening subprocess for flow run '{flow_run.id}'...")
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
