import inspect
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Tuple

import prefect
import prefect.signals
import prefect.triggers
from prefect.utilities.json import Serializable

from prefect.environments import Environment

if TYPE_CHECKING:
    from prefect.core import Flow, Task  # pylint: disable=W0611

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


class TaskResult:
    """
    TaskResults represent the execution of a specific task in a given flow.
    """

    def __init__(self, task: "Task", flow: "Flow" = None) -> None:
        if flow is None:
            flow = prefect.core.Flow()
        flow.add_task(task)
        self.task = task
        self.flow = flow

    def __getitem__(self, index: Any) -> "TaskResult":
        from prefect.tasks.core.operators import GetItem

        index_task = GetItem(index=index, name="{}[{}]".format(self.task.name, index))
        return index_task(task_result=self)

    def set_dependencies(
        self,
        upstream_tasks: Iterable["Task"] = None,
        downstream_tasks: Iterable["Task"] = None,
        keyword_results: Dict[str, "Task"] = None,
    ) -> None:

        self.flow.set_dependencies(
            task=self.task,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            keyword_results=keyword_results,
        )

    # def wait_for(self, task_results):
    #     self.set_dependencies(upstream_tasks=task_results)
