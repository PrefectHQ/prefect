import asyncio
import os
import sys
from typing import Optional

import sniffio
from anyio.abc import TaskStatus
from pydantic import BaseModel
from typing_extensions import Literal

from prefect.infrastructure.base import Infrastructure
from prefect.utilities.processutils import run_process


def _use_threaded_child_watcher():
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


class Process(Infrastructure):
    type: Literal["subprocess"] = "subprocess"
    stream_output: bool = True

    async def run(
        self,
        task_status: TaskStatus = None,
    ) -> Optional[bool]:
        if not self.command:
            raise ValueError("Process cannot be run with empty command.")

        _use_threaded_child_watcher()

        # Open a subprocess to execute the flow run
        self.logger.info(f"Opening process {self.name!r}...")
        self.logger.debug(
            f"Process {self.name!r} running command: {' '.join(self.command)}"
        )

        process = await run_process(
            self.command,
            stream_output=self.stream_output,
            task_status=task_status,
            env={**os.environ, **self.env},
        )

        if process.returncode:
            self.logger.error(
                f"Process {self.name!r} exited with bad code: " f"{process.returncode}"
            )
        else:
            self.logger.info(f"Process '{self.name}' exited cleanly.")

        return ProcessResult(returncode=process.returncode)


class ProcessResult(BaseModel):
    returncode: int

    def __bool__(self):
        return self.returncode == 0
