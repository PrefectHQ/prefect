import inspect
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator, Iterable, TYPE_CHECKING

from toolz import curry

import prefect

__all__ = ["tags", "as_task", "pause_task", "task", "unmapped", "defaults_from_attrs"]

if TYPE_CHECKING:
    import prefect.tasks.core.function


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

    with Flow("My Flow") as f:
        with tags("math", "function"):
            result = add(1, 5)

    print(result.tags) # {"function", "math"}
    ```
    """
    tags_set = set(tags)
    tags_set.update(prefect.context.get("tags", set()))
    with prefect.context(tags=tags_set):
        yield


def as_task(x: Any) -> "prefect.Task":
    """
    Wraps a function, collection, or constant with the appropriate Task type.

    Args:
        - x (object): any Python object to convert to a prefect Task

    Returns:
        - a prefect Task representing the passed object
    """
    # task objects
    if isinstance(x, prefect.core.Task):  # type: ignore
        return x
    elif isinstance(x, unmapped):
        return x.task

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


def pause_task(message: str = None) -> None:
    """
    Utility function for pausing a task during execution to wait for manual intervention.
    Note that the _entire task_ will be rerun if the user decides to run this task again!
    The only difference is that this utility will simply _not_ raise a `PAUSE` signal.
    To bypass a `PAUSE` signal being raised, simply put the task into a Resume state.

    Args:
        - message (str): an optional message for the Pause state.

    Example:
        ```python
        from prefect import Flow
        from prefect.utilities.tasks import task, pause_task

        @task
        def add(x, y):
            z = y - x  ## this code will be rerun after resuming from the pause!
            if z == 0: ## this code will be rerun after resuming from the pause!
                pause_task()
            return x + y

        with Flow("My Flow") as f:
            res = add(4, 4)

        state = f.run()
        state.result[res] # a Paused state

        state = f.run(task_states={res: Resume()})
        state.result[res] # a Success state
        ```
    """
    if prefect.context.get("resume", False) is False:
        raise prefect.engine.signals.PAUSE(  # type: ignore
            message or "Pause signal raised during task execution."
        )


@curry
def task(
    fn: Callable, **task_init_kwargs: Any
) -> "prefect.tasks.core.function.FunctionTask":
    """
    A decorator for creating Tasks from functions.

    Args:
        - fn (Callable): the decorated function
        - **task_init_kwargs (Any): keyword arguments that will be passed to the `Task`
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

    with Flow("My Flow") as flow:
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
    with Flow("My Flow"):
        fn_without_args()
        fn_with_args(1)
    ```
    """
    return prefect.tasks.core.function.FunctionTask(fn=fn, **task_init_kwargs)


class unmapped:
    """
    A container for specifying that a task should _not_ be mapped over when
    called with `task.map`.

    Args:
        - task (Task): the task to mark as "unmapped"; if not a Task subclass,
            Prefect will attempt to convert it to one.

    Example:
        ```python
        from prefect import Flow, Task, unmapped

        class AddTask(Task):
            def run(self, x, y):
                return x + y

        class ListTask(Task):
            def run(self):
                return [1, 2, 3]

        with Flow("My Flow"):
            add = AddTask()
            ll = ListTask()
            result = add.map(x=ll, y=unmapped(5), upstream_tasks=[unmapped(Task())])
        ```
    """

    def __init__(self, task: "prefect.Task"):
        self.task = as_task(task)


def defaults_from_attrs(*attr_args: str) -> Callable:
    """
    Helper decorator for dealing with Task classes with attributes which serve
    as defaults for `Task.run`.  Specifically, this decorator allows the author of a Task
    to identify certain keyword arguments to the run method which will fall back to `self.ATTR_NAME`
    if not explicitly provided to `self.run`.  This pattern allows users to create a Task "template",
    whose default settings can be created at initialization but overrided in individual instances when the
    Task is called.

    Args:
        - *attr_args (str): a splatted list of strings specifying which
            kwargs should fallback to attributes, if not provided at runtime. Note that
            the strings provided here must match keyword arguments in the `run` call signature,
            as well as the names of attributes of this Task.

    Returns:
        - Callable: the decorated / altered `Task.run` method

    Example:
    ```python
    class MyTask(Task):
        def __init__(self, a=None, b=None):
            self.a = a
            self.b = b

        @defaults_from_attrs('a', 'b')
        def run(self, a=None, b=None):
            return a, b

    task = MyTask(a=1, b=2)

    task.run() # (1, 2)
    task.run(a=99) # (99, 2)
    task.run(a=None, b=None) # (None, None)
    ```
    """

    def wrapper(run_method: Callable) -> Callable:
        @wraps(run_method)
        def method(self: Any, *args: Any, **kwargs: Any) -> Any:
            for attr in attr_args:
                kwargs.setdefault(attr, getattr(self, attr))
            return run_method(self, *args, **kwargs)

        return method

    return wrapper
