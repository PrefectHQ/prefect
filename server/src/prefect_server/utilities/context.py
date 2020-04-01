# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
The Prefect Server context is a Python 3.7 `ContextVar`, meaning it will not leak across threads
or asynchronous frames.

The context is a dictionary of arbitrary keys and values. At any time, the current context
can be retrieved by calling `get_context()`.

Values can be set in the context for a specific block of code by using the `set_context()`
context manager.
"""

import contextvars
from contextlib import contextmanager
from typing import Any, Dict

# create a ContextVar to hold the context. This must be a globally-scoped variable.
_context = contextvars.ContextVar("prefect-server-context", default=None)


def get_context() -> Dict[str, Any]:
    """
    Retrieve the current Server Context.

    Returns:
        - Dict[str, Any]: the current context
    """
    ctx = _context.get()  # type: ignore
    if ctx is not None:
        assert isinstance(ctx, dict)
        return ctx.copy()
    else:
        return {}


@contextmanager
def set_context(**kwargs: Any):
    """
    Set the Server Context for the duration of the context manager.

    Args:
        **kwargs (Any): values to add to the context

    Example:

    ```
    ctx = get_context()
    assert 'x' not in ctx

    with set_context(x=1):
        assert get_context()['x'] == 1

        with set_context(x=2):
            assert get_context()['x'] == 2

        assert get_context()['x'] == 1

    assert 'x' not in ctx
    ```

    """

    # retrieve the current context dictionary
    ctx = get_context()
    # update it with new values
    ctx.update(**kwargs)
    # set the global context
    token = _context.set(ctx)

    try:
        yield

    finally:
        # reset the context
        _context.reset(token)
