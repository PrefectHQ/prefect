# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import copy
from contextlib import contextmanager
from typing import Any, Iterator

import prefect
from prefect.configuration import Config
from prefect.engine.state import State


@contextmanager
def set_temporary_config(temp_config: dict) -> Iterator:
    """
    Temporarily sets configuration values for the duration of the context manager.

    Args:
        - temp_config (dict): a dictionary containing (possibly nested) configuration keys and values.
            Nested configuration keys should be supplied as `.`-delimited strings.

    Example:
        ```python
        with set_temporary_config({'setting': 1, 'nested.setting': 2}):
            assert prefect.config.setting == 1
            assert prefect.config.nested.setting == 2
        ```
    """
    try:
        old_config = prefect.config.copy()

        for key, value in temp_config.items():
            prefect.config.set_nested(key, value)

        yield prefect.config
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
