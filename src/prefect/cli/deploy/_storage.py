from __future__ import annotations

from pathlib import Path
from typing import Any


class _PullStepStorage:
    """
    A shim storage class that allows passing pull steps to a `RunnerDeployment`.
    """

    def __init__(self, pull_steps: list[dict[str, Any]]):
        self._base_path = Path.cwd()
        self.pull_steps = pull_steps

    def set_base_path(self, path: Path):
        self._base_path = path

    @property
    def destination(self):
        return self._base_path

    @property
    def pull_interval(self):
        return 60

    async def pull_code(self):
        pass

    def to_pull_step(self):
        return self.pull_steps

    def __eq__(self, other: Any) -> bool:
        return self.pull_steps == getattr(other, "pull_steps", None)
