"""
Utilities for interacting with [Prefect
configuration](https://docs.prefect.io/core/concepts/configuration.html).  These are only
intended to be used for testing.
"""
from contextlib import contextmanager
from typing import Iterator

import prefect
from prefect.configuration import Config


@contextmanager
def set_temporary_config(temp_config: dict) -> Iterator:
    """
    Temporarily sets configuration values for the duration of the context manager.

    This is only intended to be used for testing.

    Args:
        - temp_config (dict): a dictionary containing (possibly nested) configuration keys and
            values. Nested configuration keys should be supplied as `.`-delimited strings.

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
            # the `key` might be a dot-delimited string, so we split on "." and set the value
            cfg = prefect.config
            subkeys = key.split(".")
            for subkey in subkeys[:-1]:
                cfg = cfg.setdefault(subkey, Config())
            cfg[subkeys[-1]] = value

        # ensure the new config is available in context
        with prefect.context(config=prefect.config):
            yield prefect.config
    finally:
        prefect.config.clear()
        prefect.config.update(old_config)
