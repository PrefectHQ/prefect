# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import warnings
from typing import Any, Callable, List

import prefect
from prefect import Task
from prefect.triggers import all_finished
from prefect.engine.result import NoResultType


class FilterTask(Task):
    def __init__(self, filter_func: Callable = None, **kwargs) -> None:
        kwargs.setdefault("skip_on_upstream_skip", False)
        kwargs.setdefault("trigger", all_finished)
        self.filter_func = filter_func or (lambda r: not isinstance(r, (NoResultType, Exception)))
        super().__init__(**kwargs)

    def run(self, task_results: List[Any]) -> List[Any]:
        return [r for r in task_results if self.filter_func(r)]
