""""
Internal utilities for tests.
"""
import sys
import warnings
from contextlib import ExitStack, contextmanager
from pathlib import Path
from pprint import pprint
from tempfile import TemporaryDirectory
from typing import Dict, List, Union

import pytest

import prefect.context
import prefect.orion.schemas as schemas
import prefect.settings
from prefect.client import OrionClient, get_client
from prefect.orion.database.dependencies import temporary_database_interface


def flaky_on_windows(fn, **kwargs):
    """
    Mark a test as flaky for repeated test runs if on Windows.
    """
    if sys.platform == "win32":
        return pytest.mark.flaky(**kwargs)(fn)
    else:
        return fn


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
    from mock import AsyncMock  # noqa
else:
    from unittest.mock import AsyncMock  # noqa


def kubernetes_environments_equal(
    actual: List[Dict[str, str]],
    expected: Union[List[Dict[str, str]], Dict[str, str]],
):

    # Convert to a required format and sort by name
    if isinstance(expected, dict):
        expected = [{"name": key, "value": value} for key, value in expected.items()]

    expected = list(sorted(expected, key=lambda item: item["name"]))

    # Just sort the actual so the format can be tested
    if isinstance(actual, dict):
        raise TypeError(
            "Unexpected type 'dict' for 'actual' kubernetes environment. "
            "Expected 'List[dict]'. Did you pass your arguments in the wrong order?"
        )

    actual = list(sorted(actual, key=lambda item: item["name"]))

    print("---- Actual Kubernetes environment ----")
    pprint(actual, width=180)
    print()
    print("---- Expected Kubernetes environment ----")
    pprint(expected, width=180)
    print()

    for actual_item, expected_item in zip(actual, expected):
        if actual_item != expected_item:
            print("----- First difference in Kubernetes environments -----")
            print(f"Actual: {actual_item}")
            print(f"Expected: {expected_item}")
            break

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

            DB_PATH = "sqlite+aiosqlite:///" + str(Path(temp_dir) / "orion.db")
            stack.enter_context(
                prefect.settings.temporary_settings(
                    # Clear the PREFECT_API_URL
                    restore_defaults={prefect.settings.PREFECT_API_URL},
                    # Use a temporary directory for the database
                    updates={
                        prefect.settings.PREFECT_ORION_DATABASE_CONNECTION_URL: DB_PATH,
                        prefect.settings.PREFECT_API_URL: None,
                    },
                )
            )
            yield


async def get_most_recent_flow_run(client: OrionClient = None):
    if client is None:
        client = get_client()

    flow_runs = await client.read_flow_runs(
        sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC, limit=1
    )

    return flow_runs[0]
