import collections.abc
import copy
import enum
import functools
import inspect
import typing
import warnings
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Union,
    Tuple,
)
from collections import defaultdict

import prefect
import prefect.engine.cache_validators
import prefect.engine.signals
import prefect.triggers
from prefect.utilities import logging
from prefect.utilities.notifications import callback_factory
from prefect.utilities.edges import EdgeAnnotation

if TYPE_CHECKING:
    from prefect.core.flow import Flow
    from prefect.engine.result import Result
    from prefect.engine.state import State
    from prefect.core import Edge

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


# A sentinel value indicating no default was provided
# mypy requires enums for typed sentinel values, so other
# simpler solutions won't work :/
class NoDefault(enum.Enum):
    value = "no_default"

    def __repr__(self) -> str:
        return "<no default>"


def _validate_run_signature(run: Callable) -> None:
    func = inspect.unwrap(run)
    try:
        run_sig = inspect.getfullargspec(func)
    except TypeError as exc:
        if str(exc) == "unsupported callable":
            raise ValueError(
                "This function can not be inspected (this is common "
                "with `builtin` and `numpy` functions). In order to "
                "use it as a task, please wrap it in a standard "
                "Python function. For more detail, see "
                "https://docs.prefect.io/core/advanced_tutorials/task-guide.html#the-task-decorator"
            ) from exc
        raise

    if run_sig.varargs:
        raise ValueError(
            "Tasks with variable positional arguments (*args) are not "
            "supported, because all Prefect arguments are stored as "
            "keywords. As a workaround, consider modifying the run() "
            "method to accept **kwargs and feeding the values "
            "to *args."
        )

    reserved_kwargs = ["upstream_tasks", "mapped", "task_args", "flow"]
    violations = [kw for kw in reserved_kwargs if kw in run_sig.args]
    if violations:
        msg = "Tasks cannot have the following argument names: {}.".format(
            ", ".join(violations)
        )
        msg += " These are reserved keyword arguments."
        raise ValueError(msg)


def _infer_run_nout(run: Callable) -> Optional[int]:
    """Infer the number of outputs for a callable from its type annotations.

    Returns `None` if infererence failed, or if the type has variable-length.
    """
    try:
        ret_type = inspect.signature(run).return_annotation
    except Exception:
        return None
    if ret_type is inspect.Parameter.empty:
        return None
    # New in python 3.8
    if hasattr(typing, "get_origin"):
        origin = typing.get_origin(ret_type)
    else:
        origin = getattr(ret_type, "__origin__", None)

    if origin in (typing.Tuple, tuple):
        # Plain Tuple is a variable-length tuple
        if ret_type in (typing.Tuple, tuple):
            return None

        # New in python 3.8
        if hasattr(typing, "get_args"):
            args = typing.get_args(ret_type)
        else:
            args = getattr(ret_type, "__args__", ())

        # Empty tuple type has a type arg of the empty tuple
        if len(args) == 1 and args[0] == ():
            return 0
        # Variable-length tuples have Ellipsis as the 2nd arg
        if len(args) == 2 and args[1] == Ellipsis:
            return None
        # All other Tuples are length-of args
        return len(args)
    return None


class TaskMetaclass(type):
    """A metaclass for enforcing two checks on a task:

    - Checks that the `run` method has a valid signature
    - Adds a check to the `__init__` method that no tasks are passed as arguments
    """

    def __new__(cls, name: str, parents: tuple, methods: dict) -> "TaskMetaclass":
        run = methods.get("run", lambda: None)
        _validate_run_signature(run)

        if "__init__" in methods:
            old_init = methods["__init__"]

            # Theoretically we could do this by defining a `__new__` method for
            # the `Task` class that handles this check, but unfortunately if a
            # class defines `__new__`, `inspect.signature` will use the
            # signature for `__new__` regardless of the signature for
            # `__init__`. This basically kills all type completions or type
            # hints for the `Task` constructors. As such, we handle it in the
            # metaclass
            @functools.wraps(old_init)
            def init(self: Any, *args: Any, **kwargs: Any) -> None:
                if any(isinstance(a, Task) for a in args + tuple(kwargs.values())):
                    cls_name = type(self).__name__
                    warnings.warn(
                        f"A Task was passed as an argument to {cls_name}, you likely want to "
                        f"first initialize {cls_name} with any static (non-Task) arguments, "
                        "then call the initialized task with any dynamic (Task) arguments instead. "
                        "For example:\n\n"
                        f"  my_task = {cls_name}(...)  # static (non-Task) args go here\n"
                        f"  res = my_task(...)  # dynamic (Task) args go here\n\n"
                        "see https://docs.prefect.io/core/concepts/flows.html#apis for more info.",
                        stacklevel=2,
                    )
                old_init(self, *args, **kwargs)

            methods = methods.copy()
            methods["__init__"] = init

        # necessary to ensure classes that inherit from parent class
        # also get passed through __new__
        return type.__new__(cls, name, parents, methods)  # type: ignore

    @property
    def _reserved_attributes(self) -> Tuple[str]:
        """A tuple of attributes reserved for use by the `Task` class.

        Dynamically computed to make it easier to keep up to date. Lazily
        computed to avoid circular import issues.
        """
        if not hasattr(Task, "_cached_reserved_attributes"):
            # Create a base task instance to determine which attributes are reserved
            # we need to disable the unused_task_tracker for this duration or it will
            # track this task
            with prefect.context(_unused_task_tracker=set()):
                Task._cached_reserved_attributes = tuple(sorted(Task().__dict__))  # type: ignore
        return Task._cached_reserved_attributes  # type: ignore


class instance_property:
    """Like property, but only available on instances, not the class"""

    def __init__(self, func: Callable):
        self.func = func

    def __getattr__(self, k: str) -> Any:
        return getattr(self.func, k)

    def __get__(self, obj: Any, cls: Any) -> Any:
        if obj is None:
            raise AttributeError
        return self.func(obj)


class Task(metaclass=TaskMetaclass):
    """
    The Task class which is used as the full representation of a unit of work.

    This Task class can be used directly as a first class object where it must
    be inherited from by a class that implements the `run` method.  For a more
    functional way of generating Tasks, see [the task decorator](../utilities/tasks.html).

    Inheritance example:
    ```python
    class AddTask(Task):
        def run(self, x, y):
            return x + y
    ```

    *Note:* The implemented `run` method cannot have `*args` in its signature. In addition,
    the following keywords are reserved: `upstream_tasks`, `task_args` and `mapped`.

    An instance of a `Task` can be used functionally to generate other task instances
    with the same attributes but with different values bound to their `run` methods.

    Example:
    ```python
    class AddTask(Task):
        def run(self, x, y):
            return x + y

    a = AddTask()

    with Flow("My Flow") as f:
        t1 = a(1, 2) # t1 != a
        t2 = a(5, 7) # t2 != a
    ```

    To bind values to a Task's run method imperatively (and without making a copy), see `Task.bind`.

    Args:
        - name (str, optional): The name of this task
        - slug (str, optional): The slug for this task. Slugs provide a stable ID for tasks so
            that the Prefect API can identify task run states. If a slug is not provided, one
            will be generated automatically once the task is added to a Flow.
        - tags ([str], optional): A list of tags for this task
        - max_retries (int, optional): The maximum amount of times this task can be retried
        - retry_delay (timedelta, optional): The amount of time to wait until task is retried
        - timeout (Union[int, timedelta], optional): The amount of time (in seconds) to wait while
            running this task before a timeout occurs; note that sub-second
            resolution is not supported, even when passing in a timedelta.
        - trigger (callable, optional): a function that determines whether the
            task should run, based on the states of any upstream tasks.
        - skip_on_upstream_skip (bool, optional): if `True`, if any immediately
            upstream tasks are skipped, this task will automatically be skipped as
            well, regardless of trigger. By default, this prevents tasks from
            attempting to use either state or data from tasks that didn't run. If
            `False`, the task's trigger will be called as normal, with skips
            considered successes. Defaults to `True`.
        - cache_for (timedelta, optional): The amount of time to maintain a cache
            of the outputs of this task.  Useful for situations where the containing Flow
            will be rerun multiple times, but this task doesn't need to be.
        - cache_validator (Callable, optional): Validator that will determine
            whether the cache for this task is still valid (only required if `cache_for`
            is provided; defaults to `prefect.engine.cache_validators.duration_only`)
        - cache_key (str, optional): if provided, a `cache_key`
            serves as a unique identifier for this Task's cache, and can be shared
            across both Tasks _and_ Flows; if not provided, the Task's _name_ will
            be used if running locally, or the Task's database ID if running in
            Cloud
        - checkpoint (bool, optional): if this Task is successful, whether to
            store its result using the configured result available during the run;
            Also note that checkpointing will only occur locally if
            `prefect.config.flows.checkpointing` is set to `True`
        - result (Result, optional): the result instance used to retrieve and
            store task results during execution
        - target (Union[str, Callable], optional): location to check for task Result. If a result
            exists at that location then the task run will enter a cached state.
            `target` strings can be templated formatting strings which will be
            formatted at runtime with values from `prefect.context`. If a callable function
            is provided, it should have signature `callable(**kwargs) -> str` and at write
            time all formatting kwargs will be passed and a fully formatted location is
            expected as the return value. The callable can be used for string formatting logic that
            `.format(**kwargs)` doesn't support.
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the task changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the task instance, the old (prior) state, and the new
            (current) state, with the following signature:
                `state_handler(task: Task, old_state: State, new_state: State) -> Optional[State]`
            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.
        - on_failure (Callable, optional): A function with signature
            `fn(task: Task, state: State) -> None` that will be called anytime this
            Task enters a failure state
        - log_stdout (bool, optional): Toggle whether or not to send stdout messages to
            the Prefect logger. Defaults to `False`.
        - task_run_name (Union[str, Callable], optional): a name to set for this task at runtime.
            `task_run_name` strings can be templated formatting strings which will be
            formatted at runtime with values from task arguments, `prefect.context`, and flow
            parameters (in the case of a name conflict between these, earlier values take precedence).
            If a callable function is provided, it should have signature `callable(**kwargs) -> str`
            and at write time all formatting kwargs will be passed and a fully formatted location is
            expected as the return value. The callable can be used for string formatting logic that
            `.format(**kwargs)` doesn't support. **Note**: this only works for tasks running against a
            backend API.
        - nout (int, optional): for tasks that return multiple results, the number of outputs
            to expect. If not provided, will be inferred from the task return annotation, if
            possible.  Note that `nout=1` implies the task returns a tuple of
            one value (leave as `None` for non-tuple return types).

    Raises:
        - TypeError: if `tags` is of type `str`
        - TypeError: if `timeout` is not of type `int`
    """

    def __init__(
        self,
        name: str = None,
        slug: str = None,
        tags: Iterable[str] = None,
        max_retries: int = None,
        retry_delay: timedelta = None,
        timeout: Union[int, timedelta] = None,
        trigger: "Callable[[Dict[Edge, State]], bool]" = None,
        skip_on_upstream_skip: bool = True,
        cache_for: timedelta = None,
        cache_validator: Callable = None,
        cache_key: str = None,
        checkpoint: bool = None,
        state_handlers: List[Callable] = None,
        on_failure: Callable = None,
        log_stdout: bool = False,
        result: "Result" = None,
        target: Union[str, Callable] = None,
        task_run_name: Union[str, Callable] = None,
        nout: int = None,
    ):
        if type(self) is not Task:
            for attr in Task._reserved_attributes:
                if hasattr(self, attr):
                    warnings.warn(
                        f"`{type(self).__name__}` sets a `{attr}` attribute, which "
                        "will be overwritten by `prefect.Task`. Please rename this "
                        "attribute to avoid this issue."
                    )

        self.name = name or type(self).__name__
        self.slug = slug

        self.logger = logging.get_logger(self.name)

        # avoid silently iterating over a string
        if isinstance(tags, str):
            raise TypeError("Tags should be a set of tags, not a string.")
        current_tags = set(prefect.context.get("tags", set()))
        self.tags = (set(tags) if tags is not None else set()) | current_tags

        max_retries = (
            max_retries
            if max_retries is not None
            else prefect.config.tasks.defaults.max_retries
        )
        retry_delay = (
            retry_delay
            if retry_delay is not None
            else prefect.config.tasks.defaults.retry_delay
        )
        timeout = (
            timeout if timeout is not None else prefect.config.tasks.defaults.timeout
        )

        if max_retries > 0 and retry_delay is None:
            raise ValueError(
                "A datetime.timedelta `retry_delay` must be provided if max_retries > 0"
            )
        # specify not max retries because the default is false
        if retry_delay is not None and not max_retries:
            raise ValueError(
                "A `max_retries` argument greater than 0 must be provided if specifying "
                "a retry delay."
                "a retry delay."
            )
        # Make sure timeout is an integer in seconds
        if isinstance(timeout, timedelta):
            if timeout.microseconds > 0:
                warnings.warn(
                    "Task timeouts do not support a sub-second resolution; "
                    "smaller units will be ignored!",
                    stacklevel=2,
                )
            timeout = int(timeout.total_seconds())
        if timeout is not None and not isinstance(timeout, int):
            raise TypeError(
                "Only integer timeouts (representing seconds) are supported."
            )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        self.trigger = trigger or prefect.triggers.all_successful
        self.skip_on_upstream_skip = skip_on_upstream_skip

        if cache_for is None and (
            cache_validator is not None
            and cache_validator is not prefect.engine.cache_validators.never_use
        ):
            warnings.warn(
                "cache_validator provided without specifying cache expiration "
                "(cache_for); this Task will not be cached.",
                stacklevel=2,
            )

        self.cache_for = cache_for
        self.cache_key = cache_key
        default_validator = (
            prefect.engine.cache_validators.never_use
            if cache_for is None
            else prefect.engine.cache_validators.duration_only
        )
        self.cache_validator = cache_validator or default_validator
        self.checkpoint = checkpoint
        self.result = result

        self.target = target

        # if both a target and a result were provided, update the result location
        # to point at the target
        if self.target and self.result:
            if (
                getattr(self.result, "location", None)
                and self.result.location != self.target
            ):
                warnings.warn(
                    "Both `result.location` and `target` were provided. "
                    "The `target` value will be used.",
                    stacklevel=2,
                )
            self.result = self.result.copy()
            self.result.location = self.target  # type: ignore

        self.task_run_name = task_run_name  # type: ignore

        if state_handlers and not isinstance(state_handlers, collections.abc.Sequence):
            raise TypeError("state_handlers should be iterable.")
        self.state_handlers = state_handlers or []
        if on_failure is not None:
            self.state_handlers.append(
                callback_factory(on_failure, check=lambda s: s.is_failed())
            )
        self.auto_generated = False

        self.log_stdout = log_stdout

        if nout is None:
            nout = _infer_run_nout(self.run)
        self.nout = nout

        # if new task creations are being tracked, add this task
        # this makes it possible to give guidance to users that forget
        # to add tasks to a flow
        if "_unused_task_tracker" in prefect.context:
            if not isinstance(self, prefect.tasks.core.constants.Constant):
                prefect.context._unused_task_tracker.add(self)

    def __repr__(self) -> str:
        return "<Task: {self.name}>".format(self=self)

    # reimplement __hash__ because we override __eq__
    def __hash__(self) -> int:
        return id(self)

    # Run  --------------------------------------------------------------------

    def run(self) -> None:
        """
        The `run()` method is called (with arguments, if appropriate) to run a task.

        *Note:* The implemented `run` method cannot have `*args` in its signature. In addition,
        the following keywords are reserved: `upstream_tasks`, `task_args` and `mapped`.

        If a task has arguments in its `run()` method, these can be bound either by using the
        functional API and _calling_ the task instance, or by using `self.bind` directly.

        In addition to running arbitrary functions, tasks can interact with Prefect in a few ways:
        <ul><li> Return an optional result. When this function runs successfully,
            the task is considered successful and the result (if any) can be
            made available to downstream tasks. </li>
        <li> Raise an error. Errors are interpreted as failure. </li>
        <li> Raise a [signal](../engine/signals.html). Signals can include `FAIL`, `SUCCESS`,
            `RETRY`, `SKIP`, etc. and indicate that the task should be put in the indicated state.
                <ul>
                <li> `FAIL` will lead to retries if appropriate </li>
                <li> `SUCCESS` will cause the task to be marked successful </li>
                <li> `RETRY` will cause the task to be marked for retry, even if `max_retries`
                    has been exceeded </li>
                <li> `SKIP` will skip the task and possibly propogate the skip state through the
                    flow, depending on whether downstream tasks have `skip_on_upstream_skip=True`.
                </li></ul>
        </li></ul>
        """

    # Dependencies -------------------------------------------------------------

    def copy(self, **task_args: Any) -> "Task":
        """
        Creates and returns a copy of the current Task.

        Args:
            - **task_args (dict, optional): a dictionary of task attribute keyword arguments,
                these attributes will be set on the new copy

        Raises:
            - AttributeError: if any passed `task_args` are not attributes of the original

        Returns:
            - Task: a copy of the current Task, with any attributes updated from `task_args`
        """

        flow = prefect.context.get("flow", None)
        if (
            flow
            and self in flow.tasks
            and (flow.edges_to(self) or flow.edges_from(self))
        ):
            warnings.warn(
                "You are making a copy of a task that has dependencies on or to other tasks "
                "in the active flow context. The copy will not retain those dependencies.",
                stacklevel=2,
            )

        new = copy.copy(self)

        if new.slug and "slug" not in task_args:
            task_args["slug"] = new.slug + "-copy"

        # check task_args
        for attr, val in task_args.items():
            if not hasattr(new, attr):
                raise AttributeError(
                    "{0} does not have {1} as an attribute".format(self, attr)
                )
            else:
                setattr(new, attr, val)

        # if both a target and a result were provided, update the result location
        # to point at the target
        if new.target and new.result:
            if (
                getattr(new.result, "location", None)
                and new.result.location != new.target
            ):
                warnings.warn(
                    "Both `result.location` and `target` were provided. "
                    "The `target` value will be used.",
                    stacklevel=2,
                )
            new.result = new.result.copy()
            new.result.location = new.target  # type: ignore

        new.tags = copy.deepcopy(self.tags).union(set(new.tags))
        tags = set(prefect.context.get("tags", set()))
        new.tags.update(tags)

        # if new task creations are being tracked, add this task
        # this makes it possible to give guidance to users that forget
        # to add tasks to a flow. We also remove the original task,
        # as it has been "interacted" with and don't want spurious
        # warnings
        if "_unused_task_tracker" in prefect.context:
            prefect.context._unused_task_tracker.discard(self)
            if not isinstance(new, prefect.tasks.core.constants.Constant):
                prefect.context._unused_task_tracker.add(new)

        return new

    @instance_property
    def __signature__(self) -> inspect.Signature:
        """Dynamically generate the signature, replacing ``*args``/``**kwargs``
        with parameters from ``run``"""
        if not hasattr(self, "_cached_signature"):
            sig = inspect.Signature.from_callable(self.run)
            parameters = list(sig.parameters.values())
            parameters_by_kind = defaultdict(list)
            for parameter in parameters:
                parameters_by_kind[parameter.kind].append(parameter)
            parameters_by_kind[inspect.Parameter.KEYWORD_ONLY].extend(
                EXTRA_CALL_PARAMETERS
            )

            ordered_parameters = []
            ordered_kinds = (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.KEYWORD_ONLY,
                inspect.Parameter.VAR_KEYWORD,
            )
            for kind in ordered_kinds:
                ordered_parameters.extend(parameters_by_kind[kind])

            self._cached_signature = inspect.Signature(
                parameters=ordered_parameters, return_annotation="Task"
            )
        return self._cached_signature

    def __call__(
        self,
        *args: Any,
        mapped: bool = False,
        task_args: dict = None,
        upstream_tasks: Iterable[Any] = None,
        flow: "Flow" = None,
        **kwargs: Any,
    ) -> "Task":
        """
        Calling a Task instance will first create a _copy_ of the instance, and then
        bind any passed `args` / `kwargs` to the run method of the copy. This new task
        is then returned.

        Args:
            - *args: arguments to bind to the new Task's `run` method
            - **kwargs: keyword arguments to bind to the new Task's `run` method
            - mapped (bool, optional): Whether the results of these tasks should be mapped over
                with the specified keyword arguments; defaults to `False`.
                If `True`, any arguments contained within a `prefect.utilities.edges.unmapped`
                container will _not_ be mapped over.
            - task_args (dict, optional): a dictionary of task attribute keyword arguments,
                these attributes will be set on the new copy
            - upstream_tasks ([Task], optional): a list of upstream dependencies
                for the new task.  This kwarg can be used to functionally specify
                dependencies without binding their result to `run()`
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified

        Returns:
            - Task: a new Task instance
        """
        new = self.copy(**(task_args or {}))
        new.bind(
            *args, mapped=mapped, upstream_tasks=upstream_tasks, flow=flow, **kwargs
        )
        return new

    def bind(
        self,
        *args: Any,
        mapped: bool = False,
        upstream_tasks: Iterable[Any] = None,
        flow: "Flow" = None,
        **kwargs: Any,
    ) -> "Task":
        """
        Binding a task to (keyword) arguments creates a _keyed_ edge in the active Flow
        that will pass data from the arguments (whether Tasks or constants) to the
        Task's `run` method under the appropriate key. Once a Task is bound in this
        manner, the same task instance cannot be bound a second time in the same Flow.

        To bind arguments to a _copy_ of this Task instance, see `__call__`.
        Additionally, non-keyed edges can be created by passing any upstream
        dependencies through `upstream_tasks`.

        Args:
            - *args: arguments to bind to the current Task's `run` method
            - mapped (bool, optional): Whether the results of these tasks should be mapped over
                with the specified keyword arguments; defaults to `False`.
                If `True`, any arguments contained within a `prefect.utilities.edges.unmapped`
                container will _not_ be mapped over.
            - upstream_tasks ([Task], optional): a list of upstream dependencies for the
                current task.
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified
            - **kwargs: keyword arguments to bind to the current Task's `run` method

        Returns:
            - Task: the current Task instance
        """

        # this will raise an error if callargs weren't all provided
        signature = inspect.signature(self.run)
        callargs = dict(signature.bind(*args, **kwargs).arguments)  # type: Dict

        # bind() compresses all variable keyword arguments under the ** argument name,
        # so we expand them explicitly
        var_kw_arg = next(
            (p for p in signature.parameters.values() if p.kind == VAR_KEYWORD), None
        )
        if var_kw_arg:
            callargs.update(callargs.pop(var_kw_arg.name, {}))

        flow = flow or prefect.context.get("flow", None)
        if not flow:
            # Determine the task name to display which is either the function task name
            # or the initialized class where we can't know the name of the variable
            task_name = (
                self.name
                if isinstance(self, prefect.tasks.core.function.FunctionTask)
                else f"{type(self).__name__}(...)"
            )
            raise ValueError(
                f"Could not infer an active Flow context while creating edge to {self}."
                " This often means you called a task outside a `with Flow(...)` block. "
                "If you're trying to run this task outside of a Flow context, you "
                f"need to call `{task_name}.run(...)`"
            )

        self.set_dependencies(
            flow=flow,
            upstream_tasks=upstream_tasks,
            keyword_tasks=callargs,
            mapped=mapped,
        )

        tags = set(prefect.context.get("tags", set()))
        self.tags.update(tags)

        return self

    def map(
        self,
        *args: Any,
        upstream_tasks: Iterable[Any] = None,
        flow: "Flow" = None,
        task_args: dict = None,
        **kwargs: Any,
    ) -> "Task":
        """
        Map the Task elementwise across one or more Tasks. Arguments that should _not_ be
        mapped over should be placed in the `prefect.utilities.edges.unmapped` container.

        For example:
            ```
            task.map(x=X, y=unmapped(Y))
            ```
        will map over the values of `X`, but not over the values of `Y`


        Args:
            - *args: arguments to map over, which will elementwise be bound to the Task's `run`
                method
            - upstream_tasks ([Task], optional): a list of upstream dependencies
                to map over
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified
            - task_args (dict, optional): a dictionary of task attribute keyword arguments,
                these attributes will be set on the new copy
            - **kwargs: keyword arguments to map over, which will elementwise be bound to the
                Task's `run` method

        Raises:
            - AttributeError: if any passed `task_args` are not attributes of the original

        Returns:
            - Task: a new Task instance
        """
        for arg in args:
            if not hasattr(arg, "__getitem__") and not isinstance(arg, EdgeAnnotation):
                raise TypeError(
                    "Cannot map over unsubscriptable object of type {t}: {preview}...".format(
                        t=type(arg), preview=repr(arg)[:10]
                    )
                )
        task_args = task_args.copy() if task_args else {}
        task_args.setdefault("nout", None)
        new = self.copy(**task_args)
        return new.bind(
            *args, mapped=True, upstream_tasks=upstream_tasks, flow=flow, **kwargs
        )

    def set_dependencies(
        self,
        flow: "Flow" = None,
        upstream_tasks: Iterable[object] = None,
        downstream_tasks: Iterable[object] = None,
        keyword_tasks: Mapping[str, object] = None,
        mapped: bool = False,
        validate: bool = None,
    ) -> "Task":
        """
        Set dependencies for a flow either specified or in the current context using this task

        Args:
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
            flow in context if no flow is specified
            - upstream_tasks ([object], optional): A list of upstream tasks for this task
            - downstream_tasks ([object], optional): A list of downtream tasks for this task
            - keyword_tasks ({str, object}}, optional): The results of these tasks will be provided
            to this task under the specified keyword arguments.
            - mapped (bool, optional): Whether the results of the _upstream_ tasks should be
                mapped over with the specified keyword arguments
            - validate (bool, optional): Whether or not to check the validity of the flow. If not
                provided, defaults to the value of `eager_edge_validation` in your Prefect
                configuration file.

        Returns:
            - self

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        flow = flow or prefect.context.get("flow", None)
        if not flow:
            raise ValueError(
                "No Flow was passed, and could not infer an active Flow context."
            )

        flow.set_dependencies(
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            keyword_tasks=keyword_tasks,
            validate=validate,
            mapped=mapped,
        )

        return self

    def set_upstream(
        self, task: object, flow: "Flow" = None, key: str = None, mapped: bool = False
    ) -> "Task":
        """
        Sets the provided task as an upstream dependency of this task.

        Args:
            - task (object): A task or object that will be converted to a task that will be set
                as a upstream dependency of this task.
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified
            - key (str, optional): The key to be set for the new edge; the result of the
                upstream task will be passed to this task's `run()` method under this keyword
                argument.
            - mapped (bool, optional): Whether this dependency is mapped; defaults to `False`

        Returns:
            - self

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        if key is not None:
            keyword_tasks = {key: task}
            self.set_dependencies(flow=flow, keyword_tasks=keyword_tasks, mapped=mapped)
        else:
            self.set_dependencies(flow=flow, upstream_tasks=[task], mapped=mapped)

        return self

    def set_downstream(
        self, task: "Task", flow: "Flow" = None, key: str = None, mapped: bool = False
    ) -> "Task":
        """
        Sets the provided task as a downstream dependency of this task.

        Args:
            - task (Task): A task that will be set as a downstream dependency of this task.
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified
            - key (str, optional): The key to be set for the new edge; the result of this task
                will be passed to the downstream task's `run()` method under this keyword argument.
            - mapped (bool, optional): Whether this dependency is mapped; defaults to `False`

        Returns:
            - self

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        if key is not None:
            keyword_tasks = {key: self}
            task.set_dependencies(  # type: ignore
                flow=flow, keyword_tasks=keyword_tasks, mapped=mapped
            )  # type: ignore
        else:
            task.set_dependencies(flow=flow, upstream_tasks=[self], mapped=mapped)

        return self

    def inputs(self) -> Dict[str, Dict]:
        """
        Describe the inputs for this task. The result is a dictionary that maps each input to
        a `type`, `required`, and `default`. All values are inferred from the `run()`
        signature; this method can be overloaded for more precise control.

        Returns:
            - dict
        """
        inputs = {}
        for name, parameter in inspect.signature(self.run).parameters.items():
            input_type = parameter.annotation
            if input_type is inspect._empty:  # type: ignore
                input_type = Any

            input_default = parameter.default
            input_required = False
            if input_default is inspect._empty:  # type: ignore
                input_required = True
                input_default = None

            inputs[name] = dict(
                type=input_type, default=input_default, required=input_required
            )

        return inputs

    def outputs(self) -> Any:
        """
        Get the output types for this task.

        Returns:
            - Any
        """
        return_annotation = inspect.signature(self.run).return_annotation
        if return_annotation is inspect._empty:  # type: ignore
            return_annotation = Any
        return return_annotation

    # Serialization ------------------------------------------------------------

    def serialize(self) -> Dict[str, Any]:
        """
        Creates a serialized representation of this task

        Returns:
            - dict representing this task
        """
        return prefect.serialization.task.TaskSchema().dump(self)

    # Operators  ----------------------------------------------------------------

    def is_equal(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self == other`

        This can't be implemented as the __eq__() magic method because of Task
        comparisons.

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Equal().bind(self, other)

    def is_not_equal(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self != other`

        This can't be implemented as the __neq__() magic method because of Task
        comparisons.

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.NotEqual().bind(self, other)

    def not_(self) -> "Task":
        """
        Produces a Task that evaluates `not self`

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Not().bind(self)

    def or_(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self or other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Or().bind(self, other)

    # Magic Method Interactions  ----------------------------------------------------

    def __iter__(self) -> Iterator:
        if self.nout is None:
            raise TypeError(
                "Task is not iterable. If your task returns multiple results, "
                "pass `nout` to the task decorator/constructor, or provide a "
                "`Tuple` return-type annotation to your task."
            )
        return (self[i] for i in range(self.nout))

    def __getitem__(self, key: Any) -> "Task":
        """
        Produces a Task that evaluates `self[key]`

        Args:
            - key (object): the object to use as an index for this task. It will be converted
                to a Task if it isn't one already.

        Returns:
            - Task
        """
        if isinstance(key, Task):
            name = f"{self.name}[{key.name}]"
        else:
            name = f"{self.name}[{key!r}]"
        return prefect.tasks.core.operators.GetItem(
            checkpoint=self.checkpoint, name=name, result=self.result
        ).bind(self, key)

    def __or__(self, other: object) -> object:
        """
        Creates a state dependency between `self` and `other`
            `self | other --> self.set_dependencies(downstream_tasks=[other])`

        Args:
            - other (object): An object that will be converted to a Task (if it isn't one already)
                and set as a downstream dependency of this Task.

        Returns:
            - Task
        """
        self.set_dependencies(downstream_tasks=[other])
        return other

    def __mifflin__(self) -> None:  # coverage: ignore
        "Calls Dunder Mifflin"
        import webbrowser

        webbrowser.open("https://cicdw.github.io/welcome.html")

    def __ror__(self, other: object) -> "Task":
        """
        Creates a state dependency between `self` and `other`:
            `other | self --> self.set_dependencies(upstream_tasks=[other])`

        Args:
            - other (object): An object that will be converted to a Task and set as an
                upstream dependency of this Task.

        Returns:
            - Task
        """
        self.set_dependencies(upstream_tasks=[other])
        return self

    # Magic Method Operators  -----------------------------------------------------

    def __add__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self + other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Add().bind(self, other)

    def __sub__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self - other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Sub().bind(self, other)

    def __mul__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self * other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Mul().bind(self, other)

    def __truediv__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self / other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Div().bind(self, other)

    def __floordiv__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self // other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.FloorDiv().bind(self, other)

    def __mod__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self % other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Mod().bind(self, other)

    def __pow__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self ** other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Pow().bind(self, other)

    def __and__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self & other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.And().bind(self, other)

    def __radd__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other + self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Add().bind(other, self)

    def __rsub__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other - self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Sub().bind(other, self)

    def __rmul__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other * self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Mul().bind(other, self)

    def __rtruediv__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other / self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Div().bind(other, self)

    def __rfloordiv__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other // self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.FloorDiv().bind(other, self)

    def __rmod__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other % self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Mod().bind(other, self)

    def __rpow__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other ** self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.Pow().bind(other, self)

    def __rand__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `other & self`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.And().bind(other, self)

    def __gt__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self > other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.GreaterThan().bind(self, other)

    def __ge__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self >= other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.GreaterThanOrEqual().bind(self, other)

    def __lt__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self < other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.LessThan().bind(self, other)

    def __le__(self, other: object) -> "Task":
        """
        Produces a Task that evaluates `self <= other`

        Args:
            - other (object): the other operand of the operator. It will be converted to a Task
                if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.LessThanOrEqual().bind(self, other)


# All keyword-only arguments to Task.__call__, used for dynamically generating
# Signature objects for Task objects
EXTRA_CALL_PARAMETERS = [
    p
    for p in inspect.Signature.from_callable(Task.__call__).parameters.values()
    if p.kind == inspect.Parameter.KEYWORD_ONLY
]


# DEPRECATED - this is to allow backwards-compatible access to Parameters
# https://github.com/PrefectHQ/prefect/pull/2758
from .parameter import Parameter as _Parameter


class Parameter(_Parameter):
    def __new__(cls, *args, **kwargs):  # type: ignore
        warnings.warn(
            "`Parameter` has moved, please import as `prefect.Parameter`", stacklevel=2
        )
        return super().__new__(cls)
