"""
Module containing the base workflow class and decorator - for most use cases, using the [`@flow` decorator][prefect.flows.flow] is preferred.
"""
# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645

import inspect
import os
import warnings
from functools import partial, update_wrapper
from tempfile import NamedTemporaryFile
from typing import (
    Any,
    AnyStr,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    List,
    NoReturn,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

import pydantic
from fastapi.encoders import jsonable_encoder
from pydantic.decorator import ValidatedFunction
from typing_extensions import ParamSpec

from prefect import State
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.exceptions import (
    MissingFlowError,
    ParameterTypeError,
    UnspecifiedFlowError,
)
from prefect.logging import get_logger
from prefect.orion.schemas.core import raise_on_invalid_name
from prefect.task_runners import BaseTaskRunner, ConcurrentTaskRunner
from prefect.utilities.asyncutils import is_async_fn
from prefect.utilities.callables import (
    get_call_parameters,
    parameter_schema,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import listrepr
from prefect.utilities.hashing import file_hash

T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the flow

logger = get_logger("flows")


@PrefectObjectRegistry.register_instances
class Flow(Generic[P, R]):
    """
    A Prefect workflow definition.

    !!! note
        We recommend using the [`@flow` decorator][prefect.flows.flow] for most use-cases.

    Wraps a function with an entrypoint to the Prefect engine. To preserve the input
    and output types, we use the generic type variables `P` and `R` for "Parameters" and
    "Returns" respectively.

    Args:
        fn: The function defining the workflow.
        name: An optional name for the flow; if not provided, the name will be inferred
            from the given function.
        version: An optional version string for the flow; if not provided, we will
            attempt to create a version string as a hash of the file containing the
            wrapped function; if the file cannot be located, the version will be null.
        task_runner: An optional task runner to use for task execution within the flow;
            if not provided, a `ConcurrentTaskRunner` will be used.
        description: An optional string description for the flow; if not provided, the
            description will be pulled from the docstring for the decorated function.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the flow. If the flow exceeds this runtime, it will be marked as failed.
            Flow execution may continue until the next task is called.
        validate_parameters: By default, parameters passed to flows are validated by
            Pydantic. This will check that input values conform to the annotated types
            on the function. Where possible, values will be coerced into the correct
            type; for example, if a parameter is defined as `x: int` and "5" is passed,
            it will be resolved to `5`. If set to `False`, no validation will be
            performed on flow parameters.
        retries: An optional number of times to retry on flow run failure.
        retry_delay_seconds: An optional number of seconds to wait before retrying the
            flow after failure. This is only applicable if `retries` is nonzero.
    """

    # NOTE: These parameters (types, defaults, and docstrings) should be duplicated
    #       exactly in the @flow decorator
    def __init__(
        self,
        fn: Callable[P, R],
        name: str = None,
        version: str = None,
        retries: int = 0,
        retry_delay_seconds: Union[int, float] = 0,
        task_runner: Union[Type[BaseTaskRunner], BaseTaskRunner] = ConcurrentTaskRunner,
        description: str = None,
        timeout_seconds: Union[int, float] = None,
        validate_parameters: bool = True,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        # Validate name if given
        if name:
            raise_on_invalid_name(name)

        self.name = name or fn.__name__.replace("_", "-")
        task_runner = task_runner or ConcurrentTaskRunner()
        self.task_runner = (
            task_runner() if isinstance(task_runner, type) else task_runner
        )

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = is_async_fn(self.fn)

        # Version defaults to a hash of the function's file
        flow_file = inspect.getsourcefile(self.fn)
        if not version:
            try:
                version = file_hash(flow_file)
            except (FileNotFoundError, TypeError, OSError):
                pass  # `getsourcefile` can return null values and "<stdin>" for objects in repls
        self.version = version

        self.timeout_seconds = float(timeout_seconds) if timeout_seconds else None

        # FlowRunPolicy settings
        # TODO: We can instantiate a `FlowRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

        self.parameters = parameter_schema(self.fn)
        self.should_validate_parameters = validate_parameters

        if self.should_validate_parameters:
            # Try to create the validated function now so that incompatibility can be
            # raised at declaration time rather than at runtime
            # We cannot, however, store the validated function on the flow because it
            # is not picklable in some environments
            try:
                ValidatedFunction(self.fn, config=None)
            except pydantic.ConfigError as exc:
                raise ValueError(
                    "Flow function is not compatible with `validate_parameters`. "
                    "Disable validation or change the argument names."
                ) from exc

        # Check for collision in the registry
        registry = PrefectObjectRegistry.get()

        if registry and any(
            other
            for other in registry.get_instances(Flow)
            if other.name == self.name and id(other.fn) != id(self.fn)
        ):
            file = inspect.getsourcefile(self.fn)
            line_number = inspect.getsourcelines(self.fn)[1]
            warnings.warn(
                f"A flow named {self.name!r} and defined at '{file}:{line_number}' "
                "conflicts with another flow. Consider specifying a unique `name` "
                "parameter in the flow definition:\n\n "
                "`@flow(name='my_unique_name', ...)`"
            )

    def with_options(
        self,
        *,
        name: str = None,
        version: str = None,
        retries: int = 0,
        retry_delay_seconds: Union[int, float] = 0,
        description: str = None,
        task_runner: Union[Type[BaseTaskRunner], BaseTaskRunner] = None,
        timeout_seconds: Union[int, float] = None,
        validate_parameters: bool = None,
    ):
        """
        Create a new flow from the current object, updating provided options.

        Args:
            name: A new name for the flow.
            version: A new version for the flow.
            description: A new description for the flow.
            task_runner: A new task runner for the flow.
            timeout_seconds: A new number of seconds to fail the flow after if still
                running.
            validate_parameters: A new value indicating if flow calls should validate
                given parameters.

        Returns:
            A new `Flow` instance.

        Examples:

            Create a new flow from an existing flow and update the name:

            >>> @flow(name="My flow")
            >>> def my_flow():
            >>>     return 1
            >>>
            >>> new_flow = my_flow.with_options(name="My new flow")

            Create a new flow from an existing flow, update the task runner, and call
            it without an intermediate variable:

            >>> from prefect.task_runners import SequentialTaskRunner
            >>>
            >>> @flow
            >>> def my_flow(x, y):
            >>>     return x + y
            >>>
            >>> state = my_flow.with_options(task_runner=SequentialTaskRunner)(1, 3)
            >>> assert state.result() == 4

        """
        return Flow(
            fn=self.fn,
            name=name or self.name,
            description=description or self.description,
            version=version or self.version,
            task_runner=task_runner or self.task_runner,
            timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else self.timeout_seconds
            ),
            validate_parameters=(
                validate_parameters
                if validate_parameters is not None
                else self.should_validate_parameters
            ),
        )

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for compatibility with the flow by attempting to cast the inputs to the
        associated types specified by the function's type annotations.

        Returns:
            A new dict of parameters that have been cast to the appropriate types

        Raises:
            FlowParameterError: if the provided parameters are not valid
        """
        validated_fn = ValidatedFunction(self.fn, config=None)
        args, kwargs = parameters_to_args_kwargs(self.fn, parameters)

        validation_err = None
        try:
            model = validated_fn.init_model_instance(*args, **kwargs)
        except pydantic.ValidationError as exc:
            # We capture the pydantic exception and raise our own because the pydantic
            # exception is not picklable when using a cythonized pydantic installation
            validation_err = ParameterTypeError(str(exc))

        if validation_err:
            # Raise the valdiation error outside of the `except` so the pydandic
            # internals are not included
            raise validation_err

        # Get the updated parameter dict with cast values from the model
        cast_parameters = {
            k: v
            for k, v in model._iter()
            if k in model.__fields_set__ or model.__fields__[k].default_factory
        }
        return cast_parameters

    def serialize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parameters to a serializable form.

        Uses FastAPI's `jsonable_encoder` to convert to JSON compatible objects without
        converting everything directly to a string. This maintains basic types like
        integers during API roundtrips.
        """
        serialized_parameters = {}
        for key, value in parameters.items():
            try:
                serialized_parameters[key] = jsonable_encoder(value)
            except (TypeError, ValueError):
                logger.debug(
                    f"Parameter {key!r} for flow {self.name!r} is of unserializable "
                    f"type {type(value).__name__!r} and will not be stored "
                    "in the backend."
                )
                serialized_parameters[key] = f"<{type(value).__name__}>"
        return serialized_parameters

    @overload
    def __call__(self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs) -> T:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]", *args: P.args, **kwargs: P.kwargs
    ) -> Awaitable[T]:
        ...

    @overload
    def __call__(self: "Flow[P, T]", *args: P.args, **kwargs: P.kwargs) -> T:
        ...

    def __call__(
        self,
        *args: "P.args",
        **kwargs: "P.kwargs",
    ):
        """
        Run the flow and return its result.


        Flow parameter values must be serializable by Pydantic.

        If writing an async flow, this call must be awaited.

        This will create a new flow run in the API.

        Args:
            *args: Arguments to run the flow with.
            **kwargs: Keyword arguments to run the flow with.

        Returns:
            The result of the flow run.

        Examples:

            Define a flow

            >>> @flow
            >>> def my_flow(name):
            >>>     print(f"hello {name}")
            >>>     return f"goodbye {name}"

            Run a flow

            >>> my_flow("marvin")
            hello marvin
            "goodbye marvin"

            Run a flow with additional tags

            >>> from prefect import tags
            >>> with tags("db", "blue"):
            >>>     my_flow("foo")
        """
        from prefect.engine import enter_flow_run_engine_from_flow_call

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_flow_run_engine_from_flow_call(
            self, parameters, return_type="result"
        )

    @overload
    def _run(self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs) -> State[T]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def _run(
        self: "Flow[P, Coroutine[Any, Any, T]]", *args: P.args, **kwargs: P.kwargs
    ) -> Awaitable[T]:
        ...

    @overload
    def _run(self: "Flow[P, T]", *args: P.args, **kwargs: P.kwargs) -> State[T]:
        ...

    def _run(
        self,
        *args: "P.args",
        **kwargs: "P.kwargs",
    ):
        """
        Run the flow and return its final state.

        Examples:

            Run a flow and get the returned result

            >>> state = my_flow._run("marvin")
            >>> state.result()
           "goodbye marvin"
        """
        from prefect.engine import enter_flow_run_engine_from_flow_call

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_flow_run_engine_from_flow_call(
            self, parameters, return_type="state"
        )


@overload
def flow(__fn: Callable[P, R]) -> Flow[P, R]:
    ...


@overload
def flow(
    *,
    name: str = None,
    version: str = None,
    retries: int = 0,
    retry_delay_seconds: Union[int, float] = 0,
    task_runner: BaseTaskRunner = ConcurrentTaskRunner,
    description: str = None,
    timeout_seconds: Union[int, float] = None,
    validate_parameters: bool = True,
) -> Callable[[Callable[P, R]], Flow[P, R]]:
    ...


def flow(
    __fn=None,
    *,
    name: str = None,
    version: str = None,
    retries: int = 0,
    retry_delay_seconds: Union[int, float] = 0,
    task_runner: BaseTaskRunner = ConcurrentTaskRunner,
    description: str = None,
    timeout_seconds: Union[int, float] = None,
    validate_parameters: bool = True,
):
    """
    Decorator to designate a function as a Prefect workflow.

    This decorator may be used for asynchronous or synchronous functions.

    Flow parameters must be serializable by Pydantic.

    Args:
        name: An optional name for the flow; if not provided, the name will be inferred
            from the given function.
        version: An optional version string for the flow; if not provided, we will
            attempt to create a version string as a hash of the file containing the
            wrapped function; if the file cannot be located, the version will be null.
        task_runner: An optional task runner to use for task execution within the flow; if
            not provided, a `ConcurrentTaskRunner` will be instantiated.
        description: An optional string description for the flow; if not provided, the
            description will be pulled from the docstring for the decorated function.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the flow. If the flow exceeds this runtime, it will be marked as failed.
            Flow execution may continue until the next task is called.
        validate_parameters: By default, parameters passed to flows are validated by
            Pydantic. This will check that input values conform to the annotated types
            on the function. Where possible, values will be coerced into the correct
            type; for example, if a parameter is defined as `x: int` and "5" is passed,
            it will be resolved to `5`. If set to `False`, no validation will be
            performed on flow parameters.
        retries: An optional number of times to retry on flow run failure.
        retry_delay_seconds: An optional number of seconds to wait before retrying the
            flow after failure. This is only applicable if `retries` is nonzero.

    Returns:
        A callable `Flow` object which, when called, will run the flow and return its
        final state.

    Examples:
        Define a simple flow

        >>> from prefect import flow
        >>> @flow
        >>> def add(x, y):
        >>>     return x + y

        Define an async flow

        >>> @flow
        >>> async def add(x, y):
        >>>     return x + y

        Define a flow with a version and description

        >>> @flow(version="first-flow", description="This flow is empty!")
        >>> def my_flow():
        >>>     pass

        Define a flow with a custom name

        >>> @flow(name="The Ultimate Flow")
        >>> def my_flow():
        >>>     pass

        Define a flow that submits its tasks to dask

        >>> from prefect.task_runners import DaskTaskRunner
        >>>
        >>> @flow(task_runner=DaskTaskRunner)
        >>> def my_flow():
        >>>     pass
    """
    if __fn:
        return cast(
            Flow[P, R],
            Flow(
                fn=__fn,
                name=name,
                version=version,
                task_runner=task_runner,
                description=description,
                timeout_seconds=timeout_seconds,
                validate_parameters=validate_parameters,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )
    else:
        return cast(
            Callable[[Callable[P, R]], Flow[P, R]],
            partial(
                flow,
                name=name,
                version=version,
                task_runner=task_runner,
                description=description,
                timeout_seconds=timeout_seconds,
                validate_parameters=validate_parameters,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )


def select_flow(
    flows: Iterable[Flow], flow_name: str = None, from_message: str = None
) -> Flow:
    """
    Select the only flow in an iterable or a flow specified by name.

    Returns
        A single flow object

    Raises:
        MissingFlowError: If no flows exist in the iterable
        MissingFlowError: If a flow name is provided and that flow does not exist
        UnspecifiedFlowError: If multiple flows exist but no flow name was provided
    """
    # Convert to flows by name
    flows = {f.name: f for f in flows}

    # Add a leading space if given, otherwise use an empty string
    from_message = (" " + from_message) if from_message else ""

    if not flows:
        raise MissingFlowError(f"No flows found{from_message}.")

    elif flow_name and flow_name not in flows:
        raise MissingFlowError(
            f"Flow {flow_name!r} not found{from_message}. "
            f"Found the following flows: {listrepr(flows.keys())}"
        )

    elif not flow_name and len(flows) > 1:
        raise UnspecifiedFlowError(
            f"Found {len(flows)} flows{from_message}: {listrepr(sorted(flows.keys()))}. "
            "Specify a flow name to select a flow.",
        )

    if flow_name:
        return flows[flow_name]
    else:
        return list(flows.values())[0]


def load_flows_from_script(path: str) -> List[Flow]:
    """
    Load all flow objects from the given python script. All of the code in the file
    will be executed.

    Returns:
        A list of flows

    Raises:
        FlowScriptError: If an exception is encountered while running the script
    """

    return registry_from_script(path).get_instances(Flow)


def load_flow_from_script(path: str, flow_name: str = None) -> Flow:
    """
    Extract a flow object from a script by running all of the code in the file.

    If the script has multiple flows in it, a flow name must be provided to specify
    the flow to return.

    Args:
        path: A path to a Python script containing flows
        flow_name: An optional flow name to look for in the script

    Returns:
        The flow object from the script

    Raises:
        See `load_flows_from_script` and `select_flow`
    """
    return select_flow(
        load_flows_from_script(path),
        flow_name=flow_name,
        from_message=f"in script '{path}'",
    )


def load_flow_from_text(script_contents: AnyStr, flow_name: str):
    """
    Load a flow from a text script.

    The script will be written to a temporary local file path so errors can refer
    to line numbers and contextual tracebacks can be provided.
    """
    with NamedTemporaryFile(
        mode="wt" if isinstance(script_contents, str) else "wb",
        prefix=f"flow-script-{flow_name}",
        suffix=".py",
        delete=False,
    ) as tmpfile:
        tmpfile.write(script_contents)
        tmpfile.flush()
    try:
        flow = load_flow_from_script(tmpfile.name, flow_name=flow_name)
    finally:
        # windows compat
        tmpfile.close()
        os.remove(tmpfile.name)
    return flow
