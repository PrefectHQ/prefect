import itertools
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional, overload, Union

import pendulum

import prefect

__all__ = [
    "tags",
    "as_task",
    "pause_task",
    "task",
    "apply_map",
    "defaults_from_attrs",
]

if TYPE_CHECKING:
    import prefect.tasks.core.constants
    import prefect.tasks.core.collections
    import prefect.tasks.core.function
    from prefect import Flow


def apply_map(func: Callable, *args: Any, flow: "Flow" = None, **kwargs: Any) -> Any:
    """
    Map a function that adds tasks to a flow elementwise across one or more
    tasks.  Arguments that should _not_ be mapped over should be wrapped with
    `prefect.unmapped`.

    This can be useful when wanting to create complicated mapped pipelines
    (e.g. ones using control flow components like `case`).

    Args:
        - func (Callable): a function that adds tasks to a flow
        - *args: task arguments to map over
        - flow (Flow, optional): The flow to use, defaults to the current flow
            in context if no flow is specified. If specified, `func` must accept
            a `flow` keyword argument.
        - **kwargs: keyword task arguments to map over

    Returns:
        - Any: the output of `func`, if any

    Example:

    ```python
    from prefect import task, case, apply_map
    from prefect.tasks.control_flow import merge

    @task
    def inc(x):
        return x + 1

    @task
    def is_even(x):
        return x % 2 == 0

    def inc_if_even(x):
        with case(is_even(x), True):
            x2 = inc(x)
        return merge(x, x2)

    with Flow("example") as flow:
        apply_map(inc_if_even, range(10))
    ```
    """
    from prefect.tasks.core.constants import Constant

    no_flow_provided = flow is None
    if no_flow_provided:
        flow = prefect.context.get("flow", None)
        if flow is None:
            raise ValueError("Couldn't infer a flow in the current context")
    assert isinstance(flow, prefect.Flow)  # appease mypy

    # Check if args/kwargs are valid first
    for x in itertools.chain(args, kwargs.values()):
        if not isinstance(
            x, (prefect.Task, prefect.utilities.edges.EdgeAnnotation, Sequence)
        ):
            raise TypeError(
                f"Cannot map over non-sequence object of type `{type(x).__name__}`"
            )

    flow2 = prefect.Flow("temporary flow")
    # A mapping of all the input args -> (is_mapped, is_constant)
    arg_info = {}
    # A mapping of the ids of all constants -> the Constant task.
    # Used to convert constants to constant tasks if needed
    id_to_const = {}

    # Preprocess inputs to `apply_map`:
    # - Extract information about each argument (is unmapped, is constant, ...)
    # - Convert all arguments to instances of `Task`
    # - Add all non-constant arguments to the flow and subflow. Constant arguments
    #   are added later as needed.
    def preprocess(a: Any) -> "prefect.Task":
        # Clear external case/resource when adding tasks to flow2
        with prefect.context(case=None, resource=None):
            a2 = as_task(a, flow=flow2)
            is_mapped = not isinstance(a, prefect.utilities.edges.unmapped)
            is_constant = isinstance(a2, Constant)
            if not is_constant:
                flow2.add_task(a2)  # type: ignore

        arg_info[a2] = (is_mapped, is_constant)
        if not is_constant:
            flow.add_task(a2)  # type: ignore
        if is_mapped and is_constant:
            id_to_const[id(a2.value)] = a2  # type: ignore
        return a2

    args2 = [preprocess(a) for a in args]
    kwargs2 = {k: preprocess(v) for k, v in kwargs.items()}

    # Construct a temporary flow for the subgraph
    # We set case=None & resource=None to ignore any external case/resource
    # blocks while constructing the temporary flow.
    with prefect.context(mapped=True, case=None, resource=None):
        with flow2:
            if no_flow_provided:
                res = func(*args2, **kwargs2)
            else:
                res = func(*args2, flow=flow2, **kwargs2)

    # Copy over all tasks in the subgraph
    for task in flow2.tasks:
        flow.add_task(task)

    # Copy over all edges, updating any non-explicitly-unmapped edges to mapped
    for edge in flow2.edges:
        flow.add_edge(
            upstream_task=edge.upstream_task,
            downstream_task=edge.downstream_task,
            key=edge.key,
            mapped=arg_info.get(edge.upstream_task, (True,))[0],
        )

    # Copy over all constants, updating any constants that should be mapped
    # to be tasks rather than stored in the constants mapping
    for task, constants in flow2.constants.items():
        for key, c in constants.items():
            if id(c) in id_to_const:
                c_task = id_to_const[id(c)]
                flow.add_task(c_task)
                flow.add_edge(
                    upstream_task=c_task, downstream_task=task, key=key, mapped=True
                )
            else:
                flow.constants[task][key] = c

    # Any task created inside `apply_map` must have a transitive dependency to
    # all of the inputs to apply_map, except for unmapped constants.  This
    # ensures three things:
    #
    # - All mapped arguments must have the same length. supporting disparate
    # lengths leads to odd semantics.
    #
    # - Tasks created by `apply_map` conceptually share an upstream dependency
    # tree. This matches the causality you'd expect if you were running as
    # normal eager python code - the stuff inside the `apply_map` only runs if
    # the inputs are completed, not just the inputs that certain subcomponents
    # depend on.
    #
    # - Tasks with no external dependencies are treated the same as tasks with
    # external deps (we need to add upstream_tasks to tasks created in `func`
    # with no external deps to get them to run as proper map tasks).  We add
    # upstream tasks uniformly for all tasks, not just ones without external
    # deps - the uniform behavior makes this easier to reason about.
    #
    # Here we do a final pass adding missing upstream deps on mapped arguments
    # to all newly created tasks in the apply_map.
    new_tasks = flow2.tasks.difference(arg_info)
    for task in new_tasks:
        upstream_tasks = flow.upstream_tasks(task)
        is_root_in_subgraph = not upstream_tasks.intersection(new_tasks)
        if is_root_in_subgraph:
            for arg_task, (is_mapped, is_constant) in arg_info.items():
                # Add all args except unmapped constants as direct
                # upstream tasks if they're not already upstream tasks
                if arg_task not in upstream_tasks and (is_mapped or not is_constant):
                    flow.add_edge(
                        upstream_task=arg_task, downstream_task=task, mapped=is_mapped
                    )
    return res


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


def as_task(x: Any, flow: "Optional[Flow]" = None) -> "prefect.Task":
    """
    Wraps a function, collection, or constant with the appropriate Task type. If a constant
    or collection of constants is passed, a `Constant` task is returned.

    Args:
        - x (object): any Python object to convert to a prefect Task
        - flow (Flow, optional): Flow to which the prefect Task will be bound

    Returns:
        - a prefect Task representing the passed object
    """
    from prefect.tasks.core.constants import Constant

    def is_constant(x: Any) -> bool:
        """
        Helper function for determining if nested collections are constants without calling
        `bind()`, which would create new tasks on the active graph.
        """
        if isinstance(x, (prefect.core.Task, prefect.utilities.edges.EdgeAnnotation)):
            return False
        elif isinstance(x, (list, tuple, set)):
            return all(is_constant(xi) for xi in x)
        elif isinstance(x, dict):
            return all(is_constant(xi) for xi in x.values())
        return True

    # task objects
    if isinstance(x, prefect.core.Task):  # type: ignore
        return x
    elif isinstance(x, prefect.utilities.edges.EdgeAnnotation):
        return as_task(x.value, flow=flow)

    # handle constants, including collections of constants
    elif is_constant(x):
        return_task = Constant(x)  # type: prefect.core.Task

    # collections
    elif isinstance(x, list):
        return_task = prefect.tasks.core.collections.List().bind(*x, flow=flow)
    elif isinstance(x, tuple):
        return_task = prefect.tasks.core.collections.Tuple().bind(*x, flow=flow)
    elif isinstance(x, set):
        return_task = prefect.tasks.core.collections.Set().bind(*x, flow=flow)
    elif isinstance(x, dict):
        keys, values = [], []
        for k, v in x.items():
            keys.append(k)
            values.append(v)
        return_task = prefect.tasks.core.collections.Dict().bind(
            keys=keys, values=values, flow=flow
        )

    else:
        return x

    return_task.auto_generated = True  # type: ignore
    return return_task


def pause_task(message: str = None, duration: timedelta = None) -> None:
    """
    Utility function for pausing a task during execution to wait for manual intervention.
    Note that the _entire task_ will be rerun if the user decides to run this task again!
    The only difference is that this utility will _not_ raise a `PAUSE` signal.
    To bypass a `PAUSE` signal being raised, put the task into a Resume state.

    Args:
        - message (str): an optional message for the Pause state.
        - duration (timedelta): an optional pause duration; otherwise infinite (well, 10 years)

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
    if duration is not None:
        start_time = pendulum.now("utc") + duration
    else:
        start_time = None
    if prefect.context.get("resume", False) is False:
        raise prefect.engine.signals.PAUSE(  # type: ignore
            message=message or "Pause signal raised during task execution.",
            start_time=start_time,
        )


# To support mypy type checking with optional arguments to `task`, we need to
# make use of `typing.overload`
@overload
def task(__fn: Callable) -> "prefect.tasks.core.function.FunctionTask":
    pass


@overload
def task(
    **task_init_kwargs: Any,
) -> Callable[[Callable], "prefect.tasks.core.function.FunctionTask"]:
    pass


def task(
    fn: Callable = None, **task_init_kwargs: Any
) -> Union[
    "prefect.tasks.core.function.FunctionTask",
    Callable[[Callable], "prefect.tasks.core.function.FunctionTask"],
]:
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
    if fn is None:
        return lambda fn: prefect.tasks.core.function.FunctionTask(
            fn=fn,
            **task_init_kwargs,
        )
    return prefect.tasks.core.function.FunctionTask(fn=fn, **task_init_kwargs)


def defaults_from_attrs(*attr_args: str) -> Callable:
    """
    Helper decorator for dealing with Task classes with attributes that serve
    as defaults for `Task.run`.  Specifically, this decorator allows the author
    of a Task to identify certain keyword arguments to the run method which
    will fall back to `self.ATTR_NAME` if not explicitly provided to
    `self.run`.  This pattern allows users to create a Task "template", whose
    default settings can be created at initialization but overrided in
    individual instances when the Task is called.

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
