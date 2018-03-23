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
import contextlib
import copy
import datetime
import inspect
from types import SimpleNamespace
from typing import Any, NewType

import wrapt

from prefect.utilities.json import Serializable


# context dictionary
class Context(SimpleNamespace, Serializable):
    """
    A context store for Prefect data.
    """

    def __repr__(self):
        return '<Prefect Context>'

    def to_dict(self):
        return self.__dict__.copy()

    def update(self, *args, **kwargs):
        args = [a.to_dict() if isinstance(a, type(self)) else a for a in args]
        self.__dict__.update(*args, **kwargs)

    def clear(self):
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
        previous_context = copy.deepcopy(self)
        try:
            self.update(*context_args, **context_kwargs)
            yield self
        finally:
            self.clear()
            self.update(previous_context)

    def get(self, key, if_missing=None):
        return getattr(self, key, if_missing)

context = Context()


class Annotations:
    """
    Task functions can be annotated with these types to have them supplied
    at runtime.
    """

    # any other variable [this is a catch all]
    context_variable = NewType('context', Any)

    # the context itself
    context = NewType('context', dict)

    # execution
    run_dt = NewType('run_dt', datetime.datetime)
    as_of_dt = NewType('as_of_dt', datetime.datetime)

    # API
    api_server = NewType('api_server', str)
    api_token = NewType('api_token', str)

    # flow
    flow = NewType('flow', Any)  # Flow hasn't been defined yet
    flow_id = NewType('flow_id', str)
    flow_name = NewType('flow_name', str)

    # task
    task_id = NewType('task_id', str)
    task_name = NewType('task_name', str)

    # flow_run
    flow_run_id = NewType('flow_run_id', str)
    flow_run_start_tasks = NewType('flow_run_start_tasks', list)
    params = NewType('params', dict)

    # task_run
    task_run_id = NewType('task_run_id', str)
    task_run_upstream_states = NewType('task_run_upstream_states', dict)
    task_run_inputs = NewType('task_run_inputs', dict)

    @classmethod
    def _annotations(cls):
        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_')}


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

    annotations = Annotations._annotations()

    # iterate over the function signature to examine each parameter
    for i, (key, param) in enumerate(signature.parameters.items()):
        # skip any that were explicitly provided
        if key in kwargs or len(args) > i:
            continue

        # skip any that aren't context variables
        elif param.annotation not in annotations.values():
            continue

        # if the annotation IS the context, return the context dict
        elif param.annotation is Annotations.context:
            kwargs[key] = context.to_dict()

        # else return the context variable
        elif key in context:
            kwargs[key] = context[key]

    return fn(*args, **kwargs)
