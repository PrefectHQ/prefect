import asyncio
import logging
import pathlib
import tempfile

import pytest

import prefect
import prefect.settings
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_HOME,
    PREFECT_LOGGING_LEVEL,
    PREFECT_LOGGING_ORION_ENABLED,
    PREFECT_ORION_ANALYTICS_ENABLED,
    PREFECT_ORION_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED,
    PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_ORION_SERVICES_SCHEDULER_ENABLED,
    PREFECT_PROFILES_PATH,
)

# isort: off
# Import fixtures

from prefect.testing.fixtures import *
from prefect.testing.cli import *

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
def testing_session_settings():
    """
    Creates a fixture for the scope of the test session that modifies setting defaults.

    This ensures that tests are isolated from existing settings, databases, etc.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        profile = prefect.settings.Profile(
            name="test-session",
            settings={
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
            },
            source=__file__,
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
