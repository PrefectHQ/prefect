import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from prometheus_client import REGISTRY

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


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
def bench_import_prefect(benchmark: "BenchmarkFixture"):
    def import_prefect():
        reset_imports()

        import prefect  # noqa

    benchmark(import_prefect)


@pytest.mark.timeout(180)
@pytest.mark.benchmark(group="imports")
def bench_import_prefect_flow(benchmark: "BenchmarkFixture"):
    def import_prefect_flow():
        reset_imports()

        from prefect import flow  # noqa

    benchmark(import_prefect_flow)
