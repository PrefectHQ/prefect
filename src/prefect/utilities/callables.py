"""
Utilities for working with Python callables.
"""
import inspect
from functools import partial
from typing import Any, Callable, Dict, List, Tuple

import cloudpickle
import pydantic
from typing_extensions import Literal


def get_call_parameters(
    fn: Callable, call_args: Tuple[Any, ...], call_kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bind a call to a function to get parameter/value mapping. Default values on the
    signature will be included if not overriden.

    Will throw an exception if the arguments/kwargs are not valid for the function
    """
    try:
        bound_signature = inspect.signature(fn).bind(*call_args, **call_kwargs)
    except TypeError as exc:
        raise TypeError(f"Error binding parameters for {fn.__name__}: {str(exc)}")
    bound_signature.apply_defaults()
    # We cast from `OrderedDict` to `dict` because Dask will not convert futures in an
    # ordered dictionary to values during execution; this is the default behavior in
    # Python 3.9 anyway.
    return dict(bound_signature.arguments)


def parameters_to_args_kwargs(
    fn: Callable, parameters: Dict[str, Any]
) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """
    Convert a `parameters` dictionary to positional and keyword arguments

    The function _must_ have an identical signature to the original function or this
    will return an empty tuple and dict.
    """
    bound_signature = inspect.signature(fn).bind_partial()
    bound_signature.arguments = parameters
    return bound_signature.args, bound_signature.kwargs


def call_with_parameters(fn: Callable, parameters: Dict[str, Any]):
    """
    Call a function with parameters extracted with `get_call_parameters`

    The function _must_ have an identical signature to the original function or this
    will fail. If you need to send to a function with a different signature, extract
    the args/kwargs using `parameters_to_positional_and_keyword` directly
    """
    args, kwargs = parameters_to_args_kwargs(fn, parameters)
    return fn(*args, **kwargs)


def cloudpickle_wrapped_call(
    __fn: Callable, *args: Any, **kwargs: Any
) -> Callable[[], bytes]:
    """
    Serializes a function call using cloudpickle then returns a callable which will
    execute that call and return a cloudpickle serialized return value

    This is particularly useful for sending calls to libraries that only use the Python
    built-in pickler (e.g. `anyio.to_process` and `multiprocessing`) but may require
    a wider range of pickling support.
    """
    payload = cloudpickle.dumps((__fn, args, kwargs))
    return partial(_run_serialized_call, payload)


def _run_serialized_call(payload) -> bytes:
    """
    Defined at the top-level so it can be pickled by the Python pickler.
    Used by `cloudpickle_wrapped_call`.
    """
    fn, args, kwargs = cloudpickle.loads(payload)
    retval = fn(*args, **kwargs)
    return cloudpickle.dumps(retval)


class ParameterSchema(pydantic.BaseModel):
    """Simple data model corresponding to an OpenAPI `Schema`."""

    title: Literal["Parameters"] = "Parameters"
    type: Literal["object"] = "object"
    properties: Dict[str, Any] = pydantic.Field(default_factory=dict)
    required: List[str] = None
    definitions: Dict[str, Any] = None

    def dict(self, *args, **kwargs):
        """Exclude `None` fields by default to comply with
        the OpenAPI spec.
        """
        kwargs.setdefault("exclude_none", True)
        return super().dict(*args, **kwargs)


def parameter_schema(fn: Callable) -> ParameterSchema:
    """Given a function, generates an OpenAPI-compatible description
    of the function's arguments, including:
        - name
        - typing information
        - whether it is required
        - a default value
        - additional constraints (like possible enum values)

    Args:
        fn (function): The function whose arguments will be serialized

    Returns:
        dict: the argument schema
    """
    signature = inspect.signature(fn)
    model_fields = {}
    for param in signature.parameters.values():
        model_fields[param.name] = (
            Any if param.annotation is inspect._empty else param.annotation,
            pydantic.Field(
                default=... if param.default is param.empty else param.default,
                title=param.name,
                description=None,
            ),
        )
    return ParameterSchema(
        **pydantic.create_model("Parameters", **model_fields).schema()
    )
