from uuid import UUID

from typing_extensions import Literal

from .task_run_input import TaskRunInput


class TaskRunResult(TaskRunInput):
    """Represents a task run result input to another task run."""

    input_type: Literal["task_run"] = "task_run"
    id: UUID
