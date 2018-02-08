import functools
import prefect


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


def task(fn=None, **kwargs):
    """
    A decorator for creating Tasks from functions.

    Usage:

    @task
    def myfn():
        time.sleep(10)
        return 1

    @task(name='hello', retries=3)
    def hello():
        print('hello')

    with Flow() as flow:
        hello().run_before(myfn())

    """

    if callable(fn):
        return functools.partial(prefect.tasks.FunctionTask, fn=fn)
    else:

        def wrapper(fn):
            return functools.partial(
                prefect.tasks.FunctionTask, fn=fn, **kwargs)

        return wrapper
