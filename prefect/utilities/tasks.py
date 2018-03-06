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
        return prefect.tasks.collections.List(*tasks).task
    elif isinstance(x, tuple):
        tasks = [as_task(t, return_constant=False) for t in x]
        return prefect.tasks.collections.Tuple(*tasks).task
    elif isinstance(x, set):
        tasks = [as_task(t, return_constant=False) for t in x]
        return prefect.tasks.collections.Set(*tasks).task

    # collections
    elif isinstance(x, dict):
        task_dict = {k: as_task(v, return_constant=False) for k, v in x.items()}
        return prefect.tasks.collections.Dict(**task_dict).task

    # functions
    elif callable(x):
        return prefect.tasks.FunctionTask(fn=x)

    # constants
    elif return_constant:
        return prefect.tasks.Constant(value=x)

    # others
    else:
        return x


@wrapt.decorator
def task_factory(cls, instance, args, kwargs):
    """
    A decorator for marking a Task class as a factory.

    Task factories automatically instantiate the class and calls it on the
    provided arguments
    """
    return cls(**kwargs.pop('task_kwargs', {}))(*args, **kwargs)



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

def get_task_by_id(id):
    """
    Retrieves a task by its ID. This will only work for tasks that are alive
    in the current interpreter.
    """
    return prefect.core.task.TASK_REGISTRY.get(id)
