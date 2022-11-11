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
from prefect.blocks.core import Block
from prefect.client import OrionClient, get_client
from prefect.client.orion import OrionClient
from prefect.client.utilities import inject_client
from prefect.filesystems import ReadableFileSystem
from prefect.orion.database.dependencies import temporary_database_interface
from prefect.results import PersistedResult
from prefect.serializers import Serializer
from prefect.states import State


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

# MagicMock supports async magic methods in Python 3.8+

if sys.version_info < (3, 8):
    from unittest.mock import MagicMock as _MagicMock
    from unittest.mock import MagicProxy as _MagicProxy

    class MagicMock(_MagicMock):
        def _mock_set_magics(self):
            """Patch to include proxies for async methods"""
            super()._mock_set_magics()

            for attr in {"__aenter__", "__aexit__", "__anext__"}:
                if not hasattr(MagicMock, attr):
                    setattr(MagicMock, attr, _MagicProxy(attr, self))

        def _get_child_mock(self, **kw):
            """Patch to return async mocks for async methods"""
            # This implemetation copied from unittest in Python 3.8
            _new_name = kw.get("_new_name")
            if _new_name in self.__dict__.get("_spec_asyncs", {}):
                return AsyncMock(**kw)

            _type = type(self)
            if issubclass(_type, MagicMock) and _new_name in {
                "__aenter__",
                "__aexit__",
                "__anext__",
            }:
                if self._mock_sealed:
                    attribute = "." + kw["name"] if "name" in kw else "()"
                    mock_name = self._extract_mock_name() + attribute
                    raise AttributeError(mock_name)

                return AsyncMock(**kw)

            return super()._get_child_mock(**kw)

else:
    from unittest.mock import MagicMock


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


def assert_blocks_equal(
    found, expected, exclude_private: bool = True, **kwargs
) -> bool:
    assert isinstance(
        found, type(expected)
    ), f"Unexpected type {type(found).__name__}, expected {type(expected).__name__}"

    if exclude_private:
        exclude = set(kwargs.pop("exclude", set()))
        for attr, _ in found._iter():
            if attr.startswith("_"):
                exclude.add(attr)

    assert found.dict(exclude=exclude, **kwargs) == expected.dict(
        exclude=exclude, **kwargs
    )


async def assert_uses_result_serializer(
    state: State, serializer: Union[str, Serializer]
):
    assert isinstance(state.data, PersistedResult)
    assert (
        state.data.serializer_type == serializer
        if isinstance(serializer, str)
        else serializer.type
    )
    blob = await state.data._read_blob()
    assert (
        blob.serializer == serializer
        if isinstance(serializer, Serializer)
        else Serializer(type=serializer)
    )


@inject_client
async def assert_uses_result_storage(
    state: State, storage: Union[str, ReadableFileSystem], client: "OrionClient"
):
    assert isinstance(state.data, PersistedResult)
    assert_blocks_equal(
        Block._from_block_document(
            await client.read_block_document(state.data.storage_block_id)
        ),
        storage
        if isinstance(storage, Block)
        else await Block.load(storage, client=client),
    )
