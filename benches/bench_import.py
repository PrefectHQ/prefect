import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from prometheus_client import REGISTRY

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

IMPORT_MODULES = [
    # Each entry is the deepest leaf in its import chain so that a regression
    # in any parent module (e.g. prefect.server.schemas) is still caught
    # transitively.  The full 17-module list is exercised by the subprocess-
    # based smoke tests in tests/test_import_smoke.py.
    "prefect",
    "prefect.client.schemas.objects",
    "prefect.flows",
    "prefect.deployments",
    "prefect.events",
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


@pytest.fixture(autouse=True)
def _isolate_imports():
    """Snapshot and restore prefect modules in sys.modules so import benchmarks
    don't corrupt worker state for other benchmark files (e.g. bench_flows,
    bench_tasks) when running under pytest-xdist."""
    saved_prefect = {k: v for k, v in sys.modules.items() if k.startswith("prefect")}
    saved_collectors = set(REGISTRY._collector_to_names)
    yield
    # Remove prefect modules left behind by the benchmark
    for k in [k for k in sys.modules if k.startswith("prefect")]:
        del sys.modules[k]
    # Restore the original prefect module objects
    sys.modules.update(saved_prefect)
    importlib.invalidate_caches()
    # Remove any prometheus collectors added during the benchmark
    for collector in list(REGISTRY._collector_to_names):
        if collector not in saved_collectors:
            REGISTRY.unregister(collector)
    # Re-register any collectors that were removed by reset_imports()
    for collector in saved_collectors:
        if collector not in REGISTRY._collector_to_names:
            REGISTRY.register(collector)


@pytest.mark.timeout(180)
@pytest.mark.benchmark(group="imports")
@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
@pytest.mark.parametrize("module_name", IMPORT_MODULES, ids=IMPORT_MODULES)
def bench_import_module(benchmark: "BenchmarkFixture", module_name: str):
    def do_import():
        reset_imports()
        importlib.import_module(module_name)

    benchmark(do_import)


@pytest.mark.timeout(180)
@pytest.mark.benchmark(group="imports")
@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def bench_import_prefect_flow(benchmark: "BenchmarkFixture"):
    """Benchmark the public API form: from prefect import flow"""

    def import_prefect_flow():
        reset_imports()

        from prefect import flow  # noqa: F401

    benchmark(import_prefect_flow)
