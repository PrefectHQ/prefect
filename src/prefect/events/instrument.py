import functools
import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from prefect.events import emit_event

ResourceTuple = Tuple[Dict[str, Any], List[Dict[str, Any]]]


def emit_instance_method_called_event(
    instance: Any,
    method_name: str,
    successful: bool,
    payload: Optional[Dict[str, Any]] = None,
):
    kind = instance._event_kind()
    resources: Optional[ResourceTuple] = instance._event_method_called_resources()

    if not resources:
        return

    resource, related = resources
    result = "called" if successful else "failed"

    emit_event(
        event=f"{kind}.{method_name}.{result}",
        resource=resource,
        related=related,
        payload=payload,
    )


def instrument_instance_method_call():
    def instrument(function):
        if is_instrumented(function):
            return function

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def inner(self, *args, **kwargs):
                success = True
                try:
                    return await function(self, *args, **kwargs)
                except Exception as exc:
                    success = False
                    raise exc
                finally:
                    emit_instance_method_called_event(
                        instance=self, method_name=function.__name__, successful=success
                    )

        else:

            @functools.wraps(function)
            def inner(self, *args, **kwargs):
                success = True
                try:
                    return function(self, *args, **kwargs)
                except Exception as exc:
                    success = False
                    raise exc
                finally:
                    emit_instance_method_called_event(
                        instance=self, method_name=function.__name__, successful=success
                    )

        setattr(inner, "__events_instrumented__", True)
        return inner

    return instrument


def is_instrumented(function: Callable) -> bool:
    """Indicates whether the given function is already instrumented"""
    return getattr(function, "__events_instrumented__", False)


def instrumentable_methods(
    cls: Type,
    exclude_methods: Union[List[str], Set[str], None] = None,
) -> Generator[Tuple[str, Callable], None, None]:
    """Returns all of the public methods on a class."""

    for name, kind, _, method in inspect.classify_class_attrs(cls):
        if kind == "method" and callable(method):
            if exclude_methods and name in exclude_methods:
                continue
            if name.startswith("_"):
                continue

            yield name, method


def instrument_method_calls_on_class_instances(cls: Type) -> Type:
    """Given a Python class, instruments all "public" methods that are
    defined directly on the class to emit events when called.

    Examples:

        @instrument_class
        class MyClass(MyBase):
            def my_method(self):
                ... this method will be instrumented ...

            def _my_method(self):
                ... this method will not ...
    """

    required_events_methods = ["_event_kind", "_event_method_called_resources"]
    for method in required_events_methods:
        if not hasattr(cls, method):
            raise RuntimeError(
                f"Unable to instrument class {cls}. Class must define {method!r}."
            )

    decorator = instrument_instance_method_call()

    for name, method in instrumentable_methods(
        cls,
        exclude_methods=getattr(cls, "_events_excluded_methods", []),
    ):
        setattr(cls, name, decorator(method))
    return cls
