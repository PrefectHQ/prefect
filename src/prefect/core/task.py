# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import copy
import inspect
import warnings
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Tuple

import prefect
import prefect.engine.cache_validators
import prefect.engine.signals
import prefect.triggers
from prefect.utilities.json import Serializable, to_qualified_name

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611
    from prefect.engine.state import State

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


def _validate_run_signature(run):
    run_sig = inspect.getfullargspec(run)
    if run_sig.varargs:
        raise ValueError(
            "Tasks with variable positional arguments (*args) are not "
            "supported, because all Prefect arguments are stored as "
            "keywords. As a workaround, consider modifying the run() "
            "method to accept **kwargs and feeding the values "
            "to *args."
        )

    if "upstream_tasks" in run_sig.args:
        raise ValueError(
            "Tasks cannot have an `upstream_tasks` argument name; this is a reserved keyword argument."
        )


class SignatureValidator(type):
    def __new__(cls, name, parents, methods):
        run = methods.get("run", lambda: None)
        _validate_run_signature(run)

        # necessary to ensure classes that inherit from parent class
        # also get passed through __new__
        return type.__new__(cls, name, parents, methods)


class Task(Serializable, metaclass=SignatureValidator):
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

    *Note:* The implemented `run` method cannot have `*args` in its signature.

    An instance of a `Task` can be used functionally to generate other task instances
    with the same attributes but with different values bound to their `run` methods.

    Example:
    ```python
    class AddTask(Task):
        def run(self, x, y):
            return x + y

    a = AddTask()

    with Flow() as f:
        t1 = a(1, 2) # t1 != a
        t2 = a(5, 7) # t2 != a
    ```

    To bind values to a Task's run method imperatively, see `Task.bind`.

    Args:
        - name (str, optional): The name of this task
        - slug (str, optional): The slug for this task, it must be unique withing a given Flow
        - description (str, optional): Descriptive information about this task
        - tags ([str], optional): A list of tags for this task
        - max_retries (int, optional): The maximum amount of times this task can be retried
        - retry_delay (timedelta, optional): The amount of time to wait until task is retried
        - timeout (timedelta, optional): The amount of time to wait while running before a timeout occurs
        - trigger (callable, optional): a function that determines whether the task should run, based
                on the states of any upstream tasks.
        - skip_on_upstream_skip (bool, optional): if True and any upstream tasks skipped, this task
                will automatically be skipped as well. By default, this prevents tasks from
                attempting to use either state or data from tasks that didn't run. if False,
                the task's trigger will be called as normal; skips are considered successes.
        - cache_for (timedelta, optional): The amount of time to maintain cache
        - cache_validator (Callable, optional): Validator telling what to cache

    Raises:
        - TypeError: if `tags` is of type `str`
    """

    # Tasks are not iterable, though they do have a __getitem__ method
    __iter__ = None

    def __init__(
        self,
        name: str = None,
        slug: str = None,
        description: str = None,
        tags: Iterable[str] = None,
        max_retries: int = 0,
        retry_delay: timedelta = timedelta(minutes=1),
        timeout: timedelta = None,
        trigger: Callable[[Dict["Task", "State"]], bool] = None,
        skip_on_upstream_skip: bool = True,
        cache_for: timedelta = None,
        cache_validator: Callable = None,
    ) -> None:
        self.name = name or type(self).__name__
        self.slug = slug
        self.description = description

        # avoid silently iterating over a string
        if isinstance(tags, str):
            raise TypeError("Tags should be a set of tags, not a string.")
        current_tags = set(prefect.context.get("_tags", set()))
        self.tags = (set(tags) if tags is not None else set()) | current_tags

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        self.trigger = trigger or prefect.triggers.all_successful
        self.skip_on_upstream_skip = skip_on_upstream_skip

        if cache_for is None and cache_validator is not None:
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

    def __repr__(self) -> str:
        return "<Task: {self.name}>".format(self=self)

    # reimplement __hash__ because we override __eq__
    def __hash__(self):
        return id(self)

    # Run  --------------------------------------------------------------------

    def inputs(self) -> Tuple[str, ...]:
        """
        Get the inputs for this task

        Returns:
            - tuple of strings representing the inputs for this task
        """
        return tuple(inspect.signature(self.run).parameters.keys())

    def run(self):  # type: ignore
        """
        The main entrypoint for tasks.

        In addition to running arbitrary functions, tasks can interact with
        Prefect in a few ways:
            1. Return an optional result. When this function runs successfully,
                the task is considered successful and the result (if any) is
                made available to downstream edges.
            2. Raise an error. Errors are interpreted as failure.
            3. Raise a signal. Signals can include `FAIL`, `SUCCESS`, `WAIT`, etc.
                and indicate that the task should be put in the indicated
                state.
                - `FAIL` will lead to retries if appropriate
                - `WAIT` will end execution and skip all downstream tasks with
                    state WAITING_FOR_UPSTREAM (unless appropriate triggers
                    are set). The task can be run again and should check
                    context.is_waiting to see if it was placed in a WAIT.
        """
        raise NotImplementedError()

    # Dependencies -------------------------------------------------------------

    def copy(self):

        flow = prefect.context.get("_flow", None)
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

        new.tags = copy.deepcopy(self.tags)
        tags = set(prefect.context.get("_tags", set()))
        new.tags.update(tags)

        return new

    def __call__(
        self, *args: object, upstream_tasks: Iterable[object] = None, **kwargs: object
    ) -> "Task":
        """
        Calling a Task instance will first create a _copy_ of the instance, and then
        bind any passed `args` / `kwargs` to the run method of the copy. This new task
        is then returned.

        Args:
            - *args: arguments to bind to the new Task's `run` method
            - **kwargs: keyword arguments to bind to the new Task's `run` method
            - upstream_tasks ([Task], optional): a list of upstream dependencies
                for the new task.  This kwarg can be used to functionally specify
                dependencies without binding their result to `run()`

        Returns:
            - Task: a new Task instance
        """
        new = self.copy()
        new.bind(*args, upstream_tasks=upstream_tasks, **kwargs)
        return new

    def _get_bound_signature(self, *args, **kwargs):
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

        return callargs

    def bind(
        self, *args: object, upstream_tasks: Iterable[object] = None, **kwargs: object
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
            - upstream_tasks ([Task], optional): a list of upstream dependencies for the
                current task.
            - **kwargs: keyword arguments to bind to the current Task's `run` method

        Returns: - Task: the current Task instance
        """

        callargs = self._get_bound_signature(*args, **kwargs)
        flow = prefect.context.get("_flow", None)
        if not flow:
            raise ValueError("Could not infer an active Flow context.")

        self.set_dependencies(
            flow=flow, upstream_tasks=upstream_tasks, keyword_tasks=callargs
        )

        tags = set(prefect.context.get("_tags", set()))
        self.tags.update(tags)

        return self

    def map(
        self,
        *args: object,
        upstream_tasks: Iterable[object] = None,
        unmapped: Dict[Any, Any] = None,
        **kwargs: object
    ) -> "Task":
        """
        Map the Task elementwise across one or more Tasks.

        Args:
            - *args: arguments to map over, which will elementwise be bound to the Task's `run` method
            - upstream_tasks ([Task], optional): a list of upstream dependencies
                to map over
            - unmapped (dict, optional): a dictionary of "key" -> Task
                specifying keyword arguments which will _not_ be mapped over.  The special key `None` is reserved for
                optionally including a _list_ of upstream task dependencies
            - **kwargs: keyword arguments to map over, which will elementwise be bound to the Task's `run` method

        Returns: - Task: a new Task instance
        """
        ## collect arguments / keyword arguments / upstream dependencies which will _not_ be mapped over
        unmapped = unmapped or {}
        unmapped_upstream = unmapped.pop(
            None, None
        )  # possible list of upstream dependencies

        new = self.copy()

        # bind all appropriate tasks to the run() method
        full_kwargs = dict(kwargs, **unmapped)
        callargs = new._get_bound_signature(*args, **full_kwargs)

        ## collect arguments / keyword arguments which _will_ be mapped over
        mapped = {k: v for k, v in callargs.items() if (v in args) or (k in kwargs)}

        if upstream_tasks is not None:
            mapped[None] = upstream_tasks  # add in mapped upstream dependencies

        unmapped_callargs = {
            k: v for k, v in callargs.items() if (v not in args) and (k not in kwargs)
        }

        flow = prefect.context.get("_flow", None)
        if not flow:
            raise ValueError("Could not infer an active Flow context.")

        new.set_dependencies(
            flow=flow,
            upstream_tasks=unmapped_upstream,
            keyword_tasks=unmapped_callargs,
            mapped_tasks=mapped,
        )

        tags = set(prefect.context.get("_tags", set()))
        new.tags.update(tags)

        return new

    def set_dependencies(
        self,
        flow: "Flow" = None,
        upstream_tasks: Iterable[object] = None,
        downstream_tasks: Iterable[object] = None,
        keyword_tasks: Dict[str, object] = None,
        mapped_tasks=None,
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
            - mapped_tasks ({str, object}}, optional): The results of these
                tasks will be mapped over under the specified keyword arguments, with `None` specifying a list of upstream dependencies which will also be mapped over
            - validate (bool, optional): Whether or not to check the validity of the flow

        Returns:
            - None

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        flow = flow or prefect.context.get("_flow", None)
        if not flow:
            raise ValueError(
                "No Flow was passed, and could not infer an active Flow context."
            )

        flow.set_dependencies(  # type: ignore
            task=self,
            upstream_tasks=upstream_tasks,
            downstream_tasks=downstream_tasks,
            keyword_tasks=keyword_tasks,
            validate=validate,
            mapped_tasks=mapped_tasks,
        )

    def set_upstream(self, task: object) -> None:
        """
        Sets the provided task as an upstream dependency of this task.

        Equivalent to: `self.set_dependencies(upstream_tasks=[task])`

        Args:
            - task (object): A task or object that will be converted to a task that will be set
                as a upstream dependency of this task.

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        self.set_dependencies(upstream_tasks=[task])

    def set_downstream(self, task: object) -> None:
        """
        Sets the provided task as a downstream dependency of this task.

        Equivalent to: `self.set_dependencies(downstream_tasks=[task])`

        Args:
            - task (object): A task or object that will be converted to a task that will be set
                as a downstream dependency of this task.

        Raises:
            - ValueError: if no flow is specified and no flow can be found in the current context
        """
        self.set_dependencies(downstream_tasks=[task])

    # Serialization ------------------------------------------------------------

    def serialize(self) -> Dict[str, Any]:
        """
        Creates a serialized representation of this task

        Returns:
            - dict representing this task
        """
        return dict(
            name=self.name,
            slug=self.slug,
            description=self.description,
            tags=self.tags,
            type=to_qualified_name(type(self)),
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            timeout=self.timeout,
            trigger=self.trigger,
            skip_on_upstream_skip=self.skip_on_upstream_skip,
            cache_for=self.cache_for,
            cache_validator=self.cache_validator,
        )

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

    def __or__(self, other: object) -> "Task":
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

    Args:
        - name (str): the Parameter name.
        - required (bool, optional): If True, the Parameter is required and the default
            value is ignored.
        - default (any, optional): A default value for the parameter. If the default
            is not None, the Parameter will not be required.
    """

    def __init__(self, name: str, default: Any = None, required: bool = True) -> None:
        if default is not None:
            required = False

        self.required = required
        self.default = default

        super().__init__(name=name, slug=name)

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
        params = prefect.context.get("_parameters") or {}
        if self.required and self.name not in params:
            raise prefect.engine.signals.FAIL(
                'Parameter "{}" was required but not provided.'.format(self.name)
            )
        return params.get(self.name, self.default)

    def info(self) -> Dict[str, Any]:
        info = super().info()
        info.update(required=self.required, default=self.default)
        return info
