import asyncio
import os
import sys
from typing import Optional

import sniffio
from anyio.abc import TaskStatus
from typing_extensions import Literal

from prefect.infrastructure.base import Infrastructure
from prefect.utilities.processutils import run_process


class Subprocess(Infrastructure):
    type: Literal["subprocess"] = "subprocess"
    stream_output: bool = True

    async def run(
        self,
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
        self.logger.info(f"Opening subprocess {self.name!r}...")
        self.logger.debug(
            f"Subprocess {self.name!r} running command: {' '.join(self.command)}"
        )

        process = await run_process(
            self.command,
            stream_output=self.stream_output,
            task_status=task_status,
            env={**os.environ, **self.env},
        )

        if process.returncode:
            self.logger.error(
                f"Subprocess {self.name!r} exited with bad code: "
                f"{process.returncode}"
            )
        else:
            self.logger.info(f"Subprocess '{self.name}' exited cleanly.")

        return not process.returncode
