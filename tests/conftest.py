import asyncio
import logging
import os
import pathlib
import tempfile
import warnings
from typing import Set

import pytest

import prefect
import prefect.settings

from .fixtures.api import *
from .fixtures.client import *
from .fixtures.database import *
from .fixtures.logging import *
from .fixtures.storage import *


def pytest_addoption(parser):
    parser.addoption(
        "--service",
        action="append",
        metavar="SERVICE",
        default=[],
        help="Include service integration tests for SERVICE.",
    )
    parser.addoption(
        "--only-service",
        action="append",
        metavar="SERVICE",
        default=[],
        help="Exclude all tests except service integration tests for SERVICE.",
    )
    parser.addoption(
        "--not-service",
        action="append",
        metavar="SERVICE",
        default=[],
        help="Exclude service integration tests for SERVICE.",
    )
    parser.addoption(
        "--all-services",
        action="store_true",
        default=False,
        help="Include all service integration tests",
    )
    parser.addoption(
        "--only-services",
        action="store_true",
        default=False,
        help="Exclude all tests except service integration tests",
    )


def skip_exclude_services(services: Set[str], items):
    """
    Utility to skip service tests that are excluded by `--not-service`.

    For use with `--all-services` and `--only-services` which would otherwise run tests
    for all services.
    """
    if services:
        for item in items:
            item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
            excluded_services = item_services.intersection(services)
            if excluded_services:
                item.add_marker(
                    pytest.mark.skip(
                        "Excluding tests for service(s): "
                        f"{', '.join(repr(s) for s in excluded_services)}."
                    )
                )


def pytest_collection_modifyitems(session, config, items):
    """
    Update tests to skip in accordance with service requests
    """
    not_services = set(config.getoption("--not-service"))

    if config.getoption("--all-services"):
        skip_exclude_services(not_services, items)

        if config.getoption("--only-service") or config.getoption("--only-services"):
            warnings.warn(
                "`--only-service` cannot be used with `--all-services`. "
                "`--only-service` will be ignored."
            )
        return

    only_run_service_tests = config.getoption("--only-services")
    if only_run_service_tests:
        for item in items:
            item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
            if not item_services:
                item.add_marker(pytest.mark.skip("Only running tests for services."))

        skip_exclude_services(not_services, items)

        if config.getoption("--service"):
            warnings.warn(
                "`--service` cannot be used with `--only-services`. "
                "`--service` will be ignored."
            )
        return

    only_services = set(config.getoption("--only-service"))
    if only_services:
        only_running_blurb = f"Only running tests for service(s): {', '.join(repr(s) for s in only_services)}."
        for item in items:
            item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
            not_in_only_services = only_services.difference(item_services)
            if not_in_only_services:
                item.add_marker(pytest.mark.skip(only_running_blurb))

        if config.getoption("--service"):
            warnings.warn(
                "`--service` cannot be used with `--only-service`. "
                "`--service` will be ignored."
            )
        return

    run_services = set(config.getoption("--service"))
    for item in items:
        item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
        missing_services = item_services.difference(run_services)
        if missing_services:
            item.add_marker(
                pytest.mark.skip(
                    f"Requires service(s): {', '.join(repr(s) for s in missing_services)}. "
                    "Use '--service NAME' to include."
                )
            )


@pytest.fixture(scope="session")
def event_loop(request):
    """
    Redefine the event loop to support session/module-scoped fixtures;
    see https://github.com/pytest-dev/pytest-asyncio/issues/68
    """
    policy = asyncio.get_event_loop_policy()

    if sys.version_info < (3, 8):
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
def tests_profile():
    """
    Creates a fixture for the scope of the test session that sets the PREFECT_HOME to
    a temporary directory to avoid clobbering environments and settings that the
    developer may have configured.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = prefect.settings.get_current_settings().copy_with_update(
            updates={
                prefect.settings.PREFECT_HOME: tmpdir,
                prefect.settings.PREFECT_PROFILES_PATH: "$PREFECT_HOME/profiles.toml",
            }
        )

        with prefect.context.ProfileContext(
            name="base-test-profile", settings=settings
        ) as profile:

            # It is important to initialize the profile so logging is configured
            # when the test run starts rather than lazily once a flow runs
            profile.initialize()

            yield profile
