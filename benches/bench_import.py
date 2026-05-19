import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from prometheus_client import REGISTRY

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

IMPORT_MODULES = [
    "prefect",
    "prefect.client.schemas",
    "prefect.client.schemas.objects",
    "prefect.flows",
    "prefect.deployments",
    "prefect.events",
    "prefect.events.clients",
    "prefect.server",
    "prefect.server.schemas",
    "prefect.server.schemas.core",
    "prefect.server.schemas.actions",
    "prefect.server.models",
    "prefect.server.models.flow_runs",
    "prefect.server.api",
    "prefect.server.api.flow_runs",
    "prefect.server.api.server",
    "prefect.task_runners",
]


def reset_imports():
    # Remove the module from sys.modules if it's there
    prefect_modules = [key for key in sys.modules if key.startswith("prefect")]
    for module in prefect_modules:
        del sys.modules[module]

    # Clear importlib cache
    importlib.invalidate_caches()

    # reset the prometheus registry to clear any previously measured metrics
    for collector in list(REGISTRY._collector_to_names):
        REGISTRY.unregister(collector)


@pytest.mark.benchmark(group="imports")
@pytest.mark.parametrize("module_name", IMPORT_MODULES, ids=IMPORT_MODULES)
def bench_import_module(benchmark: "BenchmarkFixture", module_name: str):
    def do_import():
        reset_imports()
        importlib.import_module(module_name)

    benchmark(do_import)


@pytest.mark.timeout(180)
@pytest.mark.benchmark(group="imports")
def bench_import_prefect_flow(benchmark: "BenchmarkFixture"):
    """Benchmark the public API form: from prefect import flow"""

    def import_prefect_flow():
        reset_imports()

        from prefect import flow  # noqa: F401

    benchmark(import_prefect_flow)
