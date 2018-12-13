# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from contextlib import contextmanager
from typing import Any, Iterator

import prefect


@contextmanager
def raise_on_exception() -> Iterator:
    """
    Context manager for raising exceptions when they occur instead of trapping them.
    Intended to be used only for local debugging and testing.

    Example:
        ```python
        from prefect import Flow, task
        from prefect.utilities.tests import raise_on_exception

        @task
        def div(x):
            return 1 / x

        with Flow() as f:
            res = div(0)

        with raise_on_exception():
            f.run() # raises ZeroDivisionError
        ```
    """
    with prefect.context(_raise_on_exception=True):
        yield
