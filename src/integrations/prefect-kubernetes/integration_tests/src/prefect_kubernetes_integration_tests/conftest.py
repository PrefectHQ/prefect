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
def work_pool_name(request: pytest.FixtureRequest) -> str:
    """Get the work pool name to use for tests."""
    work_pool_name = request.config.getoption("--work-pool-name", default="k8s-test")
    assert isinstance(work_pool_name, str)
    return work_pool_name


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
        default="k8s-test",
        help="Name of the work pool to use",
    )


@pytest.fixture(autouse=True)
def _check_k8s_deps():
    """Ensure required kubernetes tools are available."""
    k8s.ensure_evict_plugin()
