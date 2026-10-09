import subprocess
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from prefect_armada.settings import ArmadaSettings

from prefect_armada_integration_tests.utils import armada, kind


@pytest.fixture(scope="session")
def kind_cluster(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """The kind cluster running Armada for the test session."""
    cluster_name = request.config.getoption("--kind-cluster-name")
    assert isinstance(cluster_name, str)
    kind.ensure_kind_cluster(cluster_name)
    yield cluster_name


@pytest.fixture(scope="session")
def flow_image(kind_cluster: str) -> str:
    """An image holding the test flows, loaded into the cluster's nodes."""
    return kind.build_and_load_flow_image(kind_cluster)


@pytest.fixture(scope="session")
def armada_queue() -> str:
    """The Armada queue flow runs are submitted to.

    This is the queue a worker falls back to when its work pool does not set
    one, which is also the queue the worker checks for before it starts.
    """
    queue = ArmadaSettings().worker.default_queue
    armada.ensure_queue(queue)
    return queue


@pytest.fixture(scope="session")
def work_pool_name(
    request: pytest.FixtureRequest, armada_queue: str
) -> Generator[str, None, None]:
    """A work pool created for, and owned by, the test session.

    The pool lives on whatever Prefect API the session is pointed at, so it is
    only ever created, never overwritten: the teardown deletes it, and that must
    not reach a pool the session did not create.
    """
    work_pool_name = request.config.getoption("--work-pool-name")
    if not isinstance(work_pool_name, str):
        # Unique per session, and so per xdist worker.
        work_pool_name = f"armada-test-{uuid.uuid4().hex[:8]}"

    # `pytest_sessionstart` has already rejected a requested name that was taken.
    # Without `--overwrite` this fails if the pool appeared since that check.
    subprocess.check_call(
        [
            "prefect",
            "work-pool",
            "create",
            work_pool_name,
            "--type",
            "armada",
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


@pytest.fixture
def job_variables(
    request: pytest.FixtureRequest, flow_image: str, armada_queue: str
) -> dict[str, Any]:
    """Job variables for a flow run that can run on the test cluster."""
    job_variables: dict[str, Any] = {
        "image": flow_image,
        # The image exists only on the cluster's nodes, so it must not be pulled.
        "image_pull_policy": "IfNotPresent",
        "queue": armada_queue,
        # Armada rejects containers whose requests differ from their limits.
        "cpu_request": "200m",
        "cpu_limit": "200m",
        "memory_request": "512Mi",
        "memory_limit": "512Mi",
    }

    # Flow-run pods inherit the worker's PREFECT_API_URL, which for a local
    # server is an address that resolves to the pod itself.
    api_dns_name = request.config.getoption("--api-dns-name")
    if not isinstance(api_dns_name, str):
        api_dns_name = kind.get_gateway_address()
    if api_dns_name:
        job_variables["api_dns_name"] = api_dns_name

    return job_variables
