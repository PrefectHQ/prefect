"""Command line options for the integration tests.

These live at the root of the project, rather than next to the tests, so that
pytest always loads them before it parses the command line.
"""

import pytest
from prefect_armada_integration_tests.utils import prefect_core


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add armada-specific command line options."""
    parser.addoption(
        "--kind-cluster-name",
        action="store",
        default="armada",
        help="Name of the kind cluster running Armada",
    )
    parser.addoption(
        "--work-pool-name",
        action="store",
        help=(
            "Name of the work pool to create and use. Must not already exist. "
            "Defaults to a generated name."
        ),
    )
    parser.addoption(
        "--api-dns-name",
        action="store",
        help=(
            "Address the Prefect API is reachable at from inside the cluster. "
            "Defaults to the gateway of the kind Docker network."
        ),
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reject a `--work-pool-name` that names an existing work pool.

    This runs before any fixture, so the session stops before it has created an
    Armada queue or built and loaded the flow image.
    """
    work_pool_name = session.config.getoption("--work-pool-name")
    if isinstance(work_pool_name, str) and prefect_core.work_pool_exists(
        work_pool_name
    ):
        raise pytest.UsageError(
            f"Work pool {work_pool_name!r} already exists. The tests create "
            "their work pool and delete it afterwards, so they will not reuse "
            "an existing one. Pass a different --work-pool-name, or omit it "
            "to use a generated name."
        )
