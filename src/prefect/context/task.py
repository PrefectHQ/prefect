from contextvars import ContextVar
from typing import (
    Any,
    Dict,
)

from prefect.client.schemas import TaskRun
from prefect.results import ResultFactory
from prefect.tasks import Task

from .main import RunContext


class TaskRunContext(RunContext):
    """
    The context for a task run. Data in this context is only available from within a
    task run function.

    Attributes:
        task: The task instance associated with the task run
        task_run: The API metadata for this task run
    """

    task: "Task"
    task_run: TaskRun
    log_prints: bool = False
    parameters: Dict[str, Any]

    # Result handling
    result_factory: ResultFactory

    __var__ = ContextVar("task_run")

    def serialize(self):
        return self.model_dump(
            include={
                "task_run",
                "task",
                "parameters",
                "log_prints",
                "start_time",
                "input_keyset",
            },
            exclude_unset=True,
        )
