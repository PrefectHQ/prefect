import prefect
import wrapt


def as_task_result(x):
    """
    Wraps a function, collection, or constant with the appropriate Task type.
    """
    # utilities are imported first, so TaskResult must be imported here
    TaskResult = prefect.core.flow.TaskResult

    # task objects
    if isinstance(x, TaskResult):
        return x

    elif isinstance(x, prefect.Task):
        return TaskResult(task=x, flow=None)

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
        return TaskResult(task=prefect.tasks.FunctionTask(fn=x), flow=None)

    # constants
    else:
        return TaskResult(task=prefect.tasks.Constant(value=x), flow=None)

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
        task = prefect.tasks.FunctionTask(fn=fn, **task_init_kwargs)
        return task(*args, **kwargs)

    return inner


def get_task_by_id(id):
    """
    Retrieves a task by its ID. This will only work for tasks that are alive
    in the current interpreter.
    """
    return prefect.core.task.TASK_REGISTRY.get(id)
