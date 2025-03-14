import subprocess
from typing import Generator

import pytest

from prefect_kubernetes_integration_tests.utils import k8s


@pytest.fixture(scope="session")
def kind_cluster(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """Create and manage a kind cluster for the test session."""
    cluster_name = request.config.getoption("--cluster-name", default="prefect-test")
    assert isinstance(cluster_name, str)
    k8s.ensure_kind_cluster(cluster_name)
    yield cluster_name


@pytest.fixture(scope="session")
def work_pool_name(
    request: pytest.FixtureRequest, worker_id: str
) -> Generator[str, None, None]:
    """Get the work pool name to use for tests."""
    default_work_pool_name = (
        f"k8s-test-{worker_id}" if worker_id != "master" else "k8s-test"
    )
    work_pool_name = request.config.getoption("--work-pool-name")
    if not isinstance(work_pool_name, str):
        work_pool_name = default_work_pool_name

    subprocess.check_call(
        [
            "prefect",
            "work-pool",
            "create",
            work_pool_name,
            "--type",
            "kubernetes",
            "--overwrite",
        ]
    )

    yield work_pool_name

    subprocess.check_call(
        [
            "prefect",
            "--no-prompt",
            "work-pool",
            "delete",
            work_pool_name,
        ]
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add kubernetes-specific command line options."""
    parser.addoption(
        "--cluster-name",
        action="store",
        default="prefect-test",
        help="Name of the kind cluster to use",
    )
    parser.addoption(
        "--work-pool-name",
        action="store",
        help="Name of the work pool to use",
    )


@pytest.fixture(autouse=True, scope="session")
def _check_k8s_deps():  # pyright: ignore[reportUnusedFunction]
    """Ensure required kubernetes tools are available."""
    k8s.ensure_evict_plugin()


@pytest.fixture(autouse=True, scope="session")
def clean_up_pods() -> Generator[None, None, None]:
    """Clean up pods after tests."""
    yield
    k8s.delete_pods()
