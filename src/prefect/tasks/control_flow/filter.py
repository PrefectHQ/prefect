import warnings
from typing import Any, Callable, List

import prefect
from prefect import Task
from prefect.triggers import all_finished
from prefect.engine.result import NoResultType


class FilterTask(Task):
    """
    Task for filtering lists of results.  The default filter is to filter out `NoResult`s and
    Exceptions for filtering out mapped results.  Note that this task has a default trigger of
    `all_finished` and `skip_on_upstream_skip=False`.

    Args:
        - filter_func (Callable, optional): a function to use for filtering
            results; this function should accept a single positional argument and return a boolean
            indicating whether this result should be _kept_ or not.  The default is
            to filter out `NoResult`s and Exceptions
        - **kwargs (optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(self, filter_func: Callable = None, **kwargs) -> None:
        kwargs.setdefault("skip_on_upstream_skip", False)
        kwargs.setdefault("trigger", all_finished)
        self.filter_func = filter_func or (
            lambda r: not isinstance(r, (NoResultType, Exception))
        )
        super().__init__(**kwargs)

    def run(self, task_results: List[Any]) -> List[Any]:
        """
        Task run method.

        Args:
            - task_results (List[Any]): a list of results from upstream tasks,
                which will be filtered using `self.filter_func`

        Returns:
            - List[Any]: a filtered list of results
        """
        return [r for r in task_results if self.filter_func(r)]
