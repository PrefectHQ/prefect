# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import copy
from contextlib import contextmanager
from typing import Any

import prefect
from prefect.configuration import Config
from prefect.engine.state import State


@contextmanager
def set_temporary_config(key: str, value: Any):
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
        keys = key.split(".")
        for key in keys[:-1]:
            config = config.setdefault(key, Config())
        setattr(config, keys[-1], value)
        yield
    finally:
        prefect.config.__dict__.clear()
        prefect.config.__dict__.update(old_config)


@contextmanager
def raise_on_exception():
    with prefect.context(_raise_on_exception=True):
        yield
