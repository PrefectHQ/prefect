"""
Utilities for working with Python callables.
"""

import ast
import importlib.util
import inspect
import warnings
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import cloudpickle
import pydantic
from griffe.dataclasses import Docstring
from griffe.docstrings.dataclasses import DocstringSectionKind
from griffe.docstrings.parsers import Parser, parse
from typing_extensions import Literal

from prefect._internal.pydantic.v1_schema import has_v1_type_as_param
from prefect._internal.pydantic.v2_schema import (
    create_v2_schema,
    process_v2_params,
)
from prefect.exceptions import (
    MappingLengthMismatch,
    MappingMissingIterable,
    ParameterBindError,
    ReservedArgumentError,
    SignatureMismatchError,
)
from prefect.logging.loggers import disable_logger, get_logger
from prefect.utilities.annotations import allow_failure, quote, unmapped
from prefect.utilities.collections import isiterable
from prefect.utilities.importtools import safe_load_namespace

logger = get_logger(__name__)


def get_call_parameters(
    fn: Callable,
    call_args: Tuple[Any, ...],
    call_kwargs: Dict[str, Any],
    apply_defaults: bool = True,
) -> Dict[str, Any]:
    """
    Bind a call to a function to get parameter/value mapping. Default values on
    the signature will be included if not overridden.

    If the function has a `__prefect_self__` attribute, it will be included as
    the first parameter. This attribute is set when Prefect decorates a bound
    method, so this approach allows Prefect to work with bound methods in a way
    that is consistent with how Python handles them (i.e. users don't have to
    pass the instance argument to the method) while still making the implicit self
    argument visible to all of Prefect's parameter machinery (such as cache key
    functions).

    Raises a ParameterBindError if the arguments/kwargs are not valid for the
    function
    """
    if hasattr(fn, "__prefect_self__"):
        call_args = (fn.__prefect_self__,) + call_args

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
    required: List[str] = pydantic.Field(default_factory=list)
    definitions: Dict[str, Any] = pydantic.Field(default_factory=dict)

    def model_dump_for_openapi(self) -> Dict[str, Any]:
        result = self.model_dump(mode="python", exclude_none=True)
        if "required" in result and not result["required"]:
            del result["required"]
        return result


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


def process_v1_params(
    param: inspect.Parameter,
    *,
    position: int,
    docstrings: Dict[str, str],
    aliases: Dict,
) -> Tuple[str, Any, "pydantic.Field"]:
    # Pydantic model creation will fail if names collide with the BaseModel type
    if hasattr(pydantic.BaseModel, param.name):
        name = param.name + "__"
        aliases[name] = param.name
    else:
        name = param.name

    type_ = Any if param.annotation is inspect._empty else param.annotation

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=pydantic.warnings.PydanticDeprecatedSince20
        )
        field = pydantic.Field(
            default=... if param.default is param.empty else param.default,
            title=param.name,
            description=docstrings.get(param.name, None),
            alias=aliases.get(name),
            position=position,
        )
    return name, type_, field


def create_v1_schema(name_: str, model_cfg, **model_fields):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=pydantic.warnings.PydanticDeprecatedSince20
        )

        model: "pydantic.BaseModel" = pydantic.create_model(
            name_, __config__=model_cfg, **model_fields
        )
        return model.schema(by_alias=True)


def parameter_schema(fn: Callable) -> ParameterSchema:
    """Given a function, generates an OpenAPI-compatible description
    of the function's arguments, including:
        - name
        - typing information
        - whether it is required
        - a default value
        - additional constraints (like possible enum values)

    Args:
        fn (Callable): The function whose arguments will be serialized

    Returns:
        ParameterSchema: the argument schema
    """
    try:
        signature = inspect.signature(fn, eval_str=True)  # novm
    except (NameError, TypeError):
        # `eval_str` is not available in Python < 3.10
        signature = inspect.signature(fn)

    docstrings = parameter_docstrings(inspect.getdoc(fn))

    return generate_parameter_schema(signature, docstrings)


def parameter_schema_from_entrypoint(entrypoint: str) -> ParameterSchema:
    """
    Generate a parameter schema from an entrypoint string.

    Will load the source code of the function and extract the signature and docstring
    to generate the schema.

    Useful for generating a schema for a function when instantiating the function may
    not be possible due to missing imports or other issues.

    Args:
        entrypoint: A string representing the entrypoint to a function. The string
            should be in the format of `module.path.to.function:do_stuff`.

    Returns:
        ParameterSchema: The parameter schema for the function.
    """
    if ":" in entrypoint:
        # split by the last colon once to handle Windows paths with drive letters i.e C:\path\to\file.py:do_stuff
        path, func_name = entrypoint.rsplit(":", maxsplit=1)
        source_code = Path(path).read_text()
    else:
        path, func_name = entrypoint.rsplit(".", maxsplit=1)
        spec = importlib.util.find_spec(path)
        if not spec or not spec.origin:
            raise ValueError(f"Could not find module {path!r}")
        source_code = Path(spec.origin).read_text()
    signature = _generate_signature_from_source(source_code, func_name)
    docstring = _get_docstring_from_source(source_code, func_name)
    return generate_parameter_schema(signature, parameter_docstrings(docstring))


def generate_parameter_schema(
    signature: inspect.Signature, docstrings: Dict[str, str]
) -> ParameterSchema:
    """
    Generate a parameter schema from a function signature and docstrings.

    To get a signature from a function, use `inspect.signature(fn)` or
    `_generate_signature_from_source(source_code, func_name)`.

    Args:
        signature: The function signature.
        docstrings: A dictionary mapping parameter names to docstrings.

    Returns:
        ParameterSchema: The parameter schema.
    """

    model_fields = {}
    aliases = {}

    if not has_v1_type_as_param(signature):
        create_schema = create_v2_schema
        process_params = process_v2_params

        config = pydantic.ConfigDict(arbitrary_types_allowed=True)
    else:
        create_schema = create_v1_schema
        process_params = process_v1_params

        class ModelConfig:
            arbitrary_types_allowed = True

        config = ModelConfig

    for position, param in enumerate(signature.parameters.values()):
        name, type_, field = process_params(
            param, position=position, docstrings=docstrings, aliases=aliases
        )
        # Generate a Pydantic model at each step so we can check if this parameter
        # type supports schema generation
        try:
            create_schema("CheckParameter", model_cfg=config, **{name: (type_, field)})
        except (ValueError, TypeError):
            # This field's type is not valid for schema creation, update it to `Any`
            type_ = Any
        model_fields[name] = (type_, field)

    # Generate the final model and schema
    schema = create_schema("Parameters", model_cfg=config, **model_fields)
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


def _generate_signature_from_source(
    source_code: str, func_name: str
) -> inspect.Signature:
    """
    Extract the signature of a function from its source code.

    Will ignore missing imports and exceptions while loading local class definitions.

    Args:
        source_code: The source code where the function named `func_name` is declared.
        func_name: The name of the function.

    Returns:
        The signature of the function.
    """
    # Load the namespace from the source code. Missing imports and exceptions while
    # loading local class definitions are ignored.
    namespace = safe_load_namespace(source_code)
    # Parse the source code into an AST
    parsed_code = ast.parse(source_code)

    func_def = next(
        (
            node
            for node in ast.walk(parsed_code)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == func_name
        ),
        None,
    )
    if func_def is None:
        raise ValueError(f"Function {func_name} not found in source code")
    parameters = []

    # Handle annotations for positional only args e.g. def func(a, /, b, c)
    for arg in func_def.args.posonlyargs:
        name = arg.arg
        annotation = arg.annotation
        if annotation is not None:
            try:
                ann_code = compile(ast.Expression(annotation), "<string>", "eval")
                annotation = eval(ann_code, namespace)
            except Exception as e:
                logger.debug("Failed to evaluate annotation for %s: %s", name, e)
                annotation = inspect.Parameter.empty
        else:
            annotation = inspect.Parameter.empty

        param = inspect.Parameter(
            name, inspect.Parameter.POSITIONAL_ONLY, annotation=annotation
        )
        parameters.append(param)

    # Determine the annotations for args e.g. def func(a: int, b: str, c: float)
    for arg in func_def.args.args:
        name = arg.arg
        annotation = arg.annotation
        if annotation is not None:
            try:
                # Compile and evaluate the annotation
                ann_code = compile(ast.Expression(annotation), "<string>", "eval")
                annotation = eval(ann_code, namespace)
            except Exception as e:
                # Don't raise an error if the annotation evaluation fails. Set the
                # annotation to `inspect.Parameter.empty` instead which is equivalent to
                # not having an annotation.
                logger.debug("Failed to evaluate annotation for %s: %s", name, e)
                annotation = inspect.Parameter.empty
        else:
            annotation = inspect.Parameter.empty

        param = inspect.Parameter(
            name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation
        )
        parameters.append(param)

    # Handle default values for args e.g. def func(a=1, b="hello", c=3.14)
    defaults = [None] * (
        len(func_def.args.args) - len(func_def.args.defaults)
    ) + func_def.args.defaults
    for param, default in zip(parameters, defaults):
        if default is not None:
            try:
                def_code = compile(ast.Expression(default), "<string>", "eval")
                default = eval(def_code, namespace)
            except Exception as e:
                logger.debug(
                    "Failed to evaluate default value for %s: %s", param.name, e
                )
                default = None  # Set to None if evaluation fails
            parameters[parameters.index(param)] = param.replace(default=default)

    # Handle annotations for keyword only args e.g. def func(*, a: int, b: str)
    for kwarg in func_def.args.kwonlyargs:
        name = kwarg.arg
        annotation = kwarg.annotation
        if annotation is not None:
            try:
                ann_code = compile(ast.Expression(annotation), "<string>", "eval")
                annotation = eval(ann_code, namespace)
            except Exception as e:
                logger.debug("Failed to evaluate annotation for %s: %s", name, e)
                annotation = inspect.Parameter.empty
        else:
            annotation = inspect.Parameter.empty

        param = inspect.Parameter(
            name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation
        )
        parameters.append(param)

    # Handle default values for keyword only args e.g. def func(*, a=1, b="hello")
    defaults = [None] * (
        len(func_def.args.kwonlyargs) - len(func_def.args.kw_defaults)
    ) + func_def.args.kw_defaults
    for param, default in zip(parameters[-len(func_def.args.kwonlyargs) :], defaults):
        if default is not None:
            try:
                def_code = compile(ast.Expression(default), "<string>", "eval")
                default = eval(def_code, namespace)
            except Exception as e:
                logger.debug(
                    "Failed to evaluate default value for %s: %s", param.name, e
                )
                default = None
            parameters[parameters.index(param)] = param.replace(default=default)

    # Handle annotations for varargs and kwargs e.g. def func(*args: int, **kwargs: str)
    if func_def.args.vararg:
        parameters.append(
            inspect.Parameter(
                func_def.args.vararg.arg, inspect.Parameter.VAR_POSITIONAL
            )
        )
    if func_def.args.kwarg:
        parameters.append(
            inspect.Parameter(func_def.args.kwarg.arg, inspect.Parameter.VAR_KEYWORD)
        )

    # Handle return annotation e.g. def func() -> int
    return_annotation = func_def.returns
    if return_annotation is not None:
        try:
            ret_ann_code = compile(
                ast.Expression(return_annotation), "<string>", "eval"
            )
            return_annotation = eval(ret_ann_code, namespace)
        except Exception as e:
            logger.debug("Failed to evaluate return annotation: %s", e)
            return_annotation = inspect.Signature.empty

    return inspect.Signature(parameters, return_annotation=return_annotation)


def _get_docstring_from_source(source_code: str, func_name: str) -> Optional[str]:
    """
    Extract the docstring of a function from its source code.

    Args:
        source_code (str): The source code of the function.
        func_name (str): The name of the function.

    Returns:
        The docstring of the function. If the function has no docstring, returns None.
    """
    parsed_code = ast.parse(source_code)

    func_def = next(
        (
            node
            for node in ast.walk(parsed_code)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == func_name
        ),
        None,
    )
    if func_def is None:
        raise ValueError(f"Function {func_name} not found in source code")

    if (
        func_def.body
        and isinstance(func_def.body[0], ast.Expr)
        and isinstance(func_def.body[0].value, ast.Constant)
    ):
        return func_def.body[0].value.value
    return None


def expand_mapping_parameters(
    func: Callable, parameters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generates a list of call parameters to be used for individual calls in a mapping
    operation.

    Args:
        func: The function to be called
        parameters: A dictionary of parameters with iterables to be mapped over

    Returns:
        List: A list of dictionaries to be used as parameters for each
            call in the mapping operation
    """
    # Ensure that any parameters in kwargs are expanded before this check
    parameters = explode_variadic_parameter(func, parameters)

    iterable_parameters = {}
    static_parameters = {}
    annotated_parameters = {}
    for key, val in parameters.items():
        if isinstance(val, (allow_failure, quote)):
            # Unwrap annotated parameters to determine if they are iterable
            annotated_parameters[key] = val
            val = val.unwrap()

        if isinstance(val, unmapped):
            static_parameters[key] = val.value
        elif isiterable(val):
            iterable_parameters[key] = list(val)
        else:
            static_parameters[key] = val

    if not len(iterable_parameters):
        raise MappingMissingIterable(
            "No iterable parameters were received. Parameters for map must "
            f"include at least one iterable. Parameters: {parameters}"
        )

    iterable_parameter_lengths = {
        key: len(val) for key, val in iterable_parameters.items()
    }
    lengths = set(iterable_parameter_lengths.values())
    if len(lengths) > 1:
        raise MappingLengthMismatch(
            "Received iterable parameters with different lengths. Parameters for map"
            f" must all be the same length. Got lengths: {iterable_parameter_lengths}"
        )

    map_length = list(lengths)[0]

    call_parameters_list = []
    for i in range(map_length):
        call_parameters = {key: value[i] for key, value in iterable_parameters.items()}
        call_parameters.update({key: value for key, value in static_parameters.items()})

        # Add default values for parameters; these are skipped earlier since they should
        # not be mapped over
        for key, value in get_parameter_defaults(func).items():
            call_parameters.setdefault(key, value)

        # Re-apply annotations to each key again
        for key, annotation in annotated_parameters.items():
            call_parameters[key] = annotation.rewrap(call_parameters[key])

        # Collapse any previously exploded kwargs
        call_parameters_list.append(collapse_variadic_parameters(func, call_parameters))

    return call_parameters_list
