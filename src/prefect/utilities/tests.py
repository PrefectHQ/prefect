# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import copy
from contextlib import contextmanager
from typing import Any, Iterator

import prefect
from prefect.configuration import Config
from prefect.engine.state import State


@contextmanager
def set_temporary_config(key: str, value: Any) -> Iterator:
    """
    Temporarily sets a configuration value for the duration of the context manager.

    Args:
        - key (str): the fully-qualified config key (including '.'s)
        - value (Any): the value to apply to the key

    Example:
        ```python
        with set_temporary_config('flows.eager_edge_validation', True):
            assert prefect.config.flows.eager_edge_validation
        ```
    """
    try:
        old_config = copy.deepcopy(prefect.config.__dict__)

        config = prefect.config
        config.set_nested(key, value)
        yield
    finally:
        prefect.config.__dict__.clear()
        prefect.config.__dict__.update(old_config)


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
