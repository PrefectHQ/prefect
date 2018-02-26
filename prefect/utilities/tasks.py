import prefect

import wrapt


def as_task(x):
    """
    Wraps a function or constant with the appropriate Task type.
    """
    if isinstance(x, prefect.Task):
        return x
    elif callable(x):
        return prefect.tasks.FunctionTask(fn=x)
    else:
        return prefect.tasks.Constant(value=x)


def task(**task_init_kwargs):
    """
    A decorator for creating Tasks from functions.

    Usage:

    @task(name='hello', retries=3)
    def hello(name):
        print('hello, {}'.format(name))

    with Flow() as flow:
        t1 = hello('x')
        t2 = hello('y')
    """

    @wrapt.decorator
    def task_factory(fn, instance, args, kwargs):
        task = prefect.tasks.FunctionTask(fn=fn, **task_init_kwargs)
        return task(*args, **kwargs)
    return task_factory

