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

# context dictionary
context = {}

# global placeholders
run_dt = None
as_of_dt = None
flow = None
flow_id = None
flow_namespace = None
flow_name = None
flow_version = None
task_id = None
task_name = None
run_number = None
pipes = None
params = None

def set_context(**kwargs):
    """
    Sets global context and returns the original global context, so it can
    be restored later.
    """
    # store the current context
    previous_context = globals().copy()
    # update the context dict with new variables
    context.update(kwargs)
    # add the context variables to the global namespace
    globals().update(context)
    # return the previous context
    return previous_context

def reset_context(previous_context):
    """
    Reset the global context to a previous state
    """
    # clear the context dict
    context.clear()
    # restore the previous context
    globals().clear()
    globals().update(previous_context)


@_contextmanager
def prefect_context(**kwargs):
    """
    This context manager adds any keyword arguments to both
    the context dictionary and the global namespace.
    """
    previous_context = _set_context(**kwargs)
    try:
        yield context
    finally:
        _reset_context(previous_context)


def task_context(
        run_dt, as_of_dt, flow_id, flow_namespace, flow_name, flow_version, task_id,
        task_name, run_number, pipes, params, **kwargs):
    """
    Helper function for updating the Prefect context with items expected
    by tasks.
    """
    return prefect_context(**kwargs)
