import inspect
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from toolz import curry

import prefect

__all__ = ["group", "tags", "as_task", "task"]


@contextmanager
def group(name: str, append: bool = False) -> Iterator[None]:
    """
    Context manager for setting a task group.

    Args:
        - name (str): the name of the group
        - append (bool, optional): boolean specifying whether to append the new
            group name to any active group name found in context. Defaults to `False`

    Examples:
    ```python
    @task
    def add(x, y):
        return x + y

    with group("math"), Flow() as f:
        result = add(1, 5)

    print(result.group) # "math"
    ```

    ```python
    @task
    def add(x, y):
        return x + y

    with group("math"), group("functions", append=True), Flow() as f:
        result = add(1, 5)

    print(result.group) # "math/functions"
    ```
    """
    if append:
        current_group = prefect.context.get("_group", "")
        if current_group:
            name = current_group + "/" + name
    with prefect.context(_group=name):
        yield


@contextmanager
def tags(*tags: str) -> Iterator[None]:
    """
    Context manager for setting task tags.

    Args:
        - *tags ([str]): a list of tags to apply to the tasks created within
            the context manager

    Example:
    ```python
    @task
    def add(x, y):
        return x + y

    with tags("math", "function"), Flow() as f:
        result = add(1, 5)

    print(result.tags) # {"function", "math"}
    ```
    """
    tags_set = set(tags)
    tags_set.update(prefect.context.get("_tags", set()))
    with prefect.context(_tags=tags_set):
        yield


def as_task(x: Any) -> "prefect.core.Task":
    """
    Wraps a function, collection, or constant with the appropriate Task type.

    Args:
        -x (object): any Python object to convert to a prefect Task

    Returns:
        - a prefect Task representing the passed object
    """
    # task objects
    if isinstance(x, prefect.core.Task):
        return x

    # sequences
    elif isinstance(x, list):
        return prefect.tasks.collections.List(*[as_task(t) for t in x])
    elif isinstance(x, tuple):
        return prefect.tasks.collections.Tuple(*[as_task(t) for t in x])
    elif isinstance(x, set):
        return prefect.tasks.collections.Set(*[as_task(t) for t in x])

    # collections
    elif isinstance(x, dict):
        task_dict = {k: as_task(v) for k, v in x.items()}
        return prefect.tasks.collections.Dict(**task_dict)

    # functions
    elif callable(x):
        return prefect.tasks.core.function.FunctionTask(fn=x)

    # constants
    else:
        return prefect.tasks.core.constants.Constant(value=x)


class FunctionTaskGenerator:
    def __init__(self, fn: Callable, **kwargs) -> None:
        self.fn = fn
        self.task_init_kwargs = kwargs

    def as_task(self) -> "prefect.tasks.core.function.FunctionTask":
        return prefect.tasks.core.function.FunctionTask(
            fn=self.fn, **self.task_init_kwargs
        )

    def __call__(self, *args, **kwargs) -> "prefect.tasks.core.function.FunctionTask":
        task = self.as_task()
        try:
            return task(*args, **kwargs)
        except ValueError as exc:
            if "could not infer an active flow context" in str(exc).lower():
                raise ValueError(
                    "This task generator must be called inside a `Flow` context in order "
                    "to set up dependencies. To access the `Task` class without "
                    "dependencies, call `task_generator.as_task()`."
                )
            else:
                raise


@curry
def task(fn: Callable, **task_init_kwargs) -> FunctionTaskGenerator:
    """
    A decorator for creating Tasks from functions.

    Args:
        - fn (Callable): the decorated function
        - task_init_kwargs (Any): keyword arguments that will be passed to the `Task`
            constructor on initialization.

    Returns:
        - FunctionTaskGenerator: A class that returns a FunctionTask when called with
            zero or more appropriate arguments, and also provides an `as_task()`
            method for accessing the task without dependencies.

    Usage:

    ```
    @task(name='hello', retries=3)
    def hello(name):
        print('hello, {}'.format(name))

    with Flow() as flow:
        t1 = hello('foo')
        t2 = hello('bar')

    ```

    The decorator is best suited to Prefect's functional API, but can also be used
    with the imperative API.

    ```
    @task
    def fn_without_args():
        return 1

    @task
    def fn_with_args(x):
        return x

    # both tasks work inside a functional flow context
    with Flow():
        fn_without_args()
        fn_with_args(1)

    # both tasks can be accessed imperatively, without a flow context
    fn_without_args.as_task()
    fn_with_args.as_task()

    ```
    """
    return FunctionTaskGenerator(fn=fn, **task_init_kwargs)
