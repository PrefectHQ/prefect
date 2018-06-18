from typing import Any
from contextlib import contextmanager
import prefect
import wrapt


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


def as_task_result(x: Any) -> "prefect.core.TaskResult":
    """
    Wraps a function, collection, or constant with the appropriate Task type.
    """
    # utilities are imported first, so TaskResult must be imported here

    # task objects
    if isinstance(x, prefect.core.TaskResult):
        return x

    elif isinstance(x, prefect.Task):
        return prefect.core.TaskResult(task=x, flow=None)

    # sequences
    elif isinstance(x, list):
        return prefect.tasks.collections.List(*[as_task_result(t) for t in x])
    elif isinstance(x, tuple):
        return prefect.tasks.collections.Tuple(*[as_task_result(t) for t in x])
    elif isinstance(x, set):
        return prefect.tasks.collections.Set(*[as_task_result(t) for t in x])

    # collections
    elif isinstance(x, dict):
        task_dict = {k: as_task_result(v) for k, v in x.items()}
        return prefect.tasks.collections.Dict(**task_dict)

    # functions
    elif callable(x):
        return prefect.core.TaskResult(
            task=prefect.tasks.core.function_task.FunctionTask(fn=x), flow=None
        )

    # constants
    else:
        return prefect.core.TaskResult(
            task=prefect.tasks.core.constants.Constant(value=x), flow=None
        )

    # others - not reachable right now
    # else:
    #     raise ValueError('Could not create a Task Result from {}'.format(x))


def task_factory(**task_init_kwargs):
    """
    A decorator for marking a Task class as a factory.

    Task factories automatically instantiate the class and calls it on the
    provided arguments, returning a TaskResult.
    """

    @wrapt.decorator
    def inner(cls, instance, args, kwargs):
        task = cls(**task_init_kwargs)
        return task(*args, **kwargs)

    return inner


def task(**task_init_kwargs):
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

    @wrapt.decorator
    def inner(fn, instance, args, kwargs):
        task = prefect.tasks.core.function_task.FunctionTask(fn=fn, **task_init_kwargs)
        return task(*args, **kwargs)

    return inner
