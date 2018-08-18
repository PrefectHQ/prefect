# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import inspect
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from toolz import curry

import prefect

__all__ = ["tags", "as_task", "task"]


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

    with Flow() as f:
        with tags("math", "function"):
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

    # collections
    elif isinstance(x, list):
        return prefect.tasks.core.collections.List().bind(*x)
    elif isinstance(x, tuple):
        return prefect.tasks.core.collections.Tuple().bind(*x)
    elif isinstance(x, set):
        return prefect.tasks.core.collections.Set().bind(*x)
    elif isinstance(x, dict):
        return prefect.tasks.core.collections.Dict().bind(**x)

    # functions
    elif callable(x):
        return prefect.tasks.core.function.FunctionTask(fn=x)

    # constants
    else:
        return prefect.tasks.core.constants.Constant(value=x)


@curry
def task(
    fn: Callable, **task_init_kwargs
) -> "prefect.tasks.core.function.FunctionTask":
    """
    A decorator for creating Tasks from functions.

    Args:
        - fn (Callable): the decorated function
        - task_init_kwargs (Any): keyword arguments that will be passed to the `Task`
            constructor on initialization.

    Returns:
        - FunctionTask: A instance of a FunctionTask

    Raises:
        - ValueError: if the provided function violates signature requirements
            for Task run methods

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
    ```
    """
    return prefect.tasks.core.function.FunctionTask(fn=fn, **task_init_kwargs)
