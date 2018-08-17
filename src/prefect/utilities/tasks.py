import inspect
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from toolz import curry

import prefect

__all__ = ["groups", "tags", "as_task", "task"]


@contextmanager
def groups(*groups: str) -> Iterator[None]:
    """
    Context manager for setting a task group.

    Args:
        - *groups ([str]): a list of groups to apply to the tasks created within
            the context manager

    Examples:
    ```python
    @task
    def add(x, y):
        return x + y

    @task
    def sub(x, y):
        return x - y

    @task
    def say_hi():
        print('hi')

    with Flow() as f:
        with groups("math"):
            a = add(1, 5)
            b = sub(1, 5)
        with groups("io"):
            c = say_hi()

    print(a.groups) # {"math"}
    print(c.groups) # {"io"}
    ```

    ```python
    @task
    def add(x, y):
        return x + y

    with Flow() as f:
        with groups("math"):
            with groups("functions"):
                result = add(1, 5)

    print(result.groups) # {"math", "functions"}
    ```
    """
    current_groups = prefect.context.get("_groups", set())
    groups_set = current_groups | set(groups)
    with prefect.context(_groups=groups_set):
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
