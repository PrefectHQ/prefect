from typing_extensions import Literal

from .task_run_input import TaskRunInput


class Constant(TaskRunInput):
    """Represents constant input value to a task run."""

    input_type: Literal["constant"] = "constant"
    type: str
