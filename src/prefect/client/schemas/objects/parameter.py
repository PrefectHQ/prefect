from typing_extensions import Literal

from .task_run_input import TaskRunInput


class Parameter(TaskRunInput):
    """Represents a parameter input to a task run."""

    input_type: Literal["parameter"] = "parameter"
    name: str
