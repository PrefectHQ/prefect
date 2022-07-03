import inspect
import json
import pickle
from decimal import Decimal
from functools import partial, wraps
from typing import Any, Callable, Iterable, Type, Optional

from prefect.client import Secret

from toloka.client import TolokaClient, add_headers
import toloka.client as _toloka_client_lib  # To avoid `structure` pickling errors.


def with_updated_signature(
    func: Callable,
    wrapper: Callable,
    add_wrapper_args: Iterable[str] = (),
    remove_func_args: Iterable[str] = (),
) -> Callable:
    """
    Prefect tasks relate on function signature,
    so we need to change it since we use some args-changing wrappers.

    Args:
        - func (Callable): Initial function to get signature from.
        - wrapper (Callable): Wrapper to take body from.
        - add_wrapper_args (Iterable, optional): Wrapper's args to put in the final signature.
        - remove_func_args (Iterable, optional): Func's args to remove from the final signature.

    Returns:
        - Callable: initial wrapper with modified signature.
    """

    remove_func_args = set(remove_func_args)

    signature_func = inspect.signature(func)
    parameters_keep = [
        param
        for param in signature_func.parameters.values()
        if param.name not in remove_func_args
        and param.kind != inspect.Parameter.VAR_KEYWORD
    ]

    parameters_wrapper = inspect.signature(wrapper).parameters
    parameters_add = [parameters_wrapper[arg_name] for arg_name in add_wrapper_args]

    last_param = next(reversed(signature_func.parameters.values()), inspect.Parameter)
    if last_param.kind == inspect.Parameter.VAR_KEYWORD:
        parameters_add.append(last_param)

    res = wraps(func)(wrapper)
    res.__special_wrapped__ = res.__wrapped__
    del res.__wrapped__
    res.__signature__ = signature_func.replace(
        parameters=parameters_keep + parameters_add
    )

    return res


def with_logger(func: Callable) -> Callable:
    """
    Decorator that allows function to use Prefect logger instance.
    Enrich function signature with keyword-only argument "logger".
    Use it to write logs from Prefect task.

    Args:
        - func (Callable): Function that takes `logger` argument.

    Returns:
        - Callable: a wrapper with Prefect logger passed.

    Example:
        >>> @task
        ... def some_task():
        ...     return 123
        ...
        >>> @task
        ... @with_logger
        ... def task_with_logger(arg, logger):
        ...     logger.warning('arg value: %s', arg)
        ...
        >>> with Flow('some-flow') as flow:
        ...     res = some_task()
        ...     task_with_logger(res)
        ...
    """

    def _wrapper(*args, **kwargs) -> Any:
        import prefect

        return partial(func, logger=prefect.context.get("logger"))(*args, **kwargs)

    return with_updated_signature(func, _wrapper, remove_func_args={"logger"})


_json_loads = partial(json.loads, parse_float=Decimal)


def structure_from_conf(obj: Any, cl: Type) -> object:
    if isinstance(obj, cl):
        return obj
    if isinstance(obj, bytes):
        try:
            return pickle.loads(obj)
        except Exception:
            pass
        obj = obj.decode()
    if isinstance(obj, str):
        obj = _json_loads(obj)
    return _toloka_client_lib.structure(obj, cl)


def extract_id(obj: Any, cl: Type) -> str:
    if isinstance(obj, str):
        try:
            obj = _json_loads(obj)
        except Exception:
            return obj
        if isinstance(obj, int):
            return str(obj)
    res = structure_from_conf(obj, cl).id
    if res is None:
        raise ValueError(f"Got id=None from: {obj}")
    return res


DEFAULT_TOLOKA_SECRET_NAME = "TOLOKA_TOKEN"
DEFAULT_TOLOKA_ENV = "PRODUCTION"


def with_toloka_client(func: Callable) -> Callable:
    """
    Decorator that allows function to pass `token`, `secret_name` and `env` args
    and operate with `toloka_client` instance.

    Args:
        - func (Callable): Function that operate with `toloka_client` argument.

    Returns:
        - Callable: The wrapper, which takes optional `token`, `secret_name` and `env` arguments
            and operates with default `toloka_token` if they are not passed.

    Example:
        >>> @with_toloka_client
        ... def some_func(toloka_client: TolokaClient):
        ...     toloka_client.create_project(...)
        ...
        >>> some_func()  # Use default toloka_client created using TOLOKA_TOKEN secret.
        >>> some_func(secret_name="OTHER_ACCOUNT_SECRET")  # Allow to pass other secret name.
        >>> some_func(token=PrefectSecret("TOLOKA_TOKEN")) # Provide secret directly.
        ...
    """

    def _wrapper(
        *args,
        token: Optional[str] = None,
        secret_name: str = DEFAULT_TOLOKA_SECRET_NAME,
        env: str = DEFAULT_TOLOKA_ENV,
        **kwargs,
    ) -> Any:
        token = token or Secret(secret_name).get()
        toloka_client = TolokaClient(token, env)
        return partial(add_headers("prefect")(func), toloka_client=toloka_client)(
            *args, **kwargs
        )

    return with_updated_signature(
        func,
        _wrapper,
        remove_func_args=("toloka_client",),
        add_wrapper_args=("token", "secret_name", "env"),
    )
