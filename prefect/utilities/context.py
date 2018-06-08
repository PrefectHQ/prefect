"""
This module implements the Prefect context that is available when tasks run.

Tasks can import prefect.context and access attributes that will be overwritten
when the task is run.

Example:
    import prefect.context
    with prefect.context(a=1, b=2):
        print(prefect.context.a) # 1
    print (prefect.context.a) # undefined

"""

from typing import Iterable, Dict, Any
import contextlib
import copy
import inspect
from types import SimpleNamespace

import wrapt

from prefect.utilities.json import Serializable


# context dictionary
class PrefectContext(SimpleNamespace, Serializable):
    """
    A context store for Prefect data.
    """

    _context = None

    # PrefectContext is a Singleton
    def __new__(cls, *args, **kwargs) -> "PrefectContext":
        if not cls._context:
            cls._context = super().__new__(cls, *args, **kwargs)
        return cls._context

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(**kwargs)
        self.update(args)

    def __repr__(self) -> str:
        return "<Prefect Context>"

    def __delattr__(self, key) -> None:
        del self.__dict__[key]

    def __iter__(self) -> Iterable:
        return self.__dict__.keys()

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def update(self, *args, **kwargs) -> None:
        args = [a.to_dict() if isinstance(a, type(self)) else a for a in args]
        for a in args:
            self.__dict__.update(a)
        self.__dict__.update(kwargs)

    def clear(self) -> None:
        self.__dict__.clear()

    @contextlib.contextmanager
    def __call__(self, *context_args, **context_kwargs):
        """
        A context manager for setting / resetting the Prefect context

        Example:
            import prefect.context
            with prefect.context(dict(a=1, b=2), c=3):
                print(prefect.context.a) # 1
        """
        previous_context = copy.copy(self)
        try:
            self.update(*context_args, **context_kwargs)
            yield self
        finally:
            self.clear()
            self.update(previous_context)

    def get(self, key: str, default=None) -> Any:
        return getattr(self, key, default)

    def setdefault(self, key, default):
        if key not in self:
            self.key = default
        return getattr(self, key)


context = PrefectContext()


class ContextAnnotation:
    def __init__(self, name):
        self.name = name


@wrapt.decorator
def apply_context_annotations(fn, instance, args, kwargs):
    """
    This decorator wraps a function so that at runtime, any function arguments
    that are annotated as Context variables and not supplied by the user
    are supplied from the context.

    >>> @apply_context_annotations
    ... def test(
    ...         x: Annotations.context_variable,
    ...         flow_id: Annotations.flow_id):
    ...     return x, flow_id
    >>>
    >>> with Context(x=1, flow_id='id'):
    ...     test()
    (1, 'id')

    """
    return call_with_context_annotations(fn, *args, **kwargs)


def call_with_context_annotations(fn, *args, **kwargs):
    """
    If a function has been annotated with Context variables, then calling
    it in this way will automatically provide those variables to the function.
    """
    # if we can't read a signature, just return the function
    try:
        signature = inspect.signature(fn)
    except ValueError:
        return fn(*args, **kwargs)

    # iterate over the function signature to examine each parameter
    for i, (key, param) in enumerate(signature.parameters.items()):
        # skip any that were explicitly provided
        if key in kwargs or len(args) > i:
            continue

        # skip any that aren't context variables
        elif not isinstance(param.annotation, ContextAnnotation):
            continue

        # retrieve the context variable
        kwargs[key] = context[key]

    return fn(*args, **kwargs)
