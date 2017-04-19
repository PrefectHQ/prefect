# TODO this module is not threadsafe. Consider using threading.local
"""
This module handles context for Prefect objects in two ways:

1. a `context` dictionary (`prefect.context.context`)
2. injecting variables in to this module's global namespace

Therefore, tasks can use context variables by importing them from this module or
accessing the context dictionary. Variables may have no value (or not even
exist!) when tasks are defined, but tasks are run inside a context manager that assigns them at runtime.

"""
from contextlib import contextmanager as _contextmanager
import threading

# context dictionary
class context(threading.local):
    """
    A context store for Prefect data.
    """

    def __init__(self, **kwargs):
        self.reset(**kwargs)

    def __repr__(self):
        return '<PrefectContext>'

    def __iter__(self):
        return iter(self.__dict__.keys())

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return self.__dict__.copy()

    def update(self, **kwargs):
        self.__dict__.update(kwargs)

    def reset(self, **kwargs):
        self.__dict__.clear()
        self.run_dt = None
        self.as_of_dt = None
        self.flow = None
        self.flow_id = None
        self.flow_namespace = None
        self.flow_name = None
        self.flow_version = None
        self.task_id = None
        self.task_name = None
        self.run_number = None
        self.upstream_edges = None
        self.downstream_edges = None
        self.params = None
        self.update(**kwargs)

context = context()


@_contextmanager
def prefect_context(**kwargs):
    """
    This context manager adds any keyword arguments to both
    the context dictionary and the global namespace.
    """
    previous_context = context.to_dict()
    try:
        context.update(**kwargs)
        yield context
    finally:
        context.reset(**previous_context)


def task_context(
        run_dt, as_of_dt, flow_id, flow_namespace, flow_name, flow_version,
        task_id, task_name, run_number, upstream_edges, downstream_edges,
        params, **kwargs):
    """
    Helper function for updating the Prefect context with items expected
    by tasks.
    """
    return prefect_context(**kwargs)
