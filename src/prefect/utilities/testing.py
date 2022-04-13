""""
Internal utilities for tests.
"""
import os
import sys
import warnings
from contextlib import ExitStack, contextmanager
from tempfile import TemporaryDirectory
from typing import Dict, List, Union

import prefect.context
import prefect.settings
from prefect.orion.database.dependencies import temporary_database_interface


def exceptions_equal(a, b):
    """
    Exceptions cannot be compared by `==`. They can be compared using `is` but this
    will fail if the exception is serialized/deserialized so this utility does its
    best to assert equality using the type and args used to initialize the exception
    """
    if a == b:
        return True
    return type(a) == type(b) and getattr(a, "args", None) == getattr(b, "args", None)


# AsyncMock has a new import path in Python 3.8+

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


@contextmanager
def temporary_settings(**kwargs):
    """
    Temporarily override setting values by updating the current os.environ and changing
    the profile context.

    This will _not_ mutate values that have been already been accessed at module
    load time.

    Values set to `None` will be restored to the default value.

    This function should only be used for testing.

    Example:
        >>> from prefect.settings import PREFECT_API_URL
        >>> with temporary_settings(PREFECT_API_URL="foo"):
        >>>    assert PREFECT_API_URL.value() == "foo"
        >>> assert PREFECT_API_URL.value() is None
    """
    old_env = os.environ.copy()

    # Collect keys to set to new values
    set_variables = {
        # Cast values to strings
        key: str(value)
        for key, value in kwargs.items()
        if value is not None
    }
    # Collect keys to restore to defaults
    unset_variables = {key for key, value in kwargs.items() if value is None}

    try:
        for key, value in set_variables.items():
            os.environ[key] = value
        for key in unset_variables:
            os.environ.pop(key, None)

        new_settings = prefect.settings.get_settings_from_env()

        with prefect.context.ProfileContext(
            name="temporary", settings=new_settings, env=set_variables
        ):
            yield new_settings

    finally:
        for key in unset_variables.union(set_variables.keys()):
            if old_env.get(key):
                os.environ[key] = old_env[key]
            else:
                os.environ.pop(key, None)


def kubernetes_environments_equal(
    actual: List[Dict[str, str]],
    expected: Union[List[Dict[str, str]], Dict[str, str]],
):

    # Convert to a required format and sort by name
    if isinstance(expected, dict):
        expected = [
            {"name": key, "value": value} for key, value in sorted(expected.items())
        ]
    else:
        expected = list(sorted(expected, key=lambda item: item["name"]))

    # Just sort the actual so the format can be tested
    if isinstance(actual, dict):
        raise TypeError(
            "Unexpected type 'dict' for 'actual' kubernetes environment. "
            "Expected 'List[dict]'. Did you pass your arguments in the wrong order?"
        )
    actual = list(sorted(actual, key=lambda item: item["name"]))

    return actual == expected


@contextmanager
def assert_does_not_warn():
    """
    Converts warnings to errors within this context to assert warnings are not raised.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            yield
        except Warning as warning:
            raise AssertionError(f"Warning was raised. {warning!r}") from warning


@contextmanager
def prefect_test_harness():
    """
    Temporarily run flows against a local SQLite database for testing.

    Example:
        >>> from prefect import flow
        >>> @flow
        >>> def my_flow():
        >>>     return 'Done!'
        >>> with prefect_test_harness():
        >>>     assert my_flow() == 'Done!' # run against temporary db
    """
    # create temp directory for the testing database
    with TemporaryDirectory() as temp_dir:
        with ExitStack() as stack:
            # temporarily override any database interface components
            stack.enter_context(temporary_database_interface())
            # set the connection url to our temp database
            # make sure PREFECT_API_URL is not set, otherwise
            # actual API requests will be made
            stack.enter_context(
                temporary_settings(
                    PREFECT_API_URL=None,
                    PREFECT_ORION_DATABASE_CONNECTION_URL=f"sqlite+aiosqlite:////{temp_dir}/orion.db",
                )
            )
            yield
