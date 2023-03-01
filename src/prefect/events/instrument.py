import functools
import inspect
from typing import Any, Callable, Dict, Generator, List, Tuple, Type, TypeAlias, Union

from prefect.events import Event
from prefect.events.worker import get_events_worker

ResourceTuple: TypeAlias = Tuple[Dict[str, Any], List[Dict[str, Any]]]


def emit_instance_method_called_event(
    instance: Any,
    method_name: str,
    successful: bool,
):
    kind = instance._event_kind()
    resources: ResourceTuple = instance._event_method_called_resources(method_name)
    resource, related = resources
    resource["prefect.result"] = "successful" if successful else "failure"

    event = Event(event=f"{kind}-method.called", resource=resource, related=related)

    with get_events_worker() as events:
        events.emit(event)


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
    exclude_methods: Union[list[str], set[str], None] = None,
) -> Generator[Tuple[str, Callable], None, None]:
    """Returns all of the public methods on a class."""

    for name, kind, definer, method in inspect.classify_class_attrs(cls):
        if kind == "method":
            if exclude_methods and name in exclude_methods:
                continue
            if name.startswith("_"):
                continue
            if definer != cls:
                continue
            if not callable(method):
                continue
            yield name, method


def instrument_method_calls_on_class_instances(
    exclude_methods: Union[list[str], set[str], None] = None,
) -> Type:
    def instrument(cls: Type):
        """Given a Python class, instruments all "public" and "private" methods that are
        defined directly on the class (excluding base class methods).

        Examples:

            @instrument_class
            class MyClass(MyBase):
                def my_method(self):
                    ... this method will be instrumented ...

                def _my_method(self):
                    ... as will this ...

        The tracer used to instrument the class will be the one defined for the class's
        module.
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
            exclude_methods=exclude_methods,
        ):
            setattr(cls, name, decorator(method))
        return cls

    return instrument
