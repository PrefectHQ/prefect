"""
Base workflow class and decorator

This file requires type-checking with pyright because mypy does not yet support PEP612
See https://github.com/python/mypy/issues/8645
"""
import inspect
from functools import update_wrapper, partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    TypeVar,
    cast,
    overload,
    Generic,
    NoReturn,
    Dict,
)

import pydantic
from pydantic.decorator import ValidatedFunction
from typing_extensions import ParamSpec

from prefect import State
from prefect.executors import BaseExecutor, LocalExecutor
from prefect.exceptions import FlowParameterError
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.asyncio import is_async_fn
from prefect.utilities.callables import (
    get_call_parameters,
    parameters_to_positional_and_keyword,
)
from prefect.utilities.hashing import file_hash

T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the flow


class Flow(Generic[P, R]):
    """
    Base class representing Prefect workflows.
    """

    def __init__(
        self,
        fn: Callable[P, R],
        name: str = None,
        version: str = None,
        executor: BaseExecutor = None,
        description: str = None,
        tags: Iterable[str] = None,
        validate_parameters: bool = True,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__.replace("_", "-")

        self.tags = set(tags if tags else [])
        self.executor = executor or LocalExecutor()

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = is_async_fn(self.fn)

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)

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

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters that are going to be used to call the flow

        Returns:
            - A new dict of parameters

        Raises
            - FlowParameterError: if the parameters are not valid

        """
        validated_fn = ValidatedFunction(self.fn, config=None)
        args, kwargs = parameters_to_positional_and_keyword(self.fn, parameters)
        try:
            model = validated_fn.init_model_instance(*args, **kwargs)
        except pydantic.ValidationError as exc:
            # We capture the pydantic exception and raise our own because the pydantic
            # exception is not picklable when using a cythonized pydantic installation
            raise FlowParameterError(str(exc))

        # Get the updated parameter dict with cast values from the model
        cast_parameters = {
            k: v
            for k, v in model._iter()
            if k in model.__fields_set__ or model.__fields__[k].default_factory
        }
        return cast_parameters

    @overload
    def __call__(
        self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs
    ) -> State[T]:
        """
        `NoReturn` matches if a type can't be inferred for the function which stops a
        sync function from matching the `Coroutine` overload
        """
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]", *args: P.args, **kwargs: P.kwargs
    ) -> Awaitable[State[T]]:
        ...

    @overload
    def __call__(self: "Flow[P, T]", *args: P.args, **kwargs: P.kwargs) -> State[T]:
        ...

    def __call__(
        self,
        *args: "P.args",
        **kwargs: "P.kwargs",
    ):
        from prefect.engine import enter_flow_run_engine_from_flow_call

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_flow_run_engine_from_flow_call(self, parameters)


@overload
def flow(__fn: Callable[P, R]) -> Flow[P, R]:
    ...


@overload
def flow(
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = None,
    description: str = None,
    tags: Iterable[str] = None,
    validate_parameters: bool = True,
) -> Callable[[Callable[P, R]], Flow[P, R]]:
    ...


def flow(
    __fn=None,
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = None,
    description: str = None,
    tags: Iterable[str] = None,
    validate_parameters: bool = True,
):
    if __fn:
        return cast(
            Flow[P, R],
            Flow(
                fn=__fn,
                name=name,
                version=version,
                executor=executor,
                description=description,
                tags=tags,
                validate_parameters=validate_parameters,
            ),
        )
    else:
        return cast(
            Callable[[Callable[P, R]], Flow[P, R]],
            partial(
                flow,
                name=name,
                version=version,
                executor=executor,
                description=description,
                tags=tags,
                validate_parameters=validate_parameters,
            ),
        )
