"""
Internal utilities for tests.
"""

from __future__ import annotations

import atexit
import inspect
import shutil
import warnings
from contextlib import ExitStack, contextmanager
from pathlib import Path
from pprint import pprint
from tempfile import mkdtemp
from typing import TYPE_CHECKING, Any, Generator

import prefect.context
import prefect.settings
from prefect.blocks.core import Block
from prefect.client.orchestration import get_client
from prefect.client.schemas import sorting
from prefect.client.schemas.filters import FlowFilter, FlowFilterName
from prefect.client.utilities import inject_client
from prefect.events.worker import EventsWorker
from prefect.logging.handlers import APILogWorker
from prefect.results import (
    ResultRecord,
    ResultRecordMetadata,
    ResultStore,
    get_default_result_storage,
)
from prefect.serializers import Serializer
from prefect.server.api.server import SubprocessASGIServer
from prefect.states import State
from prefect.utilities.asyncutils import run_coro_as_sync

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.filesystems import ReadableFileSystem


def exceptions_equal(a: Exception, b: Exception) -> bool:
    """
    Exceptions cannot be compared by `==`. They can be compared using `is` but this
    will fail if the exception is serialized/deserialized so this utility does its
    best to assert equality using the type and args used to initialize the exception
    """
    if a == b:
        return True
    return type(a) is type(b) and getattr(a, "args", None) == getattr(b, "args", None)


def kubernetes_environments_equal(
    actual: list[dict[str, str]],
    expected: list[dict[str, str]] | dict[str, str],
) -> bool:
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
def assert_does_not_warn(
    ignore_warnings: list[type[Warning]] | None = None,
) -> Generator[None, None, None]:
    """
    Converts warnings to errors within this context to assert warnings are not raised,
    except for those specified in ignore_warnings.

    Parameters:
    - ignore_warnings: List of warning types to ignore. Example: [DeprecationWarning, UserWarning]
    """
    ignore_warnings = ignore_warnings or []
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for warning_type in ignore_warnings:
            warnings.filterwarnings("ignore", category=warning_type)

        try:
            yield
        except Warning as warning:
            raise AssertionError(f"Warning was raised. {warning!r}") from warning


@contextmanager
def prefect_test_harness(
    server_startup_timeout: int | None = 30,
    in_process: bool = False,
):
    """
    Temporarily run flows against a local SQLite database for testing.

    Args:
        server_startup_timeout: The maximum time to wait for the server to start.
            Defaults to 30 seconds. If set to `None`, the value of
            `PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS` will be used.
            Only used when `in_process=False`.
        in_process: If `True`, run the server in-process using ASGI transport
            instead of starting a subprocess HTTP server. This bypasses HTTP
            connection pooling entirely, which can help avoid issues with
            HTTP mocking libraries (like VCR/vcrpy) that interfere with
            connection management. Defaults to `False` for backwards compatibility.

    Examples:
        ```python
        from prefect import flow
        from prefect.testing.utilities import prefect_test_harness


        @flow
        def my_flow():
            return 'Done!'

        with prefect_test_harness():
            assert my_flow() == 'Done!' # run against temporary db

        # Use in_process=True to avoid HTTP connection pool issues
        # (e.g., when using VCR/vcrpy for HTTP mocking)
        with prefect_test_harness(in_process=True):
            assert my_flow() == 'Done!'
        ```
    """
    from prefect.server.database.dependencies import temporary_database_interface

    # create temp directory for the testing database
    temp_dir = mkdtemp()

    def cleanup_temp_dir(temp_dir):
        shutil.rmtree(temp_dir)

    atexit.register(cleanup_temp_dir, temp_dir)

    with ExitStack() as stack:
        # temporarily override any database interface components
        stack.enter_context(temporary_database_interface())

        DB_PATH = "sqlite+aiosqlite:///" + str(Path(temp_dir) / "prefect-test.db")
        stack.enter_context(
            prefect.settings.temporary_settings(
                # Use a temporary directory for the database
                updates={
                    prefect.settings.PREFECT_API_DATABASE_CONNECTION_URL: DB_PATH,
                },
            )
        )

        if in_process:
            # Use in-process ASGI transport - no HTTP connections at all
            # This avoids connection pool issues with HTTP mocking libraries
            from prefect.server.api.server import create_app

            app = create_app()
            stack.enter_context(
                prefect.settings.temporary_settings(
                    updates={
                        # Clear API URL to trigger ephemeral mode
                        prefect.settings.PREFECT_API_URL: None,
                        # Enable ephemeral mode so get_client() uses ASGI transport
                        prefect.settings.PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
                    },
                )
            )
            # Store the app in a module-level variable so get_client can access it
            # when PREFECT_SERVER_ALLOW_EPHEMERAL_MODE is True
            _set_in_process_app(app)
            stack.callback(_clear_in_process_app)
        else:
            # start a subprocess server to test against
            test_server = SubprocessASGIServer()
            test_server.start(
                timeout=server_startup_timeout
                if server_startup_timeout is not None
                else prefect.settings.PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS.value()
            )
            stack.enter_context(
                prefect.settings.temporary_settings(
                    # Use a temporary directory for the database
                    updates={
                        prefect.settings.PREFECT_API_URL: test_server.api_url,
                    },
                )
            )

        yield

        # drain the logs before stopping the server to avoid connection errors on shutdown
        # When running in an async context, drain() and drain_all() return awaitables.
        # We use a wrapper coroutine passed to run_coro_as_sync to ensure the awaitable
        # is created and awaited on the same loop, avoiding cross-loop issues (issue #19762)

        async def drain_workers():
            try:
                result = APILogWorker.instance().drain()
                if inspect.isawaitable(result):
                    await result
            except RuntimeError:
                # Worker may not have been started
                pass

            # drain events to prevent stale events from leaking into subsequent test harnesses
            result = EventsWorker.drain_all()
            if inspect.isawaitable(result):
                await result

        run_coro_as_sync(drain_workers())

        if not in_process:
            test_server.stop()


# Module-level storage for in-process ASGI app
_IN_PROCESS_APP: Any = None


def _set_in_process_app(app: Any) -> None:
    global _IN_PROCESS_APP
    _IN_PROCESS_APP = app


def _clear_in_process_app() -> None:
    global _IN_PROCESS_APP
    _IN_PROCESS_APP = None


def get_in_process_app() -> Any:
    """Get the in-process ASGI app if one is configured."""
    return _IN_PROCESS_APP


async def get_most_recent_flow_run(
    client: "PrefectClient | None" = None, flow_name: str | None = None
) -> "FlowRun":
    if client is None:
        client = get_client()

    flow_runs = await client.read_flow_runs(
        sort=sorting.FlowRunSort.EXPECTED_START_TIME_ASC,
        limit=1,
        flow_filter=FlowFilter(name=FlowFilterName(any_=[flow_name]))
        if flow_name
        else None,
    )

    return flow_runs[0]


def assert_blocks_equal(
    found: Block, expected: Block, exclude_private: bool = True, **kwargs: Any
) -> None:
    assert isinstance(found, type(expected)), (
        f"Unexpected type {type(found).__name__}, expected {type(expected).__name__}"
    )

    if exclude_private:
        exclude = set(kwargs.pop("exclude", set()))
        for field_name in found.__private_attributes__:
            exclude.add(field_name)

    assert found.model_dump(exclude=exclude, **kwargs) == expected.model_dump(
        exclude=exclude, **kwargs
    )


async def assert_uses_result_serializer(
    state: State, serializer: str | Serializer, client: "PrefectClient"
) -> None:
    assert isinstance(state.data, (ResultRecord, ResultRecordMetadata))
    if isinstance(state.data, ResultRecord):
        result_serializer = state.data.metadata.serializer
        storage_block_id = state.data.metadata.storage_block_id
        storage_key = state.data.metadata.storage_key
    else:
        result_serializer = state.data.serializer
        storage_block_id = state.data.storage_block_id
        storage_key = state.data.storage_key

    assert (
        result_serializer.type == serializer
        if isinstance(serializer, str)
        else serializer.type
    )
    if storage_block_id is not None:
        block = Block._from_block_document(
            await client.read_block_document(storage_block_id)
        )
    else:
        block = await get_default_result_storage()

    blob = await ResultStore(result_storage=block, serializer=result_serializer).aread(
        storage_key
    )
    assert (
        blob.metadata.serializer == serializer
        if isinstance(serializer, Serializer)
        else Serializer(type=serializer)
    )


@inject_client
async def assert_uses_result_storage(
    state: State, storage: "str | ReadableFileSystem", client: "PrefectClient"
) -> None:
    assert isinstance(state.data, (ResultRecord, ResultRecordMetadata))
    if isinstance(state.data, ResultRecord):
        assert_blocks_equal(
            Block._from_block_document(
                await client.read_block_document(state.data.metadata.storage_block_id)
            ),
            (
                storage
                if isinstance(storage, Block)
                else await Block.aload(storage, client=client)
            ),
        )
    else:
        assert_blocks_equal(
            Block._from_block_document(
                await client.read_block_document(state.data.storage_block_id)
            ),
            (
                storage
                if isinstance(storage, Block)
                else await Block.aload(storage, client=client)
            ),
        )


def a_test_step(**kwargs: Any) -> dict[str, Any]:
    kwargs.update(
        {
            "output1": 1,
            "output2": ["b", 2, 3],
            "output3": "This one is actually a string",
        }
    )
    return kwargs


def b_test_step(**kwargs: Any) -> dict[str, Any]:
    kwargs.update({"output1": 1, "output2": ["b", 2, 3]})
    return kwargs
