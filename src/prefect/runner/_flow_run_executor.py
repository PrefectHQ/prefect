from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import anyio
import anyio.abc

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._process_manager import ProcessHandle


class ProcessStarter(Protocol):
    """Structural typing interface for process-starting strategies.

    Any object with a conforming `.start()` signature qualifies -- no
    inheritance required. Test doubles can use simple AsyncMock or a plain
    async function.

    Contract for `start()`:
    - Call `task_status.started(handle)` BEFORE blocking (signals caller that
      `ProcessHandle` is available before process completes)
    - Block until process exits
    - Return None after process exits
    """

    async def start(
        self,
        flow_run: FlowRun,
        task_status: anyio.abc.TaskStatus[ProcessHandle] = anyio.TASK_STATUS_IGNORED,
    ) -> None: ...
