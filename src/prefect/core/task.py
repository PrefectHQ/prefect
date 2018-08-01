import inspect
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Tuple

import prefect
import prefect.engine.cache_validators
import prefect.engine.signals
import prefect.triggers
from prefect.environments import Environment
from prefect.utilities.json import Serializable, to_qualified_name

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611
    from prefect.engine.state import State

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


class SignatureValidator(type):
    def __new__(cls, name, parents, methods):
        run = methods.get("run", lambda: None)
        run_sig = inspect.getfullargspec(run)
        if run_sig.varargs:
            raise ValueError(
                "Tasks with variable positional arguments (*args) are not "
                "supported, because all Prefect arguments are stored as "
                "keywords. As a workaround, consider modifying the run() "
                "method to accept **kwargs and feeding the values "
                "to *args."
            )
        # necessary to ensure classes that inherit from parent class
        # also get passed through __new__
        return type.__new__(cls, name, parents, methods)


class Task(Serializable, metaclass=SignatureValidator):
    def __init__(
        self,
        name: str = None,
        slug: str = None,
        description: str = None,
        group: str = None,
        tags: Iterable[str] = None,
        max_retries: int = 0,
        retry_delay: timedelta = timedelta(minutes=1),
        timeout: timedelta = None,
        trigger: Callable[[Dict["Task", "State"]], bool] = None,
        propagate_skip: bool = False,
        cache_for: timedelta = None,
        cache_validator: Callable = None,
    ) -> None:

        self.name = name or type(self).__name__
        self.slug = slug
        self.description = description

        self.group = str(group or prefect.context.get("_group", ""))

        # avoid silently iterating over a string
        if isinstance(tags, str):
            raise TypeError("Tags should be a set of tags, not a string.")
        self.tags = set(tags or prefect.context.get("_tags", []))

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        self.trigger = trigger or prefect.triggers.all_successful
        self.propagate_skip = propagate_skip

        self.cache_for = cache_for
        self.cache_validator = cache_validator or prefect.engine.cache_validators.never_use

    def __repr__(self) -> str:
        return "<Task: {self.name}>".format(self=self)

    # Run  --------------------------------------------------------------------

    def inputs(self) -> Tuple[str, ...]:
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
            3. Raise a signal. Signals can include FAIL, SUCCESS, WAIT, etc.
                and indicate that the task should be put in the indicated
                state.
                - FAIL will lead to retries if appropriate
                - WAIT will end execution and skip all downstream tasks with
                    state WAITING_FOR_UPSTREAM (unless appropriate triggers
                    are set). The task can be run again and should check
                    context.is_waiting to see if it was placed in a WAIT.
        """
        raise NotImplementedError()

    # Dependencies -------------------------------------------------------------

    def __call__(
        self, *args: object, upstream_tasks: Iterable[object] = None, **kwargs: object
    ) -> "Task":
        # this will raise an error if callargs weren't all provided
        signature = inspect.signature(self.run)
        callargs = dict(signature.bind(*args, **kwargs).arguments)  # type: Dict

        # bind() compresses all variable keyword arguments under the ** argument name,
        # so we expand them explicitly
        var_kw_arg = next(
            (p for p in signature.parameters.values() if p.kind == VAR_KEYWORD), None
        )
        callargs.update(callargs.pop(var_kw_arg, {}))

        flow = prefect.context.get("_flow", None)
        if not flow:
            raise ValueError("Could not infer an active Flow context.")

        self.set_dependencies(
            flow=flow, upstream_tasks=upstream_tasks, keyword_tasks=callargs
        )

        return self

    def set_dependencies(
        self,
        flow: "Flow" = None,
        upstream_tasks: Iterable[object] = None,
        downstream_tasks: Iterable[object] = None,
        keyword_tasks: Dict[str, object] = None,
        validate: bool = True,
    ) -> None:

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
        )

    # Serialization ------------------------------------------------------------

    def serialize(self, task: "Task") -> Dict[str, Any]:
        return dict(
            name=task.name,
            slug=task.slug,
            type=to_qualified_name(type(task)),
            description=task.description,
            max_retries=task.max_retries,
            retry_delay=task.retry_delay,
            timeout=task.timeout,
            trigger=task.trigger,
            propagate_skip=task.propagate_skip,
            checkpoint=task.checkpoint,
        )


class Parameter(Task):
    """
    A Parameter is a special task that defines a required flow input.

    A parameter's "slug" is automatically -- and immutably -- set to the parameter name.
    Flows enforce slug uniqueness across all tasks, so this ensures that the flow has
    no other parameters by the same name.
    """

    def __init__(self, name: str, default: Any = None, required: bool = True) -> None:
        """
        Args:
            name (str): the Parameter name.

            required (bool): If True, the Parameter is required and the default
                value is ignored.

            default (any): A default value for the parameter. If the default
                is not None, the Parameter will not be required.
        """
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
        params = prefect.context.get("_parameters", {})
        if self.required and self.name not in params:
            raise prefect.engine.signals.FAIL(
                'Parameter "{}" was required but not provided.'.format(self.name)
            )
        return params.get(self.name, self.default)

    def info(self) -> Dict[str, Any]:
        info = super().info()
        info.update(required=self.required, default=self.default)
        return info
