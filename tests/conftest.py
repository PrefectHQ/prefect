import asyncio
import logging
import os
import pathlib
import tempfile
from typing import Generator, Optional
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from docker import DockerClient
from docker.errors import ImageNotFound
from sqlalchemy.dialects.postgresql.asyncpg import dialect as postgres_dialect
from typer.testing import CliRunner

import prefect
import prefect.settings
from prefect.cli.dev import dev_app
from prefect.docker import docker_client
from prefect.flow_runners.base import get_prefect_image_name
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_LOGGING_LEVEL,
    PREFECT_LOGGING_ORION_ENABLED,
    PREFECT_ORION_ANALYTICS_ENABLED,
    PREFECT_ORION_DATABASE_CONNECTION_URL,
    PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED,
    PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_ORION_SERVICES_SCHEDULER_ENABLED,
    PREFECT_PROFILES_PATH,
)

# isort: split
# Import fixtures

from prefect.testing.cli import *
from prefect.testing.fixtures import *

from .fixtures.api import *
from .fixtures.client import *
from .fixtures.database import *
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


@pytest.fixture(scope="session", autouse=True)
async def test_database_url(worker_id: str) -> Generator[Optional[str], None, None]:
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

        # TODO: https://github.com/PrefectHQ/orion/issues/2045
        # Also temporarily override the environment variable, so that child
        # subprocesses that we spin off are correctly configured as well
        original_envvar = os.environ.get("PREFECT_ORION_DATABASE_CONNECTION_URL")
        os.environ["PREFECT_ORION_DATABASE_CONNECTION_URL"] = new_url

        yield new_url

        os.environ["PREFECT_ORION_DATABASE_CONNECTION_URL"] = original_envvar

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
def testing_session_settings(test_database_url: str):
    """
    Creates a fixture for the scope of the test session that modifies setting defaults.

    This ensures that tests are isolated from existing settings, databases, etc.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_settings = {
            # Set PREFECT_HOME to a temporary directory to avoid clobbering
            # environments and settings
            PREFECT_HOME: tmpdir,
            PREFECT_PROFILES_PATH: "$PREFECT_HOME/profiles.toml",
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
        }

        if test_database_url:
            test_settings[PREFECT_ORION_DATABASE_CONNECTION_URL] = test_database_url

        profile = prefect.settings.Profile(
            name="test-session", settings=test_settings, source=__file__
        )

        with prefect.context.use_profile(
            profile,
            override_environment_variables=True,
            include_current_context=False,
        ) as ctx:

            assert (
                PREFECT_API_URL.value() is None
            ), "Tests cannot be run connected to an external API."

            setup_logging()

            yield ctx


@pytest.fixture(scope="session")
def docker() -> Generator[DockerClient, None, None]:
    with docker_client() as client:
        yield client


@pytest.fixture(scope="session")
def prefect_base_image(pytestconfig: pytest.Config, docker: DockerClient):
    """Ensure that the prefect dev image is available and up-to-date"""
    image_name = get_prefect_image_name()

    image_exists, version_is_right = False, False

    try:
        image_exists = bool(docker.images.get(image_name))
    except ImageNotFound:
        pass

    if image_exists:
        output = docker.containers.run(image_name, ["prefect", "--version"])
        image_version = output.decode().strip()
        version_is_right = image_version == prefect.__version__

    if not image_exists or not version_is_right:
        if pytestconfig.getoption("--disable-docker-image-builds"):
            if not image_exists:
                raise Exception(
                    "The --disable-docker-image-builds flag is set, but "
                    f"there is no local {image_name} image"
                )
            if not version_is_right:
                raise Exception(
                    "The --disable-docker-image-builds flag is set, but "
                    f"{image_name} includes {image_version}, not {prefect.__version__}"
                )

        CliRunner().invoke(dev_app, ["build-image"])

    return image_name


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield
