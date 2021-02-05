"""
Utilities for interacting with [Prefect
configuration](https://docs.prefect.io/core/concepts/configuration.html).  These are only
intended to be used for testing.
"""
from contextlib import contextmanager
from typing import Iterator

import toml

import prefect
from prefect.configuration import Config


@contextmanager
def set_temporary_config(temp_config: dict) -> Iterator:
    """
    Temporarily sets configuration values for the duration of the context manager.

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


def set_permanent_user_config(extra_config: dict, config_path: str = None) -> bool:
    """
    Update user config file with a specific dictionary

    Args:
        extra_config (dict): any dict with new key/values to add
        config_path str: config file path, ~/.prefect/config.toml by default

    Example:
        ```python
        set_permanent_user_config({'server': {'host': 'http://my-server'}})
        ```

    """
    from prefect.configuration import USER_CONFIG, load_toml, interpolate_env_vars

    if config_path is None:
        config_path = interpolate_env_vars(USER_CONFIG)

    user_toml = load_toml(config_path)
    user_toml.update(extra_config)

    with open(config_path, "w") as fd:
        toml.dump(user_toml, fd)

    return config_path
