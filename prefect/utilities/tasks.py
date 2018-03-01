import prefect
import wrapt


def as_task(x, return_constant=True):
    """
    Wraps a function, collection, or constant with the appropriate Task type.
    """
    # task objects
    if isinstance(x, prefect.Task):
        return x
    elif isinstance(x, prefect.core.task_result.TaskResult):
        return x.task

    # sequences
    elif isinstance(x, list):
        tasks = [as_task(t, return_constant=False) for t in x]
        return prefect.tasks.collections.list_(*tasks).task
    elif isinstance(x, tuple):
        tasks = [as_task(t, return_constant=False) for t in x]
        return prefect.tasks.collections.tuple_(*tasks).task
    elif isinstance(x, set):
        tasks = [as_task(t, return_constant=False) for t in x]
        return prefect.tasks.collections.set_(*tasks).task

    # collections
    elif isinstance(x, dict):
        task_dict = {k: as_task(v, return_constant=False) for k, v in x.items()}
        return prefect.tasks.collections.dict_(**task_dict).task

    # functions
    elif callable(x):
        return prefect.tasks.FunctionTask(fn=x)

    # constants
    elif return_constant:
        return prefect.tasks.Constant(value=x)

    # others
    else:
        return x


class TaskFactory:

    def __init__(self, task):
        self.task = task

    def __call__(self, *args, **kwargs):
        task = self.task.copy()
        return task(*args, **kwargs)


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
