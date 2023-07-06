"""
Utilities for working with Python callables.
"""
import inspect
from functools import partial
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import cloudpickle
import pydantic
import pydantic.schema
from griffe.dataclasses import Docstring
from griffe.docstrings.dataclasses import DocstringSectionKind
from griffe.docstrings.parsers import Parser, parse
from typing_extensions import Literal

from prefect.exceptions import (
    ParameterBindError,
    ReservedArgumentError,
    SignatureMismatchError,
)
from prefect.logging.loggers import disable_logger


def get_call_parameters(
    fn: Callable,
    call_args: Tuple[Any, ...],
    call_kwargs: Dict[str, Any],
    apply_defaults: bool = True,
) -> Dict[str, Any]:
    """
    Bind a call to a function to get parameter/value mapping. Default values on the
    signature will be included if not overriden.

    Raises a ParameterBindError if the arguments/kwargs are not valid for the function
    """
    try:
        bound_signature = inspect.signature(fn).bind(*call_args, **call_kwargs)
    except TypeError as exc:
        raise ParameterBindError.from_bind_failure(fn, exc, call_args, call_kwargs)

    if apply_defaults:
        bound_signature.apply_defaults()

    # We cast from `OrderedDict` to `dict` because Dask will not convert futures in an
    # ordered dictionary to values during execution; this is the default behavior in
    # Python 3.9 anyway.
    return dict(bound_signature.arguments)


def get_parameter_defaults(
    fn: Callable,
) -> Dict[str, Any]:
    """
    Get default parameter values for a callable.
    """
    signature = inspect.signature(fn)

    parameter_defaults = {}

    for name, param in signature.parameters.items():
        if param.default is not signature.empty:
            parameter_defaults[name] = param.default

    return parameter_defaults


def explode_variadic_parameter(
    fn: Callable, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Given a parameter dictionary, move any parameters stored in a variadic keyword
    argument parameter (i.e. **kwargs) into the top level.

    Example:

        ```python
        def foo(a, b, **kwargs):
            pass

        parameters = {"a": 1, "b": 2, "kwargs": {"c": 3, "d": 4}}
        explode_variadic_parameter(foo, parameters)
        # {"a": 1, "b": 2, "c": 3, "d": 4}
        ```
    """
    variadic_key = None
    for key, parameter in inspect.signature(fn).parameters.items():
        if parameter.kind == parameter.VAR_KEYWORD:
            variadic_key = key
            break

    if not variadic_key:
        return parameters

    new_parameters = parameters.copy()
    for key, value in new_parameters.pop(variadic_key, {}).items():
        new_parameters[key] = value

    return new_parameters


def collapse_variadic_parameters(
    fn: Callable, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Given a parameter dictionary, move any parameters stored not present in the
    signature into the variadic keyword argument.

    Example:

        ```python
        def foo(a, b, **kwargs):
            pass

        parameters = {"a": 1, "b": 2, "c": 3, "d": 4}
        collapse_variadic_parameters(foo, parameters)
        # {"a": 1, "b": 2, "kwargs": {"c": 3, "d": 4}}
        ```
    """
    signature_parameters = inspect.signature(fn).parameters
    variadic_key = None
    for key, parameter in signature_parameters.items():
        if parameter.kind == parameter.VAR_KEYWORD:
            variadic_key = key
            break

    missing_parameters = set(parameters.keys()) - set(signature_parameters.keys())

    if not variadic_key and missing_parameters:
        raise ValueError(
            f"Signature for {fn} does not include any variadic keyword argument "
            "but parameters were given that are not present in the signature."
        )

    if variadic_key and not missing_parameters:
        # variadic key is present but no missing parameters, return parameters unchanged
        return parameters

    new_parameters = parameters.copy()
    if variadic_key:
        new_parameters[variadic_key] = {}

    for key in missing_parameters:
        new_parameters[variadic_key][key] = new_parameters.pop(key)

    return new_parameters


def parameters_to_args_kwargs(
    fn: Callable,
    parameters: Dict[str, Any],
) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """
    Convert a `parameters` dictionary to positional and keyword arguments

    The function _must_ have an identical signature to the original function or this
    will return an empty tuple and dict.
    """
    function_params = dict(inspect.signature(fn).parameters).keys()
    # Check for parameters that are not present in the function signature
    unknown_params = parameters.keys() - function_params
    if unknown_params:
        raise SignatureMismatchError.from_bad_params(
            list(function_params), list(parameters.keys())
        )
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


def parameter_docstrings(docstring: Optional[str]) -> Dict[str, str]:
    """
    Given a docstring in Google docstring format, parse the parameter section
    and return a dictionary that maps parameter names to docstring.

    Args:
        docstring: The function's docstring.

    Returns:
        Mapping from parameter names to docstrings.
    """
    param_docstrings = {}

    if not docstring:
        return param_docstrings

    with disable_logger("griffe.docstrings.google"), disable_logger(
        "griffe.agents.nodes"
    ):
        parsed = parse(Docstring(docstring), Parser.google)
        for section in parsed:
            if section.kind != DocstringSectionKind.parameters:
                continue
            param_docstrings = {
                parameter.name: parameter.description for parameter in section.value
            }

    return param_docstrings


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
    aliases = {}
    docstrings = parameter_docstrings(inspect.getdoc(fn))

    class ModelConfig:
        arbitrary_types_allowed = True

    for position, param in enumerate(signature.parameters.values()):
        # Pydantic model creation will fail if names collide with the BaseModel type
        if hasattr(pydantic.BaseModel, param.name):
            name = param.name + "__"
            aliases[name] = param.name
        else:
            name = param.name

        type_, field = (
            Any if param.annotation is inspect._empty else param.annotation,
            pydantic.Field(
                default=... if param.default is param.empty else param.default,
                title=param.name,
                description=docstrings.get(param.name, None),
                alias=aliases.get(name),
                position=position,
            ),
        )

        # Generate a Pydantic model at each step so we can check if this parameter
        # type is supported schema generation
        try:
            pydantic.create_model(
                "CheckParameter", __config__=ModelConfig, **{name: (type_, field)}
            ).schema(by_alias=True)
        except ValueError:
            # This field's type is not valid for schema creation, update it to `Any`
            type_ = Any

        model_fields[name] = (type_, field)

    # Generate the final model and schema
    model = pydantic.create_model("Parameters", __config__=ModelConfig, **model_fields)
    schema = model.schema(by_alias=True)
    return ParameterSchema(**schema)


def raise_for_reserved_arguments(fn: Callable, reserved_arguments: Iterable[str]):
    """Raise a ReservedArgumentError if `fn` has any parameters that conflict
    with the names contained in `reserved_arguments`."""
    function_paremeters = inspect.signature(fn).parameters

    for argument in reserved_arguments:
        if argument in function_paremeters:
            raise ReservedArgumentError(
                f"{argument!r} is a reserved argument name and cannot be used."
            )
