from contextlib import contextmanager
from typing import Iterator

import prefect
from prefect.configuration import Config


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
