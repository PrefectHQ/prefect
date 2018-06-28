from contextlib import contextmanager
from typing import Any, Callable

from toolz import curry

import prefect


@contextmanager
def group(name: str) -> None:
    """
    Context manager for setting a task group.
    """
    current_group = prefect.context.get("group", "")
    if current_group:
        name = current_group + "." + name
    with prefect.context(group=name):
        yield


@contextmanager
def tags(*tags):
    """
    Context manager for setting task tags.
    """
    tags = set(tags)
    current_tags = prefect.context.get("tags", set())
    if current_tags:
        tags = tags.update(current_tags)
    with prefect.context(tags=tags):
        yield


def as_task(x: Any) -> "prefect.core.Task":
    """
    Wraps a function, collection, or constant with the appropriate Task type.
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
        return prefect.tasks.core.function_task.FunctionTask(fn=x)

    # constants
    else:
        return prefect.tasks.core.constants.Constant(value=x)


@curry
def task(fn: Callable, **task_init_kwargs):
    """
    A decorator for creating Tasks from functions.

    Usage:

    @task(name='hello', retries=3)
    def hello(name):
        print('hello, {}'.format(name))

    with Flow() as flow:
        t1 = hello('foo')
        t2 = hello('bar')
    """

    def task_generator(*args, **kwargs):
        task = prefect.tasks.core.function_task.FunctionTask(fn=fn, **task_init_kwargs)
        return task(*args, **kwargs)

    return task_generator
