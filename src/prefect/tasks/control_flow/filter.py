from typing import Any, Callable, List

from prefect import Task
from prefect.triggers import all_finished


class FilterTask(Task):
    """
    Task for filtering lists of results.  The default filter removes `NoResult`s, `None`s and
    Exceptions, intended to be used for filtering out mapped results.  Note that this task has
    a default trigger of `all_finished` and `skip_on_upstream_skip=False`.

    Args:
        - filter_func (Callable, optional): a function to use for filtering
            results; this function should accept a single positional argument and return a boolean
            indicating whether this result should be _kept_ or not.  The default is
            to filter out `NoResult`s and Exceptions
        - log_func (Callable, optional): a function to use for logging the result of the filter_func
            with info log level. If no function is passed in, no logging happens (default).
        - **kwargs (optional): additional keyword arguments to pass to the Task
            constructor

    Example:

    ```python
    from prefect import task, Flow
    from prefect.tasks.control_flow import FilterTask

    default_filter = FilterTask()
    even_filter = FilterTask(filter_func=lambda x: x % 2 == 0)
    log_filter = FilterTask(
        filter_func=lambda x: x % 2 == 0,
        log_func=lambda x: f"Even numbers: {', '.join([str(y) for y in x])}",
    )

    @task
    def add(x):
        return x + 1

    @task
    def div(x):
        return 1 / x

    with Flow("filter-numbers") as flow:
        even_numbers = even_filter(add.map(x=[-1, 0, 1, 2, 3, 99, 314]))
        even_numbers_log = log_filter(add.map(x=[-1, 0, 1, 2, 3, 99, 314]))
        final_numbers = default_filter(div.map(even_numbers))

    flow_state = flow.run()

    print(flow_state.result[final_numbers].result)
    # [0.5, 0.25, 0.01]
    ```
    """

    def __init__(
        self,
        filter_func: Callable = None,
        log_func: Callable = None,
        **kwargs,
    ) -> None:
        kwargs.setdefault("skip_on_upstream_skip", False)
        kwargs.setdefault("trigger", all_finished)
        self.filter_func = filter_func or (
            lambda r: not isinstance(r, (type(None), Exception))
        )
        self.log_func = log_func
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
        filtered = [r for r in task_results if self.filter_func(r)]

        if self.log_func:
            self.logger.info(self.log_func(filtered))
        return filtered
