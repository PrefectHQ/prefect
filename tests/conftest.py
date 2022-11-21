"""
Base configuration of pytest for testing the 'prefect' module.

Here we make the following changes to pytest:
- Add service flags to the CLI
- Skip tests with the in accordance with service marks and flags
- Override the test event loop to allow async session/module scoped fixtures
- Inject a check for open Orion client lifespans after every test call
- Create a test Prefect settings profile before test collection that will be used
  for the duration of the test run. This ensures tests are run in a temporary
  environment.

WARNING: Prefect settings cannot be modified in async fixtures.
    Async fixtures are run in a different async context than tests and the modified
    settings will not be present in tests. If a setting needs to be modified by an async
    fixture, a sync fixture must be defined that consumes the async fixture to perform
    the settings context change. See `test_database_connection_url` for example.
"""
import asyncio
import logging
import pathlib
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Optional
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from sqlalchemy.dialects.postgresql.asyncpg import dialect as postgres_dialect

# Improve diff display for assertions in utilities
# Note: This must occur before import of the module
pytest.register_assert_rewrite("prefect.testing.utilities")

import prefect
import prefect.settings
from prefect.logging import get_logger
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_ASYNC_FETCH_STATE_RESULT,
    PREFECT_CLI_COLORS,
    PREFECT_CLI_WRAP_LINES,
    PREFECT_HOME,
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_LOGGING_LEVEL,
    PREFECT_LOGGING_ORION_ENABLED,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
    PREFECT_ORION_ANALYTICS_ENABLED,
    PREFECT_ORION_BLOCKS_REGISTER_ON_START,
    PREFECT_ORION_DATABASE_CONNECTION_URL,
    PREFECT_ORION_DATABASE_TIMEOUT,
    PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED,
    PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_ORION_SERVICES_SCHEDULER_ENABLED,
    PREFECT_PROFILES_PATH,
)
from prefect.utilities.dispatch import get_registry_for_type

# isort: split
# Import fixtures

from prefect.testing.cli import *
from prefect.testing.fixtures import *

from .fixtures.api import *
from .fixtures.client import *
from .fixtures.database import *
from .fixtures.docker import *
from .fixtures.logging import *
from .fixtures.storage import *


def pytest_addoption(parser):
    parser.addoption(
        "--exclude-services",
        action="store_true",
        default=False,
        help="Exclude all service integration tests from the test run.",
    )
    parser.addoption(
        "--only-service",
        action="append",
        metavar="SERVICE",
        default=[],
        help="Exclude all tests except service integration tests for SERVICE.",
    )
    parser.addoption(
        "--exclude-service",
        action="append",
        metavar="SERVICE",
        default=[],
        help="Exclude service integration tests for SERVICE.",
    )
    parser.addoption(
        "--only-services",
        action="store_true",
        default=False,
        help="Exclude all tests except service integration tests.",
    )

    parser.addoption(
        "--disable-docker-image-builds",
        action="store_true",
        default=False,
        help=(
            "Do not build the prefect Docker image during tests.  Tests that require "
            "the image will fail if the image is not present or has an outdated "
            "version of `prefect` installed.  Used during CI to run the test suite "
            "against images built with our production release build process."
        ),
    )


def pytest_collection_modifyitems(session, config, items):
    """
    Update tests to skip in accordance with service requests
    """
    exclude_all_services = config.getoption("--exclude-services")
    if exclude_all_services:
        for item in items:
            item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
            if item_services:
                item.add_marker(
                    pytest.mark.skip(
                        "Excluding tests for services. This test requires service(s): "
                        f"{', '.join(repr(s) for s in item_services)}."
                    )
                )

    exclude_services = set(config.getoption("--exclude-service"))
    for item in items:
        item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
        excluded_services = item_services.intersection(exclude_services)
        if excluded_services:
            item.add_marker(
                pytest.mark.skip(
                    "Excluding tests for service(s): "
                    f"{', '.join(repr(s) for s in excluded_services)}."
                )
            )

    only_run_service_tests = config.getoption("--only-services")
    if only_run_service_tests:
        for item in items:
            item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
            if not item_services:
                item.add_marker(
                    pytest.mark.skip(
                        "Only running tests for services. This test does not require a service."
                    )
                )
        return

    only_services = set(config.getoption("--only-service"))
    if only_services:
        only_running_blurb = f"Only running tests for service(s): {', '.join(repr(s) for s in only_services)}."
        for item in items:
            item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
            not_in_only_services = only_services.difference(item_services)

            if item_services:
                requires_blurb = (
                    "This test requires service(s): "
                    f"{', '.join(repr(s) for s in item_services)}"
                )
            else:
                requires_blurb = "This test does not require a service."

            if not_in_only_services:
                item.add_marker(
                    pytest.mark.skip(only_running_blurb + " " + requires_blurb)
                )
        return


@pytest.fixture(scope="session")
def event_loop(request):
    """
    Redefine the event loop to support session/module-scoped fixtures;
    see https://github.com/pytest-dev/pytest-asyncio/issues/68

    When running on Windows we need to use a non-default loop for subprocess support.
    """
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    policy = asyncio.get_event_loop_policy()

    if sys.version_info < (3, 8) and sys.platform != "win32":
        from prefect.utilities.compat import ThreadedChildWatcher

        # Python < 3.8 does not use a `ThreadedChildWatcher` by default which can
        # lead to errors in tests as the previous default `SafeChildWatcher`  is not
        # compatible with threaded event loops.
        policy.set_child_watcher(ThreadedChildWatcher())

    loop = policy.new_event_loop()

    # configure asyncio logging to capture long running tasks
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel("WARNING")
    asyncio_logger.addHandler(logging.StreamHandler())
    loop.set_debug(True)
    loop.slow_callback_duration = 0.25

    try:
        yield loop
    finally:
        loop.close()

    # Workaround for failures in pytest_asyncio 0.17;
    # see https://github.com/pytest-dev/pytest-asyncio/issues/257
    policy.set_event_loop(loop)


@pytest.fixture(scope="session")
def tests_dir() -> pathlib.Path:
    return pathlib.Path(__file__).parent


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """
    This hook will be called within the test run. Allowing us to raise errors or add
    assertions to every test. On error, the test will be marked as failed. If we used
    a fixture instead, the test teardown would report an error instead.
    """
    yield
    assert_lifespan_is_not_left_open()


def assert_lifespan_is_not_left_open():
    # This checks for regressions where the application lifespan is left open
    # across tests.
    from prefect.client import APP_LIFESPANS

    yield

    open_lifespans = APP_LIFESPANS.copy()
    if open_lifespans:
        # Clean out the lifespans to avoid erroring every future test
        APP_LIFESPANS.clear()
        raise RuntimeError(
            "Lifespans should be cleared at the end of each test, but "
            f"{len(open_lifespans)} lifespans were not closed: {open_lifespans!r}"
        )


# Stores the temporary directory that is used for the test run
TEST_PREFECT_HOME = None

# Stores the profile context manager used for the test run, preventing early exit from
# garbage collection when the sessionstart function exits.
TEST_PROFILE_CTX = None


def pytest_sessionstart(session):
    """
    Creates a profile for the scope of the test session that modifies setting defaults.

    This ensures that tests are isolated from existing settings, databases, etc.

    We set the test profile during session startup instead of a fixture to ensure that
    when tests are collected they respect the setting values.
    """
    global TEST_PREFECT_HOME, TEST_PROFILE_CTX
    TEST_PREFECT_HOME = tempfile.mkdtemp()

    profile = prefect.settings.Profile(
        name="test-session",
        settings={
            # Set PREFECT_HOME to a temporary directory to avoid clobbering
            # environments and settings
            PREFECT_HOME: TEST_PREFECT_HOME,
            PREFECT_LOCAL_STORAGE_PATH: Path(TEST_PREFECT_HOME) / "storage",
            PREFECT_PROFILES_PATH: "$PREFECT_HOME/profiles.toml",
            # Disable connection to an API
            PREFECT_API_URL: None,
            # Disable pretty CLI output for easier assertions
            PREFECT_CLI_COLORS: False,
            PREFECT_CLI_WRAP_LINES: False,
            # Enable future change
            PREFECT_ASYNC_FETCH_STATE_RESULT: True,
            # Enable debug logging
            PREFECT_LOGGING_LEVEL: "DEBUG",
            # Disable shipping logs to the API;
            # can be enabled by the `enable_orion_handler` mark
            PREFECT_LOGGING_ORION_ENABLED: False,
            # Disable services for test runs
            PREFECT_ORION_ANALYTICS_ENABLED: False,
            PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED: False,
            PREFECT_ORION_SERVICES_SCHEDULER_ENABLED: False,
            PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED: False,
            # Disable block auto-registration memoization
            PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION: False,
            # Disable auto-registration of block types as they can conflict
            PREFECT_ORION_BLOCKS_REGISTER_ON_START: False,
            # Use more aggressive database timeouts during testing
            PREFECT_ORION_DATABASE_TIMEOUT: 1,
        },
        source=__file__,
    )

    TEST_PROFILE_CTX = prefect.context.use_profile(
        profile,
        override_environment_variables=True,
        include_current_context=False,
    )
    TEST_PROFILE_CTX.__enter__()

    # Create the storage path now, fixing an obscure bug where it can be created by
    # when mounted as Docker volume resulting in the directory being owned by root
    # and unwritable by the normal user
    PREFECT_LOCAL_STORAGE_PATH.value().mkdir()

    # Ensure logging is configured for the test session
    setup_logging()


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session):
    # Allow all other finish fixture to complete first
    yield

    # Then, delete the temporary directory
    if TEST_PREFECT_HOME is not None:
        shutil.rmtree(TEST_PREFECT_HOME)


@pytest.fixture(scope="session", autouse=True)
def safety_check_settings():
    # Safety check for connection to an external API
    assert (
        PREFECT_API_URL.value() is None
    ), "Tests should not be run connected to an external API."
    # Safety check for home directory
    assert (
        str(PREFECT_HOME.value()) == TEST_PREFECT_HOME
    ), "Tests should use the temporary test directory"


@pytest.fixture(scope="session", autouse=True)
async def generate_test_database_connection_url(
    worker_id: str,
) -> Generator[Optional[str], None, None]:
    """Prepares an alternative test database URL, if necessary, for the current
    connection URL.

    For databases without a server (i.e. SQLite), produces `None`, indicating we should
    just use the currently configured value.

    For databases with a server (i.e. Postgres), creates an additional database on the
    server for each test worker, using the provided connection URL as the starting
    point.  Requires that the given database user has permission to connect to the
    server and create new databases."""
    original_url = PREFECT_ORION_DATABASE_CONNECTION_URL.value()
    if not original_url:
        yield None
        return

    scheme, netloc, database, query, fragment = urlsplit(original_url)
    if scheme == "sqlite+aiosqlite":
        # SQLite databases will be scoped by the PREFECT_HOME setting, which will
        # be in an isolated temporary directory
        yield None
        return

    if scheme == "postgresql+asyncpg":
        test_db_name = database.strip("/") + f"_tests_{worker_id}"
        quoted_db_name = postgres_dialect().identifier_preparer.quote(test_db_name)

        postgres_url = urlunsplit(("postgres", netloc, "postgres", query, fragment))

        # Create an empty temporary database for use in the tests
        connection = await asyncpg.connect(postgres_url)
        try:
            # remove any connections to the test database. For example if a SQL IDE
            # is being used to investigate it, it will block the drop database command.
            await connection.execute(
                f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{quoted_db_name}'
                AND pid <> pg_backend_pid();
                """
            )

            await connection.execute(f"DROP DATABASE IF EXISTS {quoted_db_name}")
            await connection.execute(f"CREATE DATABASE {quoted_db_name}")
        finally:
            await connection.close()

        new_url = urlunsplit((scheme, netloc, test_db_name, query, fragment))

        yield new_url

        # Now drop the temporary database we created
        connection = await asyncpg.connect(postgres_url)
        try:
            await connection.execute(f"DROP DATABASE IF EXISTS {quoted_db_name}")
        except asyncpg.exceptions.ObjectInUseError:
            # If we aren't able to drop the database because there's still a connection,
            # open, that's okay.  If we're in CI, then this DB is going away permanently
            # anyway, and if we're testing locally, in the beginning of this fixture,
            # we drop the database prior to creating it.  The worst case is that we
            # leave a DB catalog lying around on your local Postgres, which will get
            # cleaned up before the next test suite run.
            pass
        finally:
            await connection.close()


@pytest.fixture(scope="session", autouse=True)
def test_database_connection_url(generate_test_database_connection_url):
    """
    Update the setting for the database connection url to the generated value from
    `generate_test_database_connection_url`

    This _must_ be separate from the generation of the test url because async fixtures
    are run in a separate context from the test suite.
    """
    url = generate_test_database_connection_url
    if url is None:
        yield None
    else:
        with temporary_settings({PREFECT_ORION_DATABASE_CONNECTION_URL: url}):
            yield url


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield


@pytest.fixture(autouse=True)
def reset_registered_blocks():
    """
    Ensures each test only has types that were registered at module initialization.
    """
    registry = get_registry_for_type(Block)
    before = registry.copy()

    yield

    registry.clear()
    registry.update(before)


@pytest.fixture
def caplog(caplog):
    """
    Overrides caplog to apply to all of our loggers that do not propagate and
    consequently would not be captured by caplog.
    """

    config = setup_logging()

    for name, logger_config in config["loggers"].items():
        if not logger_config.get("propagate", True):
            logger = get_logger(name)
            logger.handlers.append(caplog.handler)

    yield caplog
