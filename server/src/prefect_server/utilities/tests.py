# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import copy
import hashlib
import json
import subprocess
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, List, Union

import prefect_server
from prefect.configuration import Config


def yaml_sorter(data: dict) -> Union[dict, List]:
    """
    Given a possibly nested dictionary, sorts keys recursively. The
    """

    def stable_hash(x) -> str:
        h = hashlib.sha1()
        h.update(json.dumps(x).encode())
        return h.hexdigest()

    if isinstance(data, dict):
        # sort by the key, using the hash of the nested fields as a stable tiebreaker
        return {
            key: yaml_sorter(value)
            for key, value in sorted(
                data.items(), key=lambda x: (x[0], stable_hash(yaml_sorter(x[0])))
            )
        }
    elif isinstance(data, list):
        # sort by the key, using the hash of the nested fields as a stable tiebreaker
        return sorted(
            [yaml_sorter(val) for val in data],
            key=lambda x: (json.dumps(x, sort_keys=True), stable_hash(yaml_sorter(x))),
        )
    else:
        return data


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
        old_config = copy.deepcopy(prefect_server.config)

        config = prefect_server.config
        keys = key.split(".")
        for key in keys[:-1]:
            config = config.setdefault(key, Config())
        setattr(config, keys[-1], value)
        yield
    finally:
        prefect_server.config.clear()
        prefect_server.config.update(old_config)


def wait_for(test_fn: Callable, timeout: int = 5, ignore_errors: bool = True) -> bool:
    """
    Helper that waits for a test_fn to be true.

    If the test_fn raises an error, it is trapped and considered non-True.

    Args:
        - test_fn (Callable): the function to test. The `wait_for` will exit if it returns a
            Trueish value
        - timeout (int): the number of seconds before the `wait_for` times out
        - ignore_errors (bool): if True, errors raised by the test_fn will be ignored. This is
            helpful is the test function is testing for something that might not be available
            immediately.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if test_fn():
                return True
        except Exception:
            if not ignore_errors:
                raise
        time.sleep(0.1)
    raise ValueError("Wait never finished.")


def check_if_service_is_running(port: int) -> bool:
    """
    Function that tests if a service has started on the specified localhost port

    Args:
        - port (int): the port to listen on

    Returns:
        - bool: True if the service is running; False otherwise
    """
    try:
        check = subprocess.check_call(
            ["nc", "-z", prefect_server.config.services.host, str(port)]
        )
        return check == 0
    except:
        return False
