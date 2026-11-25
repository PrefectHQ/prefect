import threading
from dataclasses import dataclass, field
from typing import AsyncContextManager, Callable

from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncContextManager[AsyncSession]]


@dataclass
class ConcurrentCommits:
    """State of the `commit_after_run_read` fixture."""

    armed: bool = False
    writers: list[threading.Thread] = field(default_factory=list)
