import collections
import copy
import inspect
import uuid
import warnings
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Set, Tuple, Union

import prefect
import prefect.engine.cache_validators
import prefect.engine.signals
import prefect.triggers
from prefect.utilities import logging
from prefect.utilities.notifications import callback_factory

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611
    from prefect.engine.result_handlers import ResultHandler
    from prefect.engine.state import State

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


def _validate_run_signature(run: Callable) -> None:
    func = getattr(run, "__wrapped__", run)
    run_sig = inspect.getfullargspec(func)
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


class SignatureValidator(type):
    def __new__(cls, name: str, parents: tuple, methods: dict) -> type:
        run = methods.get("run", lambda: None)
        _validate_run_signature(run)

        # necessary to ensure classes that inherit from parent class
        # also get passed through __new__
        return type.__new__(cls, name, parents, methods)


class Task(metaclass=SignatureValidator):
    """
    The Task class which is used as the full representation of a unit of work.

    This Task class can be used directly as a first class object where it must
    be inherited from by a class which implements the `run` method.  For a more
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
        - slug (str, optional): The slug for this task, it must be unique within a given Flow
        - tags ([str], optional): A list of tags for this task
        - max_retries (int, optional): The maximum amount of times this task can be retried
        - retry_delay (timedelta, optional): The amount of time to wait until task is retried
        - timeout (int, optional): The amount of time (in seconds) to wait while
            running this task before a timeout occurs; note that sub-second resolution is not supported
        - trigger (callable, optional): a function that determines whether the task should run, based
                on the states of any upstream tasks.
        - skip_on_upstream_skip (bool, optional): if `True`, if any immediately
                upstream tasks are skipped, this task will automatically be skipped as well,
                regardless of trigger. By default, this prevents tasks from attempting to use either state or data
                from tasks that didn't run. If `False`, the task's trigger will be called as normal,
                with skips considered successes. Defaults to `True`.
        - cache_for (timedelta, optional): The amount of time to maintain a cache
            of the outputs of this task.  Useful for situations where the containing Flow
            will be rerun multiple times, but this task doesn't need to be.
        - cache_validator (Callable, optional): Validator which will determine
            whether the cache for this task is still valid (only required if `cache_for`
            is provided; defaults to `prefect.engine.cache_validators.duration_only`)
        - checkpoint (bool, optional): if this Task is successful, whether to
            store its result using the `result_handler` available during the run; defaults to the value of
            `tasks.defaults.checkpoint` in your user config
        - result_handler (ResultHandler, optional): the handler to use for
            retrieving and storing state results during execution; if not provided, will default to the
            one attached to the Flow
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the task changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the task instance, the old (prior) state, and the new
            (current) state, with the following signature:
                `state_handler(task: Task, old_state: State, new_state: State) -> Optional[State]`
            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.
        - on_failure (Callable, optional): A function with signature `fn(task: Task, state: State) -> None`
            with will be called anytime this Task enters a failure state

    Raises:
        - TypeError: if `tags` is of type `str`
        - TypeError: if `timeout` is not of type `int`
    """

    # Tasks are not iterable, though they do have a __getitem__ method
    __iter__ = None

    def __init__(
        self,
        name: str = None,
        slug: str = None,
        tags: Iterable[str] = None,
        max_retries: int = None,
        retry_delay: timedelta = None,
        timeout: int = None,
        trigger: Callable[[Set["State"]], bool] = None,
        skip_on_upstream_skip: bool = True,
        cache_for: timedelta = None,
        cache_validator: Callable = None,
        checkpoint: bool = None,
        result_handler: "ResultHandler" = None,
        state_handlers: List[Callable] = None,
        on_failure: Callable = None,
    ):

        self.name = name or type(self).__name__
        self.slug = slug

        self.id = str(uuid.uuid4())
        self.logger = logging.get_logger("Task")

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
                "cache_validator provided without specifying cache expiration (cache_for); this Task will not be cached."
            )

        self.cache_for = cache_for
        default_validator = (
            prefect.engine.cache_validators.never_use
            if cache_for is None
            else prefect.engine.cache_validators.duration_only
        )
        self.cache_validator = cache_validator or default_validator
        self.checkpoint = (
            checkpoint
            if checkpoint is not None
            else prefect.config.tasks.defaults.checkpoint
        )
        self.result_handler = result_handler

        if state_handlers and not isinstance(state_handlers, collections.Sequence):
            raise TypeError("state_handlers should be iterable.")
        self.state_handlers = state_handlers or []
        if on_failure is not None:
            self.state_handlers.append(
                callback_factory(on_failure, check=lambda s: s.is_failed())
            )

    def __repr__(self) -> str:
        return "<Task: {self.name}>".format(self=self)

    # reimplement __hash__ because we override __eq__
    def __hash__(self) -> int:
        return id(self)

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        """
        Args:
            - value (str): a UUID-formatted string
        """
        try:
            uuid.UUID(value)
        except Exception:
            raise ValueError("Badly formatted UUID string: {}".format(value))
        self._id = value

    # Run  --------------------------------------------------------------------

    def run(self) -> None:
        """
        The `run()` method is called (with arguments, if appropriate) to run a task.

        *Note:* The implemented `run` method cannot have `*args` in its signature. In addition,
        the following keywords are reserved: `upstream_tasks`, `task_args` and `mapped`.

        If a task has arguments in its `run()` method, these can be bound either by using the functional
        API and _calling_ the task instance, or by using `self.bind` directly.

        In addition to running arbitrary functions, tasks can interact with Prefect in a few ways:
        <ul><li> Return an optional result. When this function runs successfully,
            the task is considered successful and the result (if any) can be
            made available to downstream tasks. </li>
        <li> Raise an error. Errors are interpreted as failure. </li>
        <li> Raise a [signal](../engine/signals.html). Signals can include `FAIL`, `SUCCESS`, `RETRY`, `SKIP`, etc.
            and indicate that the task should be put in the indicated state.
                <ul>
                <li> `FAIL` will lead to retries if appropriate </li>
                <li> `SUCCESS` will cause the task to be marked successful </li>
                <li> `RETRY` will cause the task to be marked for retry, even if `max_retries`
                    has been exceeded </li>
                <li> `SKIP` will skip the task and possibly propogate the skip state through the
                    flow, depending on whether downstream tasks have `skip_on_upstream_skip=True`. </li></ul>
        </li></ul>
        """
        pass

    # Dependencies -------------------------------------------------------------

    def copy(self, **task_args: Any) -> "Task":
        """
        Creates and returns a copy of the current Task.

        Args:
            - **task_args (dict, optional): a dictionary of task attribute keyword arguments, these attributes
                will be set on the new copy

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
                "in the active flow context. The copy will not retain those dependencies."
            )

        new = copy.copy(self)

        # check task_args
        for attr, val in task_args.items():
            if not hasattr(new, attr):
                raise AttributeError(
                    "{0} does not have {1} as an attribute".format(self, attr)
                )
            else:
                setattr(new, attr, val)

        # assign new id
        new.id = str(uuid.uuid4())

        new.tags = copy.deepcopy(self.tags).union(set(new.tags))
        tags = set(prefect.context.get("tags", set()))
        new.tags.update(tags)

        return new

    def __call__(
        self,
        *args: Any,
        mapped: bool = False,
        task_args: dict = None,
        upstream_tasks: Iterable[Any] = None,
        flow: "Flow" = None,
        **kwargs: Any
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
                If `True`, any arguments contained within a `prefect.utilities.tasks.unmapped`
                container will _not_ be mapped over.
            - task_args (dict, optional): a dictionary of task attribute keyword arguments, these attributes
                will be set on the new copy
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
        **kwargs: Any
    ) -> "Task":
        """
        Binding a task to (keyword) arguments creates a _keyed_ edge in the active Flow
        which will pass data from the arguments (whether Tasks or constants) to the
        Task's `run` method under the appropriate key. Once a Task is bound in this
        manner, the same task instance cannot be bound a second time in the same Flow.

        To bind arguments to a _copy_ of this Task instance, see `__call__`.
        Additionally, non-keyed edges can be created by passing any upstream
        dependencies through `upstream_tasks`.

        Args:
            - *args: arguments to bind to the current Task's `run` method
            - mapped (bool, optional): Whether the results of these tasks should be mapped over
                with the specified keyword arguments; defaults to `False`.
                If `True`, any arguments contained within a `prefect.utilities.tasks.unmapped`
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
            raise ValueError("Could not infer an active Flow context.")

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
        **kwargs: Any
    ) -> "Task":
        """
        Map the Task elementwise across one or more Tasks. Arguments which should _not_ be mapped over
        should be placed in the `prefect.utilities.tasks.unmapped` container.

        For example:
            ```
            task.map(x=X, y=unmapped(Y))
            ```
        will map over the values of `X`, but not over the values of `Y`


        Args:
            - *args: arguments to map over, which will elementwise be bound to the Task's `run` method
            - upstream_tasks ([Task], optional): a list of upstream dependencies
                to map over
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified
            - **kwargs: keyword arguments to map over, which will elementwise be bound to the Task's `run` method

        Returns: - Task: a new Task instance
        """
        new = self.copy()
        return new.bind(
            *args, mapped=True, upstream_tasks=upstream_tasks, flow=flow, **kwargs
        )

    def set_dependencies(
        self,
        flow: "Flow" = None,
        upstream_tasks: Iterable[object] = None,
        downstream_tasks: Iterable[object] = None,
        keyword_tasks: Dict[str, object] = None,
        mapped: bool = False,
        validate: bool = True,
    ) -> None:
        """
        Set dependencies for a flow either specified or in the current context using this task

        Args:
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
            flow in context if no flow is specified
            - upstream_tasks ([object], optional): A list of upstream tasks for this task
            - downstream_tasks ([object], optional): A list of downtream tasks for this task
            - keyword_tasks ({str, object}}, optional): The results of these tasks will be provided
            to the task under the specified keyword arguments.
            - mapped (bool, optional): Whether the results of these tasks should be mapped over
                with the specified keyword arguments
            - validate (bool, optional): Whether or not to check the validity of the flow

        Returns:
            - None

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

    def set_upstream(self, task: object, flow: "Flow" = None) -> None:
        """
        Sets the provided task as an upstream dependency of this task.

        Equivalent to: `self.set_dependencies(upstream_tasks=[task])`

        Args:
            - task (object): A task or object that will be converted to a task that will be set
                as a upstream dependency of this task.
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        self.set_dependencies(flow=flow, upstream_tasks=[task])

    def set_downstream(self, task: object, flow: "Flow" = None) -> None:
        """
        Sets the provided task as a downstream dependency of this task.

        Equivalent to: `self.set_dependencies(downstream_tasks=[task])`

        Args:
            - task (object): A task or object that will be converted to a task that will be set
                as a downstream dependency of this task.
            - flow (Flow, optional): The flow to set dependencies on, defaults to the current
                flow in context if no flow is specified

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        self.set_dependencies(flow=flow, downstream_tasks=[task])

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

    # Magic Method Interactions  ----------------------------------------------------

    def __getitem__(self, key: Any) -> "Task":
        """
        Produces a Task that evaluates `self[key]`

        Args:
            - key (object): the object to use an an index for this task. It will be converted
                to a Task if it isn't one already.

        Returns:
            - Task
        """
        return prefect.tasks.core.operators.GetItem().bind(self, key)

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

    # Maginc Method Operators  -----------------------------------------------------

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


class Parameter(Task):
    """
    A Parameter is a special task that defines a required flow input.

    A parameter's "slug" is automatically -- and immutably -- set to the parameter name.
    Flows enforce slug uniqueness across all tasks, so this ensures that the flow has
    no other parameters by the same name.

    *Note*: Parameters should always be JSON-compatible objects, and will always be checkpointed
    during execution using the `JSONResultHandler`.

    Args:
        - name (str): the Parameter name.
        - required (bool, optional): If True, the Parameter is required and the default
            value is ignored.
        - default (any, optional): A default value for the parameter. If the default
            is not None, the Parameter will not be required.
        - tags ([str], optional): A list of tags for this parameter

    """

    def __init__(
        self,
        name: str,
        default: Any = None,
        required: bool = True,
        tags: Iterable[str] = None,
    ):
        if default is not None:
            required = False

        self.required = required
        self.default = default

        from prefect.engine.result_handlers import JSONResultHandler

        super().__init__(
            name=name,
            slug=name,
            tags=tags,
            checkpoint=True,
            result_handler=JSONResultHandler(),
        )

    def __repr__(self) -> str:
        return "<Parameter: {self.name}>".format(self=self)

    @property  # type: ignore
    def name(self) -> str:  # type: ignore
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if hasattr(self, "_name"):
            raise AttributeError("Parameter name can not be changed")
        self._name = value  # pylint: disable=W0201

    @property  # type: ignore
    def slug(self) -> str:  # type: ignore
        """
        A Parameter slug is always the same as its name. This information is used by
        Flow objects to enforce parameter name uniqueness.
        """
        return self.name

    @slug.setter
    def slug(self, value: str) -> None:
        # slug is a property, so it's not actually set by this method, but the superclass
        # attempts to set it and we need to allow that without error.
        if value != self.name:
            raise AttributeError("Parameter slug must be the same as its name.")

    def run(self) -> Any:
        params = prefect.context.get("parameters") or {}
        if self.required and self.name not in params:
            self.logger.debug(
                'Parameter "{}" was required but not provided.'.format(self.name)
            )
            raise prefect.engine.signals.FAIL(
                'Parameter "{}" was required but not provided.'.format(self.name)
            )
        return params.get(self.name, self.default)

    # Serialization ------------------------------------------------------------

    def serialize(self) -> Dict[str, Any]:
        """
        Creates a serialized representation of this parameter

        Returns:
            - dict representing this parameter
        """
        return prefect.serialization.task.ParameterSchema().dump(self)
