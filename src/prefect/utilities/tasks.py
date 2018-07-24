from contextlib import contextmanager
from typing import Any, Callable, Iterator

from toolz import curry

import prefect


@contextmanager
def group(name: str, append: bool = False) -> Iterator[None]:
    """
    Context manager for setting a task group.
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
    """
    tags_set = set(tags)
    tags_set.update(prefect.context.get("_tags", set()))
    with prefect.context(_tags=tags_set):
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
